import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PUBLIC_DATABASE_URL"] = "sqlite:///./test_public.sqlite3"
os.environ["COMMUNITY_DATABASE_URL"] = "sqlite:///./test_community.sqlite3"
# Limites de taxa altos o bastante para nao interferir nos testes.
os.environ["RATE_LIMIT_READ"] = "1000/minute"
os.environ["RATE_LIMIT_WRITE"] = "1000/minute"
os.environ["AUTO_APPROVE_REPUTATION"] = "20"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import (  # noqa: E402
    CommunityBase,
    CommunitySession,
    PublicBase,
    community_engine,
    public_engine,
)
from app.main import app  # noqa: E402
from app.models_community import User  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    CommunityBase.metadata.drop_all(bind=community_engine)
    PublicBase.metadata.drop_all(bind=public_engine)
    PublicBase.metadata.create_all(bind=public_engine)
    CommunityBase.metadata.create_all(bind=community_engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def register(client: TestClient, username: str, password: str = "testpass123") -> str:
    res = client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert res.status_code == 201, res.text
    return res.json()["api_key"]["raw_key"]


def set_user(username: str, **fields):
    db = CommunitySession()
    try:
        user = db.query(User).filter(User.username == username).first()
        for field, value in fields.items():
            setattr(user, field, value)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def trusted_headers(client):
    """Usuario com reputacao alta - contribuicoes aplicadas na hora."""
    raw_key = register(client, "trusted_user")
    set_user("trusted_user", reputation=999)
    return {"X-API-Key": raw_key}


@pytest.fixture
def newbie_headers(client):
    """Usuario recem-registrado - reputacao 0, abaixo do limite de auto-aprovacao."""
    raw_key = register(client, "newbie")
    return {"X-API-Key": raw_key}


@pytest.fixture
def moderator_headers(client):
    raw_key = register(client, "mod_user")
    set_user("mod_user", role="moderator")
    return {"X-API-Key": raw_key}
