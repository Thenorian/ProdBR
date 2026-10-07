import pytest

from tests.conftest import register, set_user


@pytest.fixture
def admin_headers(client):
    raw_key = register(client, "admin_user")
    set_user("admin_user", role="admin")
    return {"X-API-Key": raw_key}


def test_list_users_requires_admin(client, newbie_headers, moderator_headers):
    assert client.get("/admin/users", headers=newbie_headers).status_code == 403
    assert client.get("/admin/users", headers=moderator_headers).status_code == 403
    assert client.get("/admin/users").status_code == 401


def test_list_users_includes_beginners_and_email(client, admin_headers, newbie_headers):
    res = client.get("/admin/users", headers=admin_headers)
    assert res.status_code == 200
    by_name = {u["username"]: u for u in res.json()}
    assert by_name["newbie"]["email"] == "newbie@example.com"
    assert by_name["newbie"]["role"] == "member"


def test_admin_promotes_user_and_contributions_skip_queue(client, admin_headers, newbie_headers):
    res = client.put("/admin/users/newbie/role", json={"role": "moderator"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "moderator"

    # Agora aplica direto (201), sem ir pra fila (202).
    res = client.post(
        "/products",
        json={"name": "Produto confiavel", "ncm": "22030000", "source": "Teste", "reason": "Teste"},
        headers=newbie_headers,
    )
    assert res.status_code == 201, res.text


def test_admin_cannot_change_own_role(client, admin_headers):
    res = client.put("/admin/users/admin_user/role", json={"role": "member"}, headers=admin_headers)
    assert res.status_code == 400


def test_invalid_role_and_unknown_user(client, admin_headers, newbie_headers):
    assert client.put("/admin/users/newbie/role", json={"role": "rei"}, headers=admin_headers).status_code == 400
    assert client.put("/admin/users/ninguem/role", json={"role": "member"}, headers=admin_headers).status_code == 404


def test_moderator_cannot_change_roles(client, moderator_headers, newbie_headers):
    res = client.put("/admin/users/newbie/role", json={"role": "admin"}, headers=moderator_headers)
    assert res.status_code == 403


def test_admin_grants_tier_as_floor(client, admin_headers, newbie_headers):
    res = client.put("/admin/users/newbie/tier", json={"tier": "Mestre"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["tier_name"] == "Mestre"
    assert res.json()["earned_tier"] == "Iniciante"
    # Perfil publico tambem mostra o nivel concedido.
    assert client.get("/users/newbie").json()["tier_name"] == "Mestre"


def test_granted_tier_never_lowers_earned_one(client, admin_headers, newbie_headers):
    set_user("newbie", edit_count=1000)  # conquistou Renomado
    res = client.put("/admin/users/newbie/tier", json={"tier": "Editor"}, headers=admin_headers)
    assert res.json()["tier_name"] == "Renomado"


def test_remove_granted_tier_and_invalid_tier(client, admin_headers, newbie_headers):
    client.put("/admin/users/newbie/tier", json={"tier": "Mestre"}, headers=admin_headers)
    res = client.put("/admin/users/newbie/tier", json={"tier": None}, headers=admin_headers)
    assert res.json()["tier_name"] == "Iniciante"
    assert client.put("/admin/users/newbie/tier", json={"tier": "Deus"}, headers=admin_headers).status_code == 400
    assert client.put("/admin/users/newbie/tier", json={"tier": "Mestre"}, headers=newbie_headers).status_code == 403


def test_ensure_column_adds_missing_column():
    from sqlalchemy import create_engine, inspect, text

    from app.database import ensure_column

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    ensure_column(engine, "users", "tier_override", "VARCHAR(20)")
    ensure_column(engine, "users", "tier_override", "VARCHAR(20)")  # idempotente
    assert "tier_override" in {c["name"] for c in inspect(engine).get_columns("users")}
