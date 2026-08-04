def make_payload(barcode="7891149100104", ncm="22030000"):
    return {
        "ncm": ncm,
        "description": "Cerveja em garrafa de vidro, 600ml",
        "unit": "UN",
        "origin": 0,
        "icms_rate": 18.0,
        "ipi_rate": 6.0,
        "barcodes": [barcode],
    }


def test_search_empty(client):
    res = client.get("/products")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_create_requires_api_key(client):
    res = client.post("/products", json=make_payload())
    assert res.status_code == 401


def test_create_and_search_by_barcode(client, api_key_header):
    res = client.post("/products", json=make_payload(), headers=api_key_header)
    assert res.status_code == 201
    product_id = res.json()["id"]

    res = client.get("/products", params={"barcode": "7891149100104"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == product_id
    assert body["items"][0]["barcodes"] == ["7891149100104"]


def test_create_duplicate_barcode_conflicts(client, api_key_header):
    client.post("/products", json=make_payload(barcode="123", ncm="22030000"), headers=api_key_header)
    res = client.post("/products", json=make_payload(barcode="123", ncm="19059090"), headers=api_key_header)
    assert res.status_code == 409


def test_update_records_changelog(client, api_key_header):
    res = client.post("/products", json=make_payload(), headers=api_key_header)
    product_id = res.json()["id"]

    res = client.put(
        f"/products/{product_id}",
        json={"icms_rate": 12.0},
        headers=api_key_header,
    )
    assert res.status_code == 200
    assert res.json()["icms_rate"] == 12.0

    res = client.get(f"/products/{product_id}/changelog")
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 2  # create + update
    assert entries[0]["action"] == "update"  # mais recente primeiro
    assert entries[0]["diff"]["before"]["icms_rate"] == 18.0
    assert entries[0]["diff"]["after"]["icms_rate"] == 12.0


def test_update_without_api_key_rejected(client, api_key_header):
    res = client.post("/products", json=make_payload(), headers=api_key_header)
    product_id = res.json()["id"]

    res = client.put(f"/products/{product_id}", json={"icms_rate": 1.0})
    assert res.status_code == 401


def test_search_page_size_is_capped(client, api_key_header):
    for i in range(12):
        payload = make_payload(barcode=f"barcode-{i}", ncm="22030000")
        client.post("/products", json=payload, headers=api_key_header)

    res = client.get("/products", params={"ncm": "22030000", "limit": 100})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 12
    assert body["limit"] == 10
    assert len(body["items"]) == 10


def test_get_product_not_found(client):
    res = client.get("/products/999")
    assert res.status_code == 404
