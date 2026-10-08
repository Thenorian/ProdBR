from tests.conftest import set_user


def make_product(client, headers):
    res = client.post(
        "/products",
        json={"name": "Special Dog Vegetais Adultos", "ncm": "23091000", "source": "Fabricante", "reason": "Teste"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_identifier_description_is_parsed(client, moderator_headers):
    product_id = make_product(client, moderator_headers)
    res = client.post(
        "/identifiers",
        json={"product_id": product_id, "type": "gtin13", "value": "7898242031936", "description": "1 kg", "reason": "Teste"},
        headers=moderator_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["description"], body["net_quantity"], body["net_unit"]) == ("1 kg", 1.0, "kg")

    product = client.get(f"/products/{product_id}").json()
    assert product["identifiers"][0]["description"] == "1 kg"


def test_explicit_fields_win_and_unsure_text_stays_raw(client, moderator_headers):
    product_id = make_product(client, moderator_headers)
    res = client.post(
        "/identifiers",
        json={"product_id": product_id, "type": "gtin13", "value": "7898242031943", "description": "Embalagem economica", "reason": "Teste"},
        headers=moderator_headers,
    )
    assert res.json()["net_quantity"] is None and res.json()["description"] == "Embalagem economica"
    identifier_id = res.json()["id"]
    res = client.put(
        f"/identifiers/{identifier_id}",
        json={"net_quantity": 3, "net_unit": "KG", "reason": "Completa a medida"},
        headers=moderator_headers,
    )
    assert res.status_code == 200, res.text
    assert (res.json()["net_quantity"], res.json()["net_unit"]) == (3.0, "kg")


def test_invalid_unit_is_rejected(client, moderator_headers):
    product_id = make_product(client, moderator_headers)
    res = client.post(
        "/identifiers",
        json={"product_id": product_id, "type": "gtin13", "value": "7898242031950", "net_quantity": 1, "net_unit": "barril", "reason": "Teste"},
        headers=moderator_headers,
    )
    assert res.status_code == 400


def test_hall_of_fame_ranks_by_edits(client, newbie_headers, moderator_headers):
    set_user("newbie", edit_count=5)
    set_user("mod_user", edit_count=12)
    ranking = client.get("/hall-of-fame").json()
    assert [(p["rank"], p["username"]) for p in ranking] == [(1, "mod_user"), (2, "newbie")]
    assert client.get("/hall-da-fama").status_code == 200
