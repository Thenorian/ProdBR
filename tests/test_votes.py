from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from tests.conftest import register, set_user
from tests.test_moderation import make_product_payload

OLD = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)


@pytest.fixture(autouse=True)
def small_threshold(monkeypatch):
    monkeypatch.setattr(settings, "community_vote_threshold", 3)


def voter(client, name):
    key = register(client, name)
    set_user(name, created_at=OLD)
    return {"X-API-Key": key}


def propose(client, headers, **overrides):
    res = client.post("/products", json=make_product_payload(**overrides), headers=headers)
    assert res.status_code == 202, res.text
    return res.json()["pending_change_id"]


def test_enough_votes_apply_the_change(client, newbie_headers):
    pending_id = propose(client, newbie_headers, name="Aprovado pela comunidade")
    for i in range(2):
        res = client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=voter(client, f"voter{i}"))
        assert res.json()["status"] == "pending"
        assert res.json()["votes_for"] == i + 1
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=voter(client, "voter2"))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"
    found = client.get("/products", params={"q": "Aprovado pela comunidade"}).json()
    assert [p["name"] for p in found["items"]] == ["Aprovado pela comunidade"]


def test_score_is_net_and_negative_rejects(client, newbie_headers):
    pending_id = propose(client, newbie_headers)
    client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=voter(client, "alice"))
    for name in ("bruno", "carla", "diego"):
        client.post(f"/moderation/{pending_id}/vote", json={"value": -1}, headers=voter(client, name))
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": -1}, headers=voter(client, "elisa"))
    assert res.json()["votes_for"] == 1 and res.json()["votes_against"] == 4
    assert res.json()["status"] == "rejected"


def test_one_vote_per_user_can_change_or_withdraw(client, newbie_headers):
    pending_id = propose(client, newbie_headers)
    h = voter(client, "alice")
    client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=h)
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=h)
    assert res.json()["votes_for"] == 1
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": -1}, headers=h)
    assert (res.json()["votes_for"], res.json()["votes_against"], res.json()["my_vote"]) == (0, 1, -1)
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": 0}, headers=h)
    assert (res.json()["votes_against"], res.json()["my_vote"]) == (0, 0)


def test_author_and_new_accounts_cannot_vote(client, newbie_headers):
    set_user("newbie", created_at=OLD)
    pending_id = propose(client, newbie_headers)
    assert client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=newbie_headers).status_code == 403
    fresh = {"X-API-Key": register(client, "recem_criado")}
    assert client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=fresh).status_code == 403


def test_cannot_vote_on_decided_change(client, newbie_headers, moderator_headers):
    pending_id = propose(client, newbie_headers)
    client.post(f"/moderation/{pending_id}/approve", headers=moderator_headers)
    res = client.post(f"/moderation/{pending_id}/vote", json={"value": 1}, headers=voter(client, "alice"))
    assert res.status_code == 409
