VALID_BARCODE = "7891000100103"
OTHER_VALID_BARCODE = "7891000053508"


def new_product(client, auth, **fields):
    payload = {"name": "Cerveja Teste 350ml", "reason": "Cadastro de teste", **fields}
    response = client.post("/products", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def test_leitura_nao_exige_token(client):
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_escrita_exige_token(client):
    response = client.post("/products", json={"name": "X", "reason": "teste"})
    assert response.status_code == 401


def test_produto_sem_ncm_e_aceito(client, auth):
    product = new_product(client, auth)
    assert product["ncm"] is None


def test_ncm_fora_da_tabela_oficial_e_aceito_com_aviso(client, auth, ncm_table):
    product = new_product(client, auth, ncm="82055000")
    assert product["ncm"]["in_official_table"] is False


def test_busca_pelo_codigo_de_barras_traz_tudo(client, auth, ncm_table):
    new_product(client, auth, barcodes=[VALID_BARCODE], ncm="2203.00.00", manufacturer="Cervejaria X", manufacturer_code="CX-350")

    response = client.get(f"/barcode/{VALID_BARCODE}")
    assert response.status_code == 200
    product = response.json()
    assert product["barcodes"] == [VALID_BARCODE]
    assert product["ncm"]["description"] == "Cervejas de malte."
    assert product["manufacturer_code"] == "CX-350"


def test_codigo_de_barras_com_digito_errado_e_recusado(client, auth):
    response = client.post("/products", json={"name": "X", "barcodes": ["7891000100104"], "reason": "teste"}, headers=auth)
    assert response.status_code == 400


def test_codigo_de_barras_nao_pode_ser_de_dois_produtos(client, auth):
    new_product(client, auth, barcodes=[VALID_BARCODE])
    response = client.post("/products", json={"name": "Outro", "barcodes": [VALID_BARCODE], "reason": "teste"}, headers=auth)
    assert response.status_code == 400
    assert "já pertence" in response.json()["detail"]


def test_produto_sem_ncm_herda_da_categoria(client, auth, ncm_table):
    client.post("/categories", json={"path": "Bebidas", "ncm": "22030000", "reason": "NCM das bebidas"}, headers=auth)
    product = new_product(client, auth, category="Bebidas > Cervejas")

    assert product["category"]["path"] == "Bebidas > Cervejas"
    assert product["ncm"]["code"] == "22030000"
    assert product["fiscal_data_from_category"] == ["ncm_code"]


def test_ncm_do_produto_vale_mais_que_o_da_categoria(client, auth, ncm_table):
    client.post("/categories", json={"path": "Bebidas", "ncm": "22030000", "reason": "NCM das bebidas"}, headers=auth)
    product = new_product(client, auth, category="Bebidas", ncm="82075011")

    assert product["ncm"]["code"] == "82075011"
    assert product["fiscal_data_from_category"] == []


def test_busca_por_ncm_inclui_produto_que_herda_da_categoria(client, auth):
    client.post("/categories", json={"path": "Bebidas", "ncm": "22030000", "reason": "NCM das bebidas"}, headers=auth)
    new_product(client, auth, category="Bebidas")

    response = client.get("/products", params={"ncm": "22030000"})
    assert response.json()["total"] == 1


def test_busca_por_fabricante_e_texto(client, auth):
    new_product(client, auth, manufacturer="Tramontina", barcodes=[VALID_BARCODE])
    assert client.get("/products", params={"manufacturer": "tramon"}).json()["total"] == 1
    assert client.get("/products", params={"q": VALID_BARCODE}).json()["total"] == 1
    assert client.get("/products", params={"q": "inexistente"}).json()["total"] == 0


def test_edicao_grava_historico_so_do_que_mudou(client, auth):
    product = new_product(client, auth, brand="Antiga")

    response = client.put(
        f"/products/{product['id']}",
        json={"brand": "Nova", "name": product["name"], "barcodes": [OTHER_VALID_BARCODE], "reason": "Corrige marca"},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    assert sorted(response.json()["changed_fields"]) == ["barcodes", "brand"]

    revisions = client.get(f"/products/{product['id']}/revisions").json()["items"]
    brand_change = next(revision for revision in revisions if revision["field"] == "brand" and revision["action"] == "update")
    assert brand_change["old_value"] == "Antiga"
    assert brand_change["new_value"] == "Nova"
    assert brand_change["contributor"] == "testador"


def test_preco_medio_e_mediana(client, auth):
    product = new_product(client, auth)
    for price in (10.0, 12.0, 100.0):
        assert client.post(f"/products/{product['id']}/prices", json={"price": price, "uf": "SP"}, headers=auth).status_code == 201

    price = client.get(f"/products/{product['id']}").json()["price"]
    assert price == {"average": 40.67, "median": 12.0, "reports": 3, "period_in_months": 12}


def test_regras_fiscais_filtradas_por_uf_e_regime(client, auth, ncm_table):
    base_rule = {"ncm": "22030000", "valid_from": "2026-01-01", "source": "Teste", "reason": "teste"}
    client.post("/fiscal-rules", json={**base_rule, "icms_rate": 17}, headers=auth)
    client.post("/fiscal-rules", json={**base_rule, "uf": "SP", "icms_rate": 18}, headers=auth)
    client.post("/fiscal-rules", json={**base_rule, "uf": "RJ", "icms_rate": 20}, headers=auth)
    product = new_product(client, auth, ncm="22030000")

    rules_sp = client.get(f"/products/{product['id']}", params={"uf": "SP"}).json()["fiscal_rules"]
    assert [rule["icms_rate"] for rule in rules_sp] == [18, 17]

    all_rules = client.get(f"/products/{product['id']}").json()["fiscal_rules"]
    assert len(all_rules) == 3


def test_produtos_alterados_desde_uma_data(client, auth):
    new_product(client, auth)
    response = client.get("/products/changed", params={"since": "2000-01-01"})
    assert len(response.json()["items"]) == 1


def test_sql_injection_na_busca_nao_quebra_nada(client, auth):
    new_product(client, auth)
    response = client.get("/products", params={"q": "' OR 1=1; DROP TABLE products; --"})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert client.get("/products").json()["total"] == 1
