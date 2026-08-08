from app.database import PublicSession


def make_ncm_payload(**overrides):
    payload = {
        "ncm": "22030000",
        "description": "Cervejas de malte",
        "chapter": "22",
        "unit": "L",
        "source": "TIPI",
        "reason": "Carga inicial",
    }
    payload.update(overrides)
    return payload


def test_search_empty(client):
    res = client.get("/ncm")
    assert res.status_code == 200
    assert res.json() == []


def test_create_requires_auth(client):
    res = client.post("/ncm", json=make_ncm_payload())
    assert res.status_code == 401


def test_create_and_get_ncm(client, trusted_headers):
    res = client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    assert res.status_code == 201, res.text

    detail = client.get("/ncm/22030000")
    assert detail.status_code == 200
    body = detail.json()
    assert body["description"] == "Cervejas de malte"
    assert body["product_count"] == 0
    assert body["fiscal_rules"] == []


def test_duplicate_ncm_rejected(client, trusted_headers):
    client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    res = client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    assert res.status_code == 400


def test_get_unknown_ncm_returns_404(client):
    res = client.get("/ncm/99999999")
    assert res.status_code == 404


def test_search_by_description(client, trusted_headers):
    client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    res = client.get("/ncm", params={"q": "cerveja"})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_ncm_detail_reports_product_count_and_fiscal_rules(client, trusted_headers):
    client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    client.post(
        "/products",
        json={"name": "Cerveja", "ncm": "22030000", "source": "teste", "reason": "criacao"},
        headers=trusted_headers,
    )
    client.post(
        "/fiscal-rules",
        json={
            "ncm": "22030000",
            "icms_rate": 18.0,
            "ii_rate": 20.0,
            "valid_from": "2024-01-01",
            "source": "Receita Federal",
            "reason": "Carga inicial",
        },
        headers=trusted_headers,
    )

    detail = client.get("/ncm/22030000").json()
    assert detail["product_count"] == 1
    assert len(detail["fiscal_rules"]) == 1
    assert detail["fiscal_rules"][0]["country"] == "BR"
    assert detail["fiscal_rules"][0]["ii_rate"] == 20.0


def test_update_ncm_requires_reason(client, trusted_headers):
    client.post("/ncm", json=make_ncm_payload(), headers=trusted_headers)
    res = client.put(
        "/ncm/22030000",
        json={"description": "Cervejas de malte, em embalagens retornaveis", "reason": "Ajuste de texto"},
        headers=trusted_headers,
    )
    assert res.status_code == 200
    assert res.json()["description"] == "Cervejas de malte, em embalagens retornaveis"


def test_ncm_category_shared_with_products(client, trusted_headers):
    client.post("/ncm", json=make_ncm_payload(category="Bebidas"), headers=trusted_headers)
    detail = client.get("/ncm/22030000").json()
    assert detail["category"] == "Bebidas"

    client.post(
        "/products",
        json={"name": "Cerveja", "ncm": "22030000", "category": "Bebidas", "source": "t", "reason": "criacao"},
        headers=trusted_headers,
    )

    db = PublicSession()
    try:
        from app.models_public import Category

        assert db.query(Category).filter(Category.name == "Bebidas").count() == 1
    finally:
        db.close()
