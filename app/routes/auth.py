from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.auth import (
    generate_token,
    hash_password,
    hash_token,
    new_session_expiry,
    require_user,
    verify_password,
)
from app.config import settings
from app.database import get_community_db
from app.models_community import ApiKey, Session as UserSession, User
from app.rate_limit import limiter
from app.schemas_auth import (
    ApiKeyOut,
    LoginRequest,
    RegisterOut,
    RegisterRequest,
    SessionOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_write)
def register(request: Request, payload: RegisterRequest, db: DbSession = Depends(get_community_db)):
    existing = (
        db.query(User)
        .filter(or_(User.username == payload.username, User.email == payload.email))
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username ou e-mail ja em uso.")

    password_hash, salt = hash_password(payload.password)
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=password_hash,
        password_salt=salt,
    )
    db.add(user)
    db.flush()

    raw_key = generate_token()
    db.add(ApiKey(user_id=user.id, name="default", key_hash=hash_token(raw_key)))
    db.commit()

    return RegisterOut(
        username=user.username,
        api_key=ApiKeyOut(name="default", raw_key=raw_key),
    )


@router.post("/login", response_model=SessionOut)
@limiter.limit(settings.rate_limit_write)
def login(request: Request, payload: LoginRequest, db: DbSession = Depends(get_community_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas.")

    raw_token = generate_token()
    expires_at = new_session_expiry()
    db.add(UserSession(user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at))
    db.commit()

    return SessionOut(token=raw_token, expires_at=expires_at)


@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_write)
def create_api_key(
    request: Request,
    name: str = "default",
    db: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    """Gera uma nova chave de API pessoal (para uso programatico). Chaves
    antigas continuam validas - revogue-as manualmente se necessario."""
    raw_key = generate_token()
    db.add(ApiKey(user_id=user.id, name=name, key_hash=hash_token(raw_key)))
    db.commit()
    return ApiKeyOut(name=name, raw_key=raw_key)
