from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import CommunityBase

ROLES = ("member", "moderator", "admin")


def utcnow() -> datetime:
    # Naive-UTC de proposito - ver comentario equivalente em models_public.py.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(CommunityBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    password_salt: Mapped[str] = mapped_column(String(32))
    reputation: Mapped[int] = mapped_column(default=0)
    role: Mapped[str] = mapped_column(String(20), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiKey(CommunityBase):
    """Chave pessoal para escrita programatica (ERPs, scripts). Login
    humano usa Session, nao isso - ver app/auth.py."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), default="default")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="api_keys")


class Session(CommunityBase):
    """Token de login humano (site/UI de moderacao), com expiracao."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PendingChange(CommunityBase):
    """Fila de moderacao: contribuicoes de usuarios com reputacao abaixo
    do limite de auto-aprovacao ficam aqui ate um moderador revisar."""

    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # product | identifier | fiscal_rule
    entity_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = criacao
    payload: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(300))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending|approved|rejected

    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
