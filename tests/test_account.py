from tests.conftest import register


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_me_returns_private_email(client):
    headers = {"X-API-Key": register(client, "alice")}
    res = client.get("/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "alice@example.com"


def test_update_requires_current_password(client):
    headers = {"X-API-Key": register(client, "alice")}
    res = client.put("/auth/me", json={"current_password": "errada123", "email": "novo@example.com"}, headers=headers)
    assert res.status_code == 403
    assert client.get("/auth/me", headers=headers).json()["email"] == "alice@example.com"


def test_change_email(client):
    headers = {"X-API-Key": register(client, "alice")}
    res = client.put("/auth/me", json={"current_password": "testpass123", "email": "alice2@example.com"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "alice2@example.com"


def test_email_already_taken(client):
    register(client, "bob")
    headers = {"X-API-Key": register(client, "alice")}
    res = client.put("/auth/me", json={"current_password": "testpass123", "email": "bob@example.com"}, headers=headers)
    assert res.status_code == 409


def test_change_password_revokes_sessions(client):
    register(client, "alice")
    token = login(client, "alice", "testpass123").json()["token"]
    session_headers = {"Authorization": f"Bearer {token}"}

    res = client.put("/auth/me", json={"current_password": "testpass123", "new_password": "outrasenha456"}, headers=session_headers)
    assert res.status_code == 200, res.text

    assert client.get("/auth/me", headers=session_headers).status_code == 401
    assert login(client, "alice", "testpass123").status_code == 401
    assert login(client, "alice", "outrasenha456").status_code == 200


def test_short_password_and_nothing_to_change(client):
    headers = {"X-API-Key": register(client, "alice")}
    assert client.put("/auth/me", json={"current_password": "testpass123", "new_password": "curta"}, headers=headers).status_code == 422
    assert client.put("/auth/me", json={"current_password": "testpass123"}, headers=headers).status_code == 400
