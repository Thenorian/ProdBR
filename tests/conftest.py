import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DATABASE_URL"] = "sqlite:///./test_prodbr.sqlite3"
# Limites de taxa altos o bastante para nao interferir nos testes.
os.environ["RATE_LIMIT_READ"] = "1000/minute"
os.environ["RATE_LIMIT_WRITE"] = "1000/minute"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ApiKey  # noqa: E402
from app.security import generate_key, hash_key  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def api_key_header():
    raw_key = generate_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(name="test-key", key_hash=hash_key(raw_key)))
        db.commit()
    finally:
        db.close()
    return {"X-API-Key": raw_key}
