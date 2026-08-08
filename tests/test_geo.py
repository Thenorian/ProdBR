def test_list_countries_empty_by_default(client):
    # Sem rodar scripts/seed_geo.py, a base de teste comeca vazia - so
    # confirma que a rota funciona e não quebra.
    res = client.get("/countries")
    assert res.status_code == 200
    assert res.json() == []


def test_list_states_for_seeded_country(client):
    from app.database import PublicSession
    from app.models_public import Country, State

    db = PublicSession()
    try:
        db.add(Country(id="BR", name="Brasil"))
        db.add(State(country_id="BR", code="SP", name="São Paulo"))
        db.add(State(country_id="BR", code="RJ", name="Rio de Janeiro"))
        db.commit()
    finally:
        db.close()

    countries = client.get("/countries").json()
    assert countries == [{"id": "BR", "name": "Brasil"}]

    states = client.get("/countries/BR/states").json()
    codes = {s["code"] for s in states}
    assert codes == {"SP", "RJ"}


def test_list_states_for_unknown_country_is_empty(client):
    res = client.get("/countries/ZZ/states")
    assert res.status_code == 200
    assert res.json() == []
