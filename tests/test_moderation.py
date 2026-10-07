from tests.conftest import set_user


def make_product_payload(**overrides):
    payload = {
        "name": "Produto proposto por newbie",
        "ncm": "22030000",
        "source": "Contribuicao da comunidade",
        "reason": "Cadastro inicial",
    }
    payload.update(overrides)
    return payload


def test_moderation_queue_open_to_logged_users_but_decisions_are_moderator_only(client, newbie_headers):
    # Fila aberta a qualquer logado (comunidade vota); aprovar/rejeitar direto
    # continua so pra moderador.
    assert client.get("/moderation/queue").status_code == 401
    assert client.get("/moderation/queue", headers=newbie_headers).status_code == 200
    res = client.post("/products", json=make_product_payload(), headers=newbie_headers)
    pending_id = res.json()["pending_change_id"]
    assert client.post(f"/moderation/{pending_id}/approve", headers=newbie_headers).status_code == 403


def test_approve_applies_change_and_grants_reputation(client, newbie_headers, moderator_headers):
    create = client.post("/products", json=make_product_payload(), headers=newbie_headers)
    pending_id = create.json()["pending_change_id"]

    queue = client.get("/moderation/queue", headers=moderator_headers).json()
    assert any(p["id"] == pending_id for p in queue)

    res = client.post(f"/moderation/{pending_id}/approve", headers=moderator_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    search = client.get("/products", params={"ncm": "22030000"})
    assert search.json()["total"] == 1

    profile = client.get("/users/newbie").json()
    assert profile["reputation"] > 0


def test_reject_does_not_apply_and_penalizes(client, newbie_headers, moderator_headers):
    set_user("newbie", reputation=5)
    create = client.post("/products", json=make_product_payload(), headers=newbie_headers)
    pending_id = create.json()["pending_change_id"]

    res = client.post(
        f"/moderation/{pending_id}/reject", json={"note": "NCM invalido"}, headers=moderator_headers
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    search = client.get("/products", params={"ncm": "22030000"})
    assert search.json()["total"] == 0

    profile = client.get("/users/newbie").json()
    assert profile["reputation"] < 5


def test_cannot_approve_twice(client, newbie_headers, moderator_headers):
    create = client.post("/products", json=make_product_payload(), headers=newbie_headers)
    pending_id = create.json()["pending_change_id"]

    client.post(f"/moderation/{pending_id}/approve", headers=moderator_headers)
    res = client.post(f"/moderation/{pending_id}/approve", headers=moderator_headers)
    assert res.status_code == 409
