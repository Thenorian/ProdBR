import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_FOLDER = Path(tempfile.mkdtemp(prefix="prodbr_tests_"))
os.environ["DB_PATH"] = str(TEST_FOLDER / "prodbr.sqlite3")
os.environ["COMMUNITY_DB_PATH"] = str(TEST_FOLDER / "prodbr_community.sqlite3")
os.environ["LEGACY_PUBLIC_DB_PATH"] = str(TEST_FOLDER / "nao_existe_public.sqlite3")
os.environ["LEGACY_COMMUNITY_DB_PATH"] = str(TEST_FOLDER / "nao_existe_community.sqlite3")
# Os testes nunca baixam nada do governo.
os.environ["NCM_AUTO_UPDATE"] = "false"
# Pasta vazia: cada teste escolhe se importa a tabela pequena de NCM (fixture ncm_table).
os.environ["NCM_TABLES_FOLDER"] = str(TEST_FOLDER / "sem_tabelas_ncm")

from fastapi.testclient import TestClient  # noqa: E402

from api import rate_limit  # noqa: E402
from api.main import app  # noqa: E402
from database.database import Database  # noqa: E402
from database.setup import prepare_databases  # noqa: E402

SMALL_NCM_TABLE = Path(__file__).resolve().parent / "files" / "ncm_pequena.json"


@pytest.fixture(autouse=True)
def empty_databases():
    """Cada teste começa com os bancos vazios e o limite de requisições zerado."""
    for file in TEST_FOLDER.glob("prodbr*.sqlite3"):
        file.unlink()
    prepare_databases()
    rate_limit.request_times_by_key.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def create_contributor(client, username, trusted=False, moderator=False, hours_ago=48):
    """Cria um contribuidor e devolve o token. Por padrão, um Iniciante com conta de 2 dias (já pode votar)."""
    from database.contributor import ContributorDB

    response = client.post("/contributors", json={"username": username})
    assert response.status_code == 201, response.text
    ContributorDB().run_sql(
        "UPDATE contributors SET trusted = ?, moderator = ?, created_at = datetime('now', ?) WHERE username = ?",
        (int(trusted), int(moderator), f"-{hours_ago} hours", username),
        fetch="rowcount",
    )
    return response.json()["token"]


@pytest.fixture
def token(client):
    """Contribuidor confiável: grava direto, sem passar pela votação."""
    return create_contributor(client, "testador", trusted=True)


@pytest.fixture
def beginner_auth(client):
    """Contribuidor Iniciante: as alterações vão para a fila de votação."""
    return {"X-API-Key": create_contributor(client, "iniciante")}


@pytest.fixture
def auth(token):
    return {"X-API-Key": token}


@pytest.fixture
def ncm_table():
    from util.data_util import DataUtil
    ok, summary = DataUtil().import_ncm_file(SMALL_NCM_TABLE)
    assert ok, summary
    return summary


def public_database():
    return Database()
