"""Reputação do contribuidor: o nível público (Iniciante, Editor...) e quem
tem a contribuição aplicada direto, sem passar pela moderação.

São duas medidas diferentes no User:
- `edit_count`: contagem pura de edições aplicadas -> nível público;
- `reputation`: pontos (criar vale mais que editar, rejeição tira) ->
  aprovação automática.
"""

from dataclasses import dataclass

from app.config import settings
from app.schemas.auth import UserPublic


@dataclass(frozen=True)
class Tier:
    name: str
    min_edits: int
    color: str  # hex, pro selo na tela


TIERS: list[Tier] = [
    Tier("Iniciante", 0, "#9aa1b0"),
    Tier("Editor", 100, "#059669"),
    Tier("Renomado", 1000, "#4f46e5"),
    Tier("Mestre", 10_000, "#9333ea"),
    Tier("Supremo", 1_000_000, "#f59e0b"),
]


def tier_for(edit_count: int) -> Tier:
    current = TIERS[0]
    for tier in TIERS:
        if edit_count < tier.min_edits:
            break
        current = tier
    return current


def tier_by_name(name: str | None) -> Tier | None:
    return next((t for t in TIERS if t.name == name), None)


def effective_tier(user) -> Tier:
    """O maior entre o nível conquistado (edit_count) e o concedido por um
    admin (tier_override) - conceder nunca rebaixa quem já conquistou mais."""
    earned = tier_for(user.edit_count)
    granted = tier_by_name(user.tier_override)
    if granted is not None and granted.min_edits > earned.min_edits:
        return granted
    return earned


def can_auto_approve(user) -> bool:
    """Contribuição aplicada direto (sem fila) quando o usuário é moderador
    ou admin, está marcado como "Aprovar automaticamente" (bots de
    confiança), tem reputação suficiente ou já passou de Iniciante."""
    return (
        user.role in ("moderator", "admin")
        or bool(user.auto_approve)
        or user.reputation >= settings.auto_approve_reputation
        or effective_tier(user).min_edits > TIERS[0].min_edits
    )


def reputation_delta(is_creation: bool) -> int:
    return settings.reputation_per_create if is_creation else settings.reputation_per_update


def credit(user, is_creation: bool) -> None:
    """Contribuição aplicada: soma reputação e conta a edição."""
    user.reputation += reputation_delta(is_creation)
    user.edit_count += 1


def penalize(user) -> None:
    """Contribuição rejeitada."""
    user.reputation = max(0, user.reputation - settings.reputation_penalty_reject)


def user_public(user) -> UserPublic:
    """Perfil público (sem e-mail)."""
    tier = effective_tier(user)
    return UserPublic(
        username=user.username,
        reputation=user.reputation,
        edit_count=user.edit_count,
        tier_name=tier.name,
        tier_color=tier.color,
        role=user.role,
        created_at=user.created_at,
    )
