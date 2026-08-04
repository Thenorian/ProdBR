from datetime import datetime

from app.database import PublicSession
from app.models_public import Product


def make_product_payload(**overrides):
    payload = {
        "name": "Cerveja em garrafa de vidro, 600ml",
        "brand": "Exemplo",
        "ncm": "22030000",
        "commercial_unit": "UN",
        "source": "Contribuicao da comunidade",
        "reason": "Cadastro inicial",
    }
    payload.update(overrides)
    return payload


def test_search_empty(client):
    res = client.get("/products")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_create_requires_auth(client):
    res = client.post("/products", json=make_product_payload())
    assert res.status_code == 401


def test_trusted_user_create_applies_immediately(client, trusted_headers):
    res = client.post("/products", json=make_product_payload(), headers=trusted_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Cerveja em garrafa de vidro, 600ml"
    assert body["id"].startswith("prod_")


def test_newbie_create_goes_to_moderation_queue(client, newbie_headers):
    res = client.post("/products", json=make_product_payload(), headers=newbie_headers)
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending"

    # nao deve aparecer na base publica ainda
    search = client.get("/products", params={"ncm": "22030000"})
    assert search.json()["total"] == 0


def test_update_records_one_revision_per_field(client, trusted_headers):
    create = client.post("/products", json=make_product_payload(), headers=trusted_headers)
    product_id = create.json()["id"]

    res = client.put(
        f"/products/{product_id}",
        json={"brand": "Nova Marca", "commercial_unit": "CX", "reason": "correcao de cadastro"},
        headers=trusted_headers,
    )
    assert res.status_code == 200
    assert res.json()["brand"] == "Nova Marca"

    revisions = client.get(f"/products/{product_id}/revisions").json()
    fields_changed = {r["field"] for r in revisions if r["action"] == "update"}
    assert fields_changed == {"brand", "commercial_unit"}
    for r in revisions:
        if r["action"] == "update":
            assert r["reason"] == "correcao de cadastro"
            assert r["contributor"] == "trusted_user"


def test_create_and_search_by_identifier(client, trusted_headers):
    create = client.post("/products", json=make_product_payload(), headers=trusted_headers)
    product_id = create.json()["id"]

    res = client.post(
        "/identifiers",
        json={
            "product_id": product_id,
            "type": "gtin13",
            "value": "7891149100104",
            "reason": "codigo de barras da embalagem",
        },
        headers=trusted_headers,
    )
    assert res.status_code == 201

    search = client.get("/products", params={"identifier": "7891149100104"})
    assert search.status_code == 200
    body = search.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == product_id


def test_duplicate_identifier_conflicts(client, trusted_headers):
    p1 = client.post("/products", json=make_product_payload(), headers=trusted_headers).json()["id"]
    p2 = client.post(
        "/products", json=make_product_payload(ncm="19059090"), headers=trusted_headers
    ).json()["id"]

    client.post(
        "/identifiers",
        json={"product_id": p1, "type": "gtin13", "value": "123", "reason": "teste"},
        headers=trusted_headers,
    )
    res = client.post(
        "/identifiers",
        json={"product_id": p2, "type": "gtin13", "value": "123", "reason": "teste"},
        headers=trusted_headers,
    )
    assert res.status_code == 400


def test_search_page_size_is_capped(client, trusted_headers):
    for i in range(12):
        client.post(
            "/products",
            json=make_product_payload(name=f"Produto {i}"),
            headers=trusted_headers,
        )

    res = client.get("/products", params={"ncm": "22030000", "limit": 100})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 12
    assert body["limit"] == 10
    assert len(body["items"]) == 10


def test_recent_sort_pagination_is_stable_with_tied_created_at(client, trusted_headers):
    """Import em lote grava tudo com o mesmo created_at - paginacao por
    offset precisa de um desempate estavel (Product.id) pra nao pular ou
    repetir produtos entre paginas."""
    ids = []
    for i in range(15):
        res = client.post(
            "/products",
            json=make_product_payload(name=f"Produto Recente {i}"),
            headers=trusted_headers,
        )
        ids.append(res.json()["id"])

    db = PublicSession()
    try:
        db.query(Product).filter(Product.id.in_(ids)).update(
            {"created_at": datetime(2026, 1, 1)}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

    seen = []
    for offset in (0, 10):
        res = client.get("/products", params={"sort": "recent", "limit": 10, "offset": offset})
        seen.extend(item["id"] for item in res.json()["items"])

    assert len(seen) == len(set(seen)), "paginacao repetiu produtos entre paginas"
    assert set(ids) <= set(seen), "paginacao pulou produtos"


def test_get_product_not_found(client):
    res = client.get("/products/prod_doesnotexist")
    assert res.status_code == 404
