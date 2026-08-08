from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import User
from app.models_public import Revision
from app.rate_limit import limiter
from app.reputation_tiers import TIERS, user_public
from app.schemas_auth import UserPublic

router = APIRouter(tags=["users"])

# Editor+ (segundo nivel) - iniciantes (nivel 0) nao aparecem no ranking
# publico, senao qualquer conta recem-criada apareceria la.
CONTRIBUTOR_MIN_EDITS = TIERS[1].min_edits


@router.get("/users", response_model=list[UserPublic])
@limiter.limit(settings.rate_limit_read)
def list_contributors(
    request: Request,
    limit: int = 20,
    db_community: DbSession = Depends(get_community_db),
):
    """Ranking publico de contribuidores (nivel Editor pra cima - ver
    app/reputation_tiers.py) por numero de edicoes. So dados publicos do
    perfil (sem e-mail)."""
    limit = max(1, min(limit, 50))
    users = (
        db_community.query(User)
        .filter(User.edit_count >= CONTRIBUTOR_MIN_EDITS)
        .order_by(User.edit_count.desc(), User.created_at)
        .limit(limit)
        .all()
    )
    return [user_public(u) for u in users]


@router.get("/users/{username}", response_model=UserPublic)
@limiter.limit(settings.rate_limit_read)
def get_user_profile(
    request: Request,
    username: str,
    db_community: DbSession = Depends(get_community_db),
    db_public: DbSession = Depends(get_public_db),
):
    """Perfil publico de um contribuidor - reputacao e papel, sem e-mail
    nem qualquer outro dado de autenticacao (isso fica so na base de
    comunidade, que nunca e distribuida)."""
    user = db_community.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    return user_public(user)


@router.get("/users/{username}/contributions", response_model=list)
@limiter.limit(settings.rate_limit_read)
def get_user_contributions(
    request: Request,
    username: str,
    limit: int = settings.max_page_size,
    db_public: DbSession = Depends(get_public_db),
):
    limit = max(1, min(limit, settings.max_page_size))
    revisions = (
        db_public.query(Revision)
        .filter(Revision.contributor == username)
        .order_by(Revision.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "action": r.action,
            "field": r.field,
            "created_at": r.created_at,
        }
        for r in revisions
    ]
