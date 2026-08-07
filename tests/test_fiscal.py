def make_fiscal_payload(**overrides):
    payload = {
        "ncm": "22030000",
        "uf": None,
        "origin": 0,
        "icms_rate": 18.0,
        "ipi_rate": 6.0,
        "valid_from": "2024-01-01",
        "source": "Receita Federal",
        "reason": "Carga inicial",
    }
    payload.update(overrides)
    return payload


def test_create_and_resolve_national_rule(client, trusted_headers):
    res = client.post("/fiscal-rules", json=make_fiscal_payload(), headers=trusted_headers)
    assert res.status_code == 201

    lookup = client.get("/fiscal-rules", params={"ncm": "22030000"})
    assert lookup.status_code == 200
    assert lookup.json()["icms_rate"] == 18.0


def test_uf_specific_rule_takes_priority_over_national(client, trusted_headers):
    client.post("/fiscal-rules", json=make_fiscal_payload(icms_rate=18.0), headers=trusted_headers)
    client.post(
        "/fiscal-rules",
        json=make_fiscal_payload(uf="SP", icms_rate=12.0),
        headers=trusted_headers,
    )

    national = client.get("/fiscal-rules", params={"ncm": "22030000", "uf": "RJ"})
    assert national.json()["icms_rate"] == 18.0

    sp = client.get("/fiscal-rules", params={"ncm": "22030000", "uf": "SP"})
    assert sp.json()["icms_rate"] == 12.0


def test_no_matching_rule_returns_404(client):
    res = client.get("/fiscal-rules", params={"ncm": "99999999"})
    assert res.status_code == 404


def test_product_fiscal_endpoint_resolves_via_product_ncm(client, trusted_headers):
    client.post("/fiscal-rules", json=make_fiscal_payload(), headers=trusted_headers)
    product = client.post(
        "/products",
        json={
            "name": "Cerveja",
            "ncm": "22030000",
            "source": "teste",
            "reason": "criacao",
        },
        headers=trusted_headers,
    ).json()

    res = client.get(f"/products/{product['id']}/fiscal")
    assert res.status_code == 200
    assert res.json()["ncm"] == "22030000"


def test_default_country_is_br(client, trusted_headers):
    client.post("/fiscal-rules", json=make_fiscal_payload(), headers=trusted_headers)
    rule = client.get("/fiscal-rules", params={"ncm": "22030000"}).json()
    assert rule["country"] == "BR"


def test_country_scoped_rules_do_not_leak_across_countries(client, trusted_headers):
    client.post("/fiscal-rules", json=make_fiscal_payload(icms_rate=18.0, country="BR"), headers=trusted_headers)
    client.post(
        "/fiscal-rules",
        json=make_fiscal_payload(icms_rate=21.0, country="AR", uf=None),
        headers=trusted_headers,
    )

    br = client.get("/fiscal-rules", params={"ncm": "22030000", "country": "BR"})
    assert br.json()["icms_rate"] == 18.0

    ar = client.get("/fiscal-rules", params={"ncm": "22030000", "country": "AR"})
    assert ar.json()["icms_rate"] == 21.0


def test_new_tax_fields_round_trip(client, trusted_headers):
    res = client.post(
        "/fiscal-rules",
        json=make_fiscal_payload(ii_rate=20.0, fcp_rate=2.0, icms_st_mva_rate=40.0, notes="Regime monofasico"),
        headers=trusted_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["ii_rate"] == 20.0
    assert body["fcp_rate"] == 2.0
    assert body["icms_st_mva_rate"] == 40.0
    assert body["notes"] == "Regime monofasico"


def test_products_with_same_ncm_share_fiscal_rule(client, trusted_headers):
    """Nao duplica dado fiscal: dois produtos com o mesmo NCM resolvem
    para a mesma regra, sem precisar cadastrar a regra duas vezes."""
    client.post("/fiscal-rules", json=make_fiscal_payload(), headers=trusted_headers)
    p1 = client.post(
        "/products",
        json={"name": "Produto A", "ncm": "22030000", "source": "t", "reason": "cad"},
        headers=trusted_headers,
    ).json()
    p2 = client.post(
        "/products",
        json={"name": "Produto B", "ncm": "22030000", "source": "t", "reason": "cad"},
        headers=trusted_headers,
    ).json()

    fiscal_1 = client.get(f"/products/{p1['id']}/fiscal").json()
    fiscal_2 = client.get(f"/products/{p2['id']}/fiscal").json()
    assert fiscal_1["id"] == fiscal_2["id"]
