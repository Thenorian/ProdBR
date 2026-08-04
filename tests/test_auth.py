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
