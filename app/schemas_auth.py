import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,40}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("Username deve ter 3-40 caracteres alfanumericos ou underscore.")
        return v

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("E-mail invalido.")
        return v



class AccountUpdate(BaseModel):
    """Edicao da propria conta. Username nao muda: o historico de edicoes
    (Revision.contributor) guarda o nome como texto, renomear quebraria a
    autoria de tudo que a pessoa ja editou."""

    current_password: str
    email: str | None = None
    new_password: str | None = Field(None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str | None) -> str | None:
        if v is not None and not EMAIL_RE.match(v):
            raise ValueError("E-mail invalido.")
        return v


class AccountOut(BaseModel):
    username: str
    email: str
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class ApiKeyOut(BaseModel):
    name: str
    raw_key: str
    note: str = "Guarde esta chave agora - ela nao sera mostrada novamente."


class SessionOut(BaseModel):
    token: str
    expires_at: datetime


class RegisterOut(BaseModel):
    username: str
    api_key: ApiKeyOut


class UserPublic(BaseModel):
    username: str
    reputation: int
    edit_count: int
    tier_name: str
    tier_color: str
    role: str
    created_at: datetime
