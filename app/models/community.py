"""Tabelas da base de comunidade - usuários, chaves, sessões e moderação.

Fica só no servidor e nunca é exportada. Por isso Revision.contributor
(na base pública) guarda o nome do usuário em texto, e não uma chave
estrangeira pra cá.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import CommunityBase
from app.models.common import utcnow

ROLES = ("member", "moderator", "admin")


class User(CommunityBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    password_salt: Mapped[str] = mapped_column(String(32))
    # Pontos que decidem a aprovação automática (criar vale mais que editar,
    # rejeição tira pontos) - ver app/services/contributions.py.
    reputation: Mapped[int] = mapped_column(default=0)
    # Contagem pura de edições aplicadas - só decide o nível público
    # (Iniciante, Editor...), ver app/services/reputation.py.
    edit_count: Mapped[int] = mapped_column(default=0)
    role: Mapped[str] = mapped_column(String(20), default="member")
    # Nível concedido por um admin (nome de um Tier). Funciona como piso:
    # vale o maior entre ele e o conquistado por edit_count.
    tier_override: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    # "Aprovar automaticamente": contas de confiança (bots da Thenorian) têm
    # a contribuição aplicada direto, sem fila.
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiKey(CommunityBase):
    """Chave pessoal pra escrita por sistema (ERPs, scripts). Login de
    pessoa usa Session."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), default="default")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="api_keys")


class Session(CommunityBase):
    """Token de login do site, com validade."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PendingChange(CommunityBase):
    """Fila de moderação: contribuição de quem ainda não tem aprovação
    automática espera aqui até um moderador (ou a votação) decidir."""

    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # product | identifier | fiscal_rule | ncm_classification
    entity_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = criação
    payload: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(300))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | approved | rejected

    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PendingVote(CommunityBase):
    """Voto da comunidade numa contribuição pendente: +1 ou -1, um por
    usuário (pode trocar). O saldo que chega em
    settings.community_vote_threshold aprova ou rejeita sozinho."""

    __tablename__ = "pending_votes"
    __table_args__ = (UniqueConstraint("pending_id", "user_id", name="uq_vote_pending_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pending_id: Mapped[int] = mapped_column(ForeignKey("pending_changes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    value: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
