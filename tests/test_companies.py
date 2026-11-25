"""Perfil de empresa no estilo Wikipedia, com os produtos dela listados."""
from tests.conftest import create_contributor

NESTLE = {"name": "Nestlé", "cnpj": "60.409.075/0001-52", "uf": "sp", "brands": ["Nescau", "Ninho", "nescau"], "reason": "Empresa nova"}


def new_company(client, auth, **changes):
    response = client.post("/companies", json={**NESTLE, **changes}, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def new_product(client, auth, **fields):
    response = client.post("/products", json={"reason": "teste", **fields}, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def test_cadastra_empresa_so_com_o_nome(client, auth):
    company = new_company(client, auth, cnpj=None, uf=None, brands=None)
    assert company["name"] == "Nestlé"
    assert company["cnpj"] is None
    assert company["brands"] == []


def test_cadastro_limpa_cnpj_uf_e_marcas_repetidas(client, auth):
    company = new_company(client, auth)
    assert company["cnpj"] == "60409075000152"
    assert company["uf"] == "SP"
    assert company["brands"] == ["Nescau", "Ninho"]


def test_cnpj_invalido_ou_repetido_e_recusado(client, auth):
    assert client.post("/companies", json={**NESTLE, "cnpj": "60.409.075/0001-53"}, headers=auth).status_code == 400
    new_company(client, auth)
    response = client.post("/companies", json={**NESTLE, "name": "Outra"}, headers=auth)
    assert response.status_code == 400
    assert "Nestlé" in response.json()["detail"]


def test_site_que_nao_e_http_e_recusado(client, auth):
    response = client.post("/companies", json={**NESTLE, "website": "javascript:alert(1)"}, headers=auth)
    assert response.status_code == 400


def test_produtos_aparecem_pela_marca_pelo_fabricante_e_pelo_vinculo(client, auth):
    company = new_company(client, auth)
    other = new_company(client, auth, name="Outra Empresa", cnpj=None, brands=["Outra Marca"])

    by_brand = new_product(client, auth, name="Achocolatado", brand="NESCAU")
    by_manufacturer = new_product(client, auth, name="Biscoito", manufacturer="nestlé")
    linked = new_product(client, auth, name="Água", brand="Outra Marca", company_id=company["id"])
    new_product(client, auth, name="Produto de outra", brand="Outra Marca")

    listed = client.get(f"/companies/{company['id']}/products").json()
    assert sorted(item["name"] for item in listed["items"]) == ["Achocolatado", "Biscoito", "Água"]
    assert client.get(f"/companies/{company['id']}").json()["product_count"] == 3
    assert client.get(f"/companies/{other['id']}").json()["product_count"] == 1

    assert client.get(f"/products/{by_brand['id']}").json()["company"]["linked_by"] == "brand"
    assert client.get(f"/products/{by_manufacturer['id']}").json()["company"]["linked_by"] == "manufacturer"
    assert client.get(f"/products/{linked['id']}").json()["company"] == {
        "id": company["id"], "name": "Nestlé", "cnpj": "60409075000152", "linked_by": "company_id",
    }


def test_produto_com_empresa_que_nao_existe_e_recusado(client, auth):
    response = client.post("/products", json={"name": "X", "company_id": "nao-existe", "reason": "teste"}, headers=auth)
    assert response.status_code == 400


def test_edicao_grava_historico_e_troca_as_marcas(client, auth):
    company = new_company(client, auth)
    response = client.put(
        f"/companies/{company['id']}", json={"city": "São Paulo", "brands": ["Ninho", "Moça"], "reason": "completa"}, headers=auth
    )
    assert sorted(response.json()["changed_fields"]) == ["brands", "city"]
    assert response.json()["company"]["brands"] == ["Moça", "Ninho"]

    history = client.get(f"/companies/{company['id']}/revisions").json()["items"]
    assert {revision["field"] for revision in history} >= {"name", "city", "brands"}


def test_busca_por_nome_cnpj_e_marca(client, auth):
    company = new_company(client, auth)
    for text in ("nest", "60409075000152", "60.409.075/0001-52", "Ninho"):
        found = client.get("/companies", params={"q": text}).json()
        assert [item["id"] for item in found["items"]] == [company["id"]], text
    assert client.get("/companies", params={"q": "inexistente"}).json()["total"] == 0


def test_iniciante_manda_empresa_para_a_votacao(client, beginner_auth):
    response = client.post("/companies", json=NESTLE, headers=beginner_auth)
    assert response.status_code == 202
    pending_change_id = response.json()["pending_change"]["id"]
    assert client.get("/companies").json()["total"] == 0

    moderator = {"X-API-Key": create_contributor(client, "moderador", moderator=True)}
    decided = client.post(f"/pending-changes/{pending_change_id}/votes", json={"vote": 1}, headers=moderator).json()
    assert decided["status"] == "approved"
    assert client.get("/companies").json()["items"][0]["name"] == "Nestlé"


def test_sql_injection_na_busca_de_empresa_nao_quebra_nada(client, auth):
    new_company(client, auth)
    response = client.get("/companies", params={"q": "'; DROP TABLE companies; --"})
    assert response.status_code == 200
    assert client.get("/companies").json()["total"] == 1


def test_rotas_da_empresa_pelo_cnpj(client, auth):
    company = new_company(client, auth)
    for cnpj in ("60409075000152", "60.409.075.0001-52"):
        assert client.get(f"/companies/{cnpj}").json()["id"] == company["id"], cnpj
    assert client.get(f"/companies/{company['id']}").status_code == 200
    assert client.get("/companies/60409075000152/products").status_code == 200
    assert client.get("/companies/60409075000152/revisions").json()["total"] > 0
    assert client.get("/companies/11222333000181").status_code == 404

    response = client.put("/companies/60409075000152", json={"city": "Vevey", "reason": "cidade"}, headers=auth)
    assert response.json()["company"]["city"] == "Vevey"


def test_cnpj_alfanumerico(client, auth):
    company = new_company(client, auth, name="Empresa Nova", cnpj="12.ABC.345/01DE-35", brands=None)
    assert company["cnpj"] == "12ABC34501DE35"
    assert client.get("/companies/12abc34501de35").json()["id"] == company["id"]
    assert client.get("/companies", params={"q": "12.ABC.345/01DE-35"}).json()["total"] == 1
    assert client.post("/companies", json={**NESTLE, "name": "X", "cnpj": "12ABC34501DE36"}, headers=auth).status_code == 400


def test_produto_aponta_para_a_empresa_pelo_cnpj(client, auth):
    company = new_company(client, auth)
    product = new_product(client, auth, name="Água", company_id="60.409.075/0001-52")
    assert client.get(f"/products/{product['id']}").json()["company"] == {
        "id": company["id"], "name": "Nestlé", "cnpj": "60409075000152", "linked_by": "company_id",
    }
