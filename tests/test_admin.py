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
