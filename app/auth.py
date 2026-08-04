import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_community_db
from app.models_community import ApiKey
from app.models_community import Session as UserSession
from app.models_community import User

PBKDF2_ITERATIONS = 260_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, password_hash)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def new_session_expiry() -> datetime:
    return utcnow() + timedelta(hours=settings.session_ttl_hours)


def get_user_by_api_key(db: DbSession, raw_key: str) -> User | None:
    key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_token(raw_key), ApiKey.is_active.is_(True))
        .first()
    )
    return key.user if key else None


def get_user_by_session_token(db: DbSession, raw_token: str) -> User | None:
    session = db.query(UserSession).filter(UserSession.token_hash == hash_token(raw_token)).first()
    if session is None or session.expires_at < utcnow():
        return None
    return db.get(User, session.user_id)


def require_user(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
    db: DbSession = Depends(get_community_db),
) -> User:
    """Aceita chave de API pessoal (X-API-Key, uso programatico) ou token
    de sessao (Authorization: Bearer ..., uso humano/login)."""
    if x_api_key:
        user = get_user_by_api_key(db, x_api_key)
        if user:
            return user
    if authorization and authorization.lower().startswith("bearer "):
        user = get_user_by_session_token(db, authorization[7:])
        if user:
            return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticacao necessaria: envie X-API-Key ou Authorization: Bearer <token de sessao>.",
    )


def require_moderator(user: User = Depends(require_user)) -> User:
    if user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acao restrita a moderadores."
        )
    return user


def can_auto_approve(user: User) -> bool:
    return user.role in ("moderator", "admin") or user.reputation >= settings.auto_approve_reputation
