from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.auth import require_admin, require_moderator
from app.config import settings
from app.database import get_community_db
from app.models_community import ROLES, User
from app.rate_limit import limiter
from app.reputation_tiers import TIERS, tier_by_name, tier_for, user_public

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: str


class AutoApproveUpdate(BaseModel):
    auto_approve: bool


class TierUpdate(BaseModel):
    tier: str | None  # nome do nivel (ex: "Mestre"); None tira o nivel concedido


def _admin_view(user: User, viewer: User) -> dict:
    view = {
        **user_public(user).model_dump(),
        "tier_override": user.tier_override,
        "earned_tier": tier_for(user.edit_count).name,
        "auto_approve": bool(user.auto_approve),
    }
    # E-mail so pro admin (pra saber de quem e cada conta, ex: a conta de
    # integracao do Simple ERP) - moderador so precisa do checkbox.
    if viewer.role == "admin":
        view["email"] = user.email
    return view


@router.get("/users")
@limiter.limit(settings.rate_limit_read)
def list_users(
    request: Request,
    db_community: DbSession = Depends(get_community_db),
    viewer: User = Depends(require_moderator),
):
    """Todos os usuarios (inclusive iniciantes, que o ranking publico de
    /users esconde). Moderador ve pra marcar "Aprovar automaticamente";
    papel/nivel/e-mail so admin."""
    users = db_community.query(User).order_by(User.created_at).all()
    return [_admin_view(u, viewer) for u in users]


@router.put("/users/{username}/role")
@limiter.limit(settings.rate_limit_write)
def update_role(
    request: Request,
    username: str,
    payload: RoleUpdate,
    db_community: DbSession = Depends(get_community_db),
    admin: User = Depends(require_admin),
):
    """Muda o papel (member/moderator/admin) de outro usuario. moderator e
    admin tem as contribuicoes aplicadas direto, sem fila de moderacao (ver
    app/changes.py::can_auto_approve) - e assim que uma conta de integracao
    confiavel (ex: Simple ERP) passa a cadastrar produto com codigo de
    barras na hora."""
    if payload.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Papel invalido. Use um de: {', '.join(ROLES)}.",
        )
    user = db_community.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    # Nunca o proprio papel - evita o admin se trancar pra fora sem querer.
    # Isso tambem garante que sempre sobra pelo menos um admin (quem pede).
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Voce nao pode mudar o seu proprio papel."
        )
    user.role = payload.role
    db_community.commit()
    db_community.refresh(user)
    return _admin_view(user, admin)


@router.get("/tiers")
@limiter.limit(settings.rate_limit_read)
def list_tiers(request: Request, admin: User = Depends(require_admin)):
    return [{"name": t.name, "min_edits": t.min_edits, "color": t.color} for t in TIERS]


@router.put("/users/{username}/tier")
@limiter.limit(settings.rate_limit_write)
def update_tier(
    request: Request,
    username: str,
    payload: TierUpdate,
    db_community: DbSession = Depends(get_community_db),
    admin: User = Depends(require_admin),
):
    """Concede um nivel (Iniciante..Supremo). E um piso: vale o maior entre
    o concedido e o conquistado por edicoes - nunca rebaixa ninguem."""
    if payload.tier is not None and tier_by_name(payload.tier) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nivel invalido. Use um de: {', '.join(t.name for t in TIERS)}.",
        )
    user = db_community.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    user.tier_override = payload.tier
    db_community.commit()
    db_community.refresh(user)
    return _admin_view(user, admin)


@router.put("/users/{username}/auto-approve")
@limiter.limit(settings.rate_limit_write)
def update_auto_approve(
    request: Request,
    username: str,
    payload: AutoApproveUpdate,
    db_community: DbSession = Depends(get_community_db),
    moderator: User = Depends(require_moderator),
):
    """Checkbox "Aprovar automaticamente" (moderador ou admin): contas de
    confianca - bots da Thenorian - tem as contribuicoes aplicadas direto,
    sem precisar de papel de moderador nem de nivel."""
    user = db_community.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    user.auto_approve = payload.auto_approve
    db_community.commit()
    db_community.refresh(user)
    return _admin_view(user, moderator)
