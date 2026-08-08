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
