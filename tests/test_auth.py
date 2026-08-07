def test_register_creates_user_and_key(client):
    res = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "supersecret1"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "alice"
    assert len(body["api_key"]["raw_key"]) > 20


def test_register_duplicate_username_conflicts(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "supersecret1"}
    client.post("/auth/register", json=payload)
    res = client.post("/auth/register", json={**payload, "email": "other@example.com"})
    assert res.status_code == 409


def test_login_returns_session_token(client):
    client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "supersecret1"},
    )
    res = client.post("/auth/login", json={"username": "carol", "password": "supersecret1"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password_rejected(client):
    client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "supersecret1"},
    )
    res = client.post("/auth/login", json={"username": "dave", "password": "wrong"})
    assert res.status_code == 401


def test_regenerate_api_key_revokes_old_one(client):
    register = client.post(
        "/auth/register",
        json={"username": "frank", "email": "frank@example.com", "password": "supersecret1"},
    )
    old_key = register.json()["api_key"]["raw_key"]

    res = client.post("/auth/api-key/regenerate", headers={"X-API-Key": old_key})
    assert res.status_code == 201
    new_key = res.json()["raw_key"]
    assert new_key != old_key

    write_with_old = client.post(
        "/products",
        json={"name": "X", "ncm": "12345678", "source": "t", "reason": "reg"},
        headers={"X-API-Key": old_key},
    )
    assert write_with_old.status_code == 401

    write_with_new = client.post(
        "/products",
        json={"name": "X", "ncm": "12345678", "source": "t", "reason": "reg"},
        headers={"X-API-Key": new_key},
    )
    assert write_with_new.status_code in (201, 202)


def test_regenerate_api_key_via_session_token(client):
    """Cobre o caso real de uso: usuario perdeu a chave, mas ainda
    consegue logar com usuario/senha para gerar uma nova."""
    client.post(
        "/auth/register",
        json={"username": "grace", "email": "grace@example.com", "password": "supersecret1"},
    )
    login = client.post("/auth/login", json={"username": "grace", "password": "supersecret1"})
    token = login.json()["token"]

    res = client.post("/auth/api-key/regenerate", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert len(res.json()["raw_key"]) > 20


def test_session_token_authenticates_write(client):
    client.post(
        "/auth/register",
        json={"username": "erin", "email": "erin@example.com", "password": "supersecret1"},
    )
    login = client.post("/auth/login", json={"username": "erin", "password": "supersecret1"})
    token = login.json()["token"]

    res = client.post(
        "/products",
        json={
            "name": "Produto via sessao",
            "ncm": "12345678",
            "source": "teste",
            "reason": "criacao de teste",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # newbie (reputacao 0) -> vai para moderacao, nao aplica na hora
    assert res.status_code == 202
