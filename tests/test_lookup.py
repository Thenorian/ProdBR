from app.database import PublicSession
from app.models_public import NcmClassification


def _ncm(code="23091000", description="Alimentos para cães ou gatos"):
    db = PublicSession()
    try:
        db.add(NcmClassification(ncm=code, description=description, chapter=code[:2], source="teste"))
        db.commit()
    finally:
        db.close()


def _rule(client, headers, **fields):
    payload = {"ncm": "23091000", "valid_from": "2026-01-01", "source": "teste", "reason": "Cadastro de teste", **fields}
    res = client.post("/fiscal-rules", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_brazil_lookup_merges_state_and_national_with_translation(client, trusted_headers):
    _ncm()
    _rule(client, trusted_headers, ipi_rate=6.5, ii_rate=12.6, source="TIPI")
    # Tudo por codigo em `rates`: ICMS vai pra coluna propria sozinho.
    _rule(client, trusted_headers, uf="SP", rates={"ICMS": 18, "FCP": 0}, source="RICMS/SP")

    res = client.get("/v1/BR/SP/23091000")
    assert res.status_code == 200, res.text
    body = res.json()
    taxes = {t["code"]: t for t in body["taxes"]}
    assert body["state"] == {"code": "SP", "name": "São Paulo"} and body["lang"] == "pt"
    assert (taxes["ICMS"]["rate"], taxes["IPI"]["rate"], taxes["II"]["rate"]) == (18.0, 6.5, 12.6)
    assert taxes["PIS"]["rate"] is None  # existe, mas ainda sem dado
    assert taxes["ICMS"]["name"] == "Imposto sobre Circulação de Mercadorias e Serviços"
    assert body["sources"] == ["RICMS/SP", "TIPI"]

    en = {t["code"]: t for t in client.get("/v1/BR/SP/23091000?lang=en").json()["taxes"]}
    assert en["ICMS"]["name"].startswith("Tax on the Circulation") and en["ICMS"]["local_name"].startswith("Imposto")

    national = {t["code"]: t["rate"] for t in client.get("/v1/br/23091000").json()["taxes"]}
    assert national["ICMS"] is None and national["IPI"] == 6.5


def test_argentina_uses_general_rate_then_specific_rule(client, trusted_headers):
    _ncm()
    body = client.get("/v1/AR/B/2309.10.00").json()
    taxes = {t["code"]: t for t in body["taxes"]}
    assert body["lang"] == "es" and body["state"]["name"] == "Buenos Aires"
    assert taxes["IVA"]["rate"] == 21.0 and taxes["IVA"]["general_rate"] is True
    assert taxes["IVA"]["name"] == "Impuesto al Valor Agregado"
    assert taxes["IIBB"]["rate"] is None

    _rule(client, trusted_headers, country="AR", rates={"IVA": 10.5}, source="Ley 23.349 art. 28")
    # Como o formulario manda: campo vazio = null.
    _rule(client, trusted_headers, country="AR", uf="B", rates={"IVA": None, "IIBB": 3.5, "DI": None}, source="Código Fiscal PBA")
    taxes = {t["code"]: t for t in client.get("/v1/AR/B/23091000?lang=pt").json()["taxes"]}
    assert (taxes["IVA"]["rate"], taxes["IVA"]["general_rate"]) == (10.5, False)
    assert taxes["IIBB"]["rate"] == 3.5
    assert taxes["IVA"]["name"] == "Imposto sobre o Valor Agregado"


def test_lookup_by_barcode_returns_product(client, trusted_headers):
    _ncm()
    _rule(client, trusted_headers, ipi_rate=6.5)
    product = client.post(
        "/products", json={"name": "Ração Teste 15kg", "ncm": "23091000", "source": "t", "reason": "cad"}, headers=trusted_headers
    ).json()
    res = client.post(
        "/identifiers",
        json={"product_id": product["id"], "type": "GTIN-13", "value": "7898242031936", "description": "Saco 15 kg", "reason": "cad"},
        headers=trusted_headers,
    )
    assert res.status_code == 201, res.text

    body = client.get("/v1/BR/SP/7898242031936").json()
    assert body["product"]["name"] == "Ração Teste 15kg" and body["product"]["package"] == "Saco 15 kg"
    assert body["ncm"] == "23091000"


def test_lookup_errors(client):
    _ncm()
    assert client.get("/v1/ZZ/23091000").status_code == 404
    res = client.get("/v1/AR/ZZ/23091000")
    assert res.status_code == 404 and "Provincia" in res.json()["detail"]
    assert client.get("/v1/BR/99999999").status_code == 404


def test_invalid_rates_rejected(client, trusted_headers):
    _ncm()
    res = client.post(
        "/fiscal-rules",
        json={"ncm": "23091000", "country": "AR", "rates": {"ICMS": 18}, "valid_from": "2026-01-01", "source": "t", "reason": "teste"},
        headers=trusted_headers,
    )
    assert res.status_code == 400 and "IVA" in res.json()["detail"]
    res = client.post(
        "/fiscal-rules",
        json={"ncm": "23091000", "country": "BR", "uf": "XX", "valid_from": "2026-01-01", "source": "t", "reason": "teste"},
        headers=trusted_headers,
    )
    assert res.status_code == 400
    res = client.post(
        "/fiscal-rules",
        json={"ncm": "23091000", "country": "CL", "valid_from": "2026-01-01", "source": "t", "reason": "teste"},
        headers=trusted_headers,
    )
    assert res.status_code == 400 and "/countries" in res.json()["detail"]


def test_admin_adds_new_country_with_its_taxes(client, admin_headers, trusted_headers):
    _ncm()
    res = client.post(
        "/admin/countries",
        json={"id": "cl", "name": "Chile", "language": "es-CL", "subdivision_label": "Región"},
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    assert client.post("/admin/countries/CL/states", json={"code": "RM", "name": "Metropolitana"}, headers=admin_headers).status_code == 201
    res = client.post(
        "/admin/tax-types",
        json={
            "country_id": "CL",
            "code": "iva",
            "name": "Impuesto al Valor Agregado",
            "translations": {"pt": "Imposto sobre o Valor Agregado", "en": "Value Added Tax"},
            "default_rate": 19,
            "default_source": "DL 825",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    tax_id = res.json()["id"]

    taxes = client.get("/v1/CL/RM/23091000?lang=en").json()["taxes"]
    assert taxes == [
        {
            "code": "IVA",
            "name": "Value Added Tax",
            "local_name": "Impuesto al Valor Agregado",
            "level": "national",
            "unit": "percent",
            "rate": 19.0,
            "general_rate": True,
            "source": "DL 825",
            "description": None,
        }
    ]

    # Desativar some da consulta; editar traducao vale na hora.
    assert client.put(f"/admin/tax-types/{tax_id}", json={"active": False}, headers=admin_headers).status_code == 200
    assert client.get("/v1/CL/23091000").json()["taxes"] == []
    assert client.get("/v1/CL").json()["states"] == [{"code": "RM", "name": "Metropolitana"}]


def test_admin_routes_need_admin(client, trusted_headers, moderator_headers):
    payload = {"id": "CL", "name": "Chile"}
    assert client.post("/admin/countries", json=payload, headers=trusted_headers).status_code == 403
    assert client.post("/admin/countries", json=payload, headers=moderator_headers).status_code == 403
    assert client.post("/admin/countries", json=payload).status_code in (401, 403)
