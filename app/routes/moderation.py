from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app.auth import require_moderator, require_user
from app.changes import dispatch_apply, reputation_delta
from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import PendingChange, PendingVote, User
from app.rate_limit import limiter
from app.routes.common import apply_or_400
from app.schemas_moderation import ModerationDecision, PendingChangeOut, VoteRequest

router = APIRouter(prefix="/moderation", tags=["moderation"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_pending(db_community: DbSession, pending_id: int) -> PendingChange:
    pending = db_community.get(PendingChange, pending_id)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribuicao nao encontrada.")
    if pending.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contribuicao ja foi '{pending.status}'.",
        )
    return pending


def _vote_counts(db_community: DbSession, pending_id: int) -> tuple[int, int]:
    rows = (
        db_community.query(PendingVote.value, func.count())
        .filter(PendingVote.pending_id == pending_id)
        .group_by(PendingVote.value)
        .all()
    )
    counts = dict(rows)
    return counts.get(1, 0), counts.get(-1, 0)


def _to_out(db_community: DbSession, pending: PendingChange, viewer: User | None = None) -> PendingChangeOut:
    proposer = db_community.get(User, pending.user_id)
    votes_for, votes_against = _vote_counts(db_community, pending.id)
    my_vote = 0
    if viewer is not None:
        vote = (
            db_community.query(PendingVote)
            .filter(PendingVote.pending_id == pending.id, PendingVote.user_id == viewer.id)
            .first()
        )
        my_vote = vote.value if vote else 0
    return PendingChangeOut(
        id=pending.id,
        entity_type=pending.entity_type,
        entity_id=pending.entity_id,
        payload=pending.payload,
        reason=pending.reason,
        contributor=proposer.username if proposer else "?",
        status=pending.status,
        created_at=pending.created_at,
        votes_for=votes_for,
        votes_against=votes_against,
        my_vote=my_vote,
        vote_threshold=settings.community_vote_threshold,
    )


def _approve(db_public: DbSession, db_community: DbSession, pending: PendingChange, reviewer_id: int | None):
    """Aplica na base publica e credita o autor. reviewer_id None = aprovada
    pela votacao da comunidade, nao por um moderador."""
    proposer = db_community.get(User, pending.user_id)
    apply_or_400(
        dispatch_apply,
        db_public,
        pending.entity_type,
        pending.entity_id,
        pending.payload,
        proposer.username if proposer else None,
        pending.reason,
    )
    pending.status = "approved"
    pending.reviewed_by = reviewer_id
    pending.reviewed_at = _utcnow()
    if reviewer_id is None:
        pending.review_note = "Aprovada pela votacao da comunidade."
    if proposer is not None:
        proposer.reputation += reputation_delta(pending.entity_id)
        proposer.edit_count += 1
    db_community.commit()


def _reject(db_community: DbSession, pending: PendingChange, reviewer_id: int | None, note: str | None):
    proposer = db_community.get(User, pending.user_id)
    pending.status = "rejected"
    pending.reviewed_by = reviewer_id
    pending.reviewed_at = _utcnow()
    pending.review_note = note
    if proposer is not None:
        proposer.reputation = max(0, proposer.reputation - settings.reputation_penalty_reject)
    db_community.commit()


@router.get("/queue", response_model=list[PendingChangeOut])
@limiter.limit(settings.rate_limit_read)
def moderation_queue(
    request: Request,
    limit: int = settings.max_page_size,
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    """Contribuicoes pendentes. Aberta a qualquer usuario logado (todos
    podem votar - ver vote); so moderador aprova/rejeita direto."""
    limit = max(1, min(limit, settings.max_page_size))
    pendings = (
        db_community.query(PendingChange)
        .filter(PendingChange.status == "pending")
        .order_by(PendingChange.id)
        .limit(limit)
        .all()
    )
    return [_to_out(db_community, p, user) for p in pendings]


@router.post("/{pending_id}/vote", response_model=PendingChangeOut)
@limiter.limit(settings.rate_limit_write)
def vote(
    request: Request,
    pending_id: int,
    payload: VoteRequest,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    """Voto da comunidade. Saldo (a favor - contra) >= limite aprova e
    aplica na hora; <= -limite rejeita. Autor nao vota na propria
    contribuicao; conta nova (menos de vote_min_account_age_hours) tambem
    nao - senao bastaria criar N contas pra se auto-aprovar."""
    if payload.value not in (1, -1, 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voto deve ser 1, -1 ou 0.")
    pending = _load_pending(db_community, pending_id)
    if pending.user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Voce nao pode votar na sua propria contribuicao."
        )
    min_age = timedelta(hours=settings.vote_min_account_age_hours)
    if _utcnow() - user.created_at < min_age:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Contas com menos de {settings.vote_min_account_age_hours}h ainda nao podem votar.",
        )

    existing = (
        db_community.query(PendingVote)
        .filter(PendingVote.pending_id == pending.id, PendingVote.user_id == user.id)
        .first()
    )
    if payload.value == 0:
        if existing is not None:
            db_community.delete(existing)
    elif existing is not None:
        existing.value = payload.value
    else:
        db_community.add(PendingVote(pending_id=pending.id, user_id=user.id, value=payload.value))
    db_community.commit()

    votes_for, votes_against = _vote_counts(db_community, pending.id)
    score = votes_for - votes_against
    if score >= settings.community_vote_threshold:
        _approve(db_public, db_community, pending, reviewer_id=None)
    elif score <= -settings.community_vote_threshold:
        _reject(db_community, pending, reviewer_id=None, note="Rejeitada pela votacao da comunidade.")
    return _to_out(db_community, pending, user)


@router.post("/{pending_id}/approve", response_model=PendingChangeOut)
@limiter.limit(settings.rate_limit_write)
def approve_pending_change(
    request: Request,
    pending_id: int,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    moderator: User = Depends(require_moderator),
):
    pending = _load_pending(db_community, pending_id)
    _approve(db_public, db_community, pending, reviewer_id=moderator.id)
    return _to_out(db_community, pending, moderator)


@router.post("/{pending_id}/reject", response_model=PendingChangeOut)
@limiter.limit(settings.rate_limit_write)
def reject_pending_change(
    request: Request,
    pending_id: int,
    payload: ModerationDecision,
    db_community: DbSession = Depends(get_community_db),
    moderator: User = Depends(require_moderator),
):
    pending = _load_pending(db_community, pending_id)
    _reject(db_community, pending, reviewer_id=moderator.id, note=payload.note)
    return _to_out(db_community, pending, moderator)
