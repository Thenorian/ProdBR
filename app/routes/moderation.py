from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.auth import require_moderator
from app.changes import dispatch_apply, reputation_delta
from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import PendingChange, User
from app.rate_limit import limiter
from app.routes.common import apply_or_400
from app.schemas_moderation import ModerationDecision, PendingChangeOut

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


@router.get("/queue", response_model=list[PendingChangeOut])
@limiter.limit(settings.rate_limit_read)
def moderation_queue(
    request: Request,
    limit: int = settings.max_page_size,
    db_community: DbSession = Depends(get_community_db),
    moderator: User = Depends(require_moderator),
):
    limit = max(1, min(limit, settings.max_page_size))
    pendings = (
        db_community.query(PendingChange)
        .filter(PendingChange.status == "pending")
        .order_by(PendingChange.id)
        .limit(limit)
        .all()
    )
    out = []
    for p in pendings:
        proposer = db_community.get(User, p.user_id)
        out.append(
            PendingChangeOut(
                id=p.id,
                entity_type=p.entity_type,
                entity_id=p.entity_id,
                payload=p.payload,
                reason=p.reason,
                contributor=proposer.username if proposer else "?",
                status=p.status,
                created_at=p.created_at,
            )
        )
    return out


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
    pending.reviewed_by = moderator.id
    pending.reviewed_at = _utcnow()
    if proposer is not None:
        proposer.reputation += reputation_delta(pending.entity_id)
    db_community.commit()

    return PendingChangeOut(
        id=pending.id,
        entity_type=pending.entity_type,
        entity_id=pending.entity_id,
        payload=pending.payload,
        reason=pending.reason,
        contributor=proposer.username if proposer else "?",
        status=pending.status,
        created_at=pending.created_at,
    )


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
    proposer = db_community.get(User, pending.user_id)

    pending.status = "rejected"
    pending.reviewed_by = moderator.id
    pending.reviewed_at = _utcnow()
    pending.review_note = payload.note
    if proposer is not None:
        proposer.reputation = max(0, proposer.reputation - settings.reputation_penalty_reject)
    db_community.commit()

    return PendingChangeOut(
        id=pending.id,
        entity_type=pending.entity_type,
        entity_id=pending.entity_id,
        payload=pending.payload,
        reason=pending.reason,
        contributor=proposer.username if proposer else "?",
        status=pending.status,
        created_at=pending.created_at,
    )
