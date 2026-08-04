from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import User
from app.models_public import Revision
from app.rate_limit import limiter
from app.schemas_auth import UserPublic

router = APIRouter(tags=["users"])


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
    return UserPublic(username=user.username, reputation=user.reputation, role=user.role, created_at=user.created_at)


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
