def test_fresh_install_has_mercosur_countries_states_and_taxes(client):
    countries = {c["id"]: c for c in client.get("/countries").json()}
    assert set(countries) == {"BR", "AR", "PY", "UY"}
    assert countries["AR"]["language"] == "es-AR" and countries["AR"]["subdivision_label"] == "Provincia"

    assert len(client.get("/countries/BR/states").json()) == 27
    assert {s["code"] for s in client.get("/countries/AR/states").json()} >= {"B", "C", "X"}
    assert len(client.get("/countries/UY/states").json()) == 19

    br_taxes = {t["code"]: t for t in client.get("/countries/BR/tax-types").json()}
    assert br_taxes["ICMS"]["column"] == "icms_rate" and br_taxes["ICMS"]["level"] == "state"
    ar_taxes = {t["code"]: t for t in client.get("/countries/AR/tax-types").json()}
    assert ar_taxes["IVA"]["default_rate"] == 21.0 and ar_taxes["IVA"]["translations"]["pt"].startswith("Imposto")


def test_seed_is_idempotent_and_keeps_admin_edits(client):
    from app.database import PublicSession
    from app.models_public import TaxType
    from app.reference_data import ensure_reference_data

    db = PublicSession()
    try:
        iva = db.query(TaxType).filter(TaxType.country_id == "AR", TaxType.code == "IVA").one()
        iva.default_rate = 10.5
        db.commit()
        assert ensure_reference_data(db) == {"countries": 0, "states": 0, "tax_types": 0}
        db.refresh(iva)
        assert iva.default_rate == 10.5
    finally:
        db.close()


def test_list_states_for_unknown_country_is_empty(client):
    res = client.get("/countries/ZZ/states")
    assert res.status_code == 200
    assert res.json() == []
