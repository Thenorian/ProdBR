"""Niveis publicos de contribuidor, baseados em contagem pura de edicoes
aplicadas (User.edit_count) - so conta edicoes, nao consultas. Separado da
`reputation` usada internamente para decidir auto-aprovacao."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    name: str
    min_edits: int
    color: str  # hex, para exibir na UI (badge)


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
        if edit_count >= tier.min_edits:
            current = tier
        else:
            break
    return current


def tier_by_name(name: str | None) -> Tier | None:
    return next((t for t in TIERS if t.name == name), None)


def effective_tier(user) -> Tier:
    """O maior entre o nivel conquistado (edit_count) e o concedido por um
    admin (tier_override) - conceder nunca rebaixa quem ja conquistou mais."""
    earned = tier_for(user.edit_count)
    granted = tier_by_name(getattr(user, "tier_override", None))
    if granted is not None and granted.min_edits > earned.min_edits:
        return granted
    return earned


def user_public(user):
    """Monta um schemas_auth.UserPublic a partir de um User - import local
    pra evitar dependencia circular (schemas_auth nao importa daqui)."""
    from app.schemas_auth import UserPublic

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
