"""Preço de venda: só entra quando muda, ficam os 100 mais novos e o gráfico usa esses."""
from api import rate_limit
from database.product import ProductDB
from tests.conftest import create_contributor

BARCODE = "7891000100103"


def new_product(client, auth):
    response = client.post("/products", json={"name": "Café", "barcodes": [BARCODE], "reason": "teste"}, headers=auth)
    return response.json()


def send_price(client, product, auth, **report):
    return client.post(f"/products/{product['id']}/prices", json={"uf": "SP", **report}, headers=auth)


def make_reports_old(product):
    """Simula que os informes foram feitos há dias (fora da janela de correção de 1 hora)."""
    ProductDB().run_sql(
        "UPDATE price_reports SET reported_at = datetime(reported_at, '-2 days') WHERE product_id = ?",
        (product["id"],), fetch="rowcount",
    )


def test_mesmo_preco_nao_grava_de_novo(client, auth):
    product = new_product(client, auth)
    assert send_price(client, product, auth, price=10).json()["recorded"] == "created"
    make_reports_old(product)
    assert send_price(client, product, auth, price=10).json()["recorded"] == "unchanged"
    assert len(client.get(f"/products/{product['id']}/prices").json()["items"]) == 1


def test_preco_novo_dentro_de_uma_hora_corrige_o_anterior(client, auth):
    product = new_product(client, auth)
    send_price(client, product, auth, price=10)
    assert send_price(client, product, auth, price=11).json()["recorded"] == "corrected"
    items = client.get(f"/products/{product['id']}/prices").json()["items"]
    assert [item["price"] for item in items] == [11.0]


def test_preco_que_mudou_depois_vira_ponto_novo(client, auth):
    product = new_product(client, auth)
    send_price(client, product, auth, price=10)
    make_reports_old(product)
    assert send_price(client, product, auth, price=12.5).json()["recorded"] == "created"

    history = client.get(f"/products/{product['id']}/prices").json()
    assert [item["price"] for item in history["items"]] == [10.0, 12.5]
    assert history["summary"]["last"] == 12.5
    assert history["summary"]["minimum"] == 10.0
    assert history["summary"]["maximum"] == 12.5


def test_guarda_so_os_100_mais_novos(client, auth):
    product = new_product(client, auth)
    for cents in range(1000, 1105):
        rate_limit.request_times_by_key.clear()  # o limite de 20 escritas por minuto não é o que está sendo testado
        assert send_price(client, product, auth, price=cents / 100).status_code == 201
        make_reports_old(product)

    items = client.get(f"/products/{product['id']}/prices").json()["items"]
    assert len(items) == 100
    assert items[0]["price"] == 10.05
    assert items[-1]["price"] == 11.04


def test_promocao_fica_fora_do_preco_base(client, auth):
    product = new_product(client, auth)
    send_price(client, product, auth, price=20)
    other_store = {"X-API-Key": create_contributor(client, "outra_loja")}
    send_price(client, product, other_store, price=5, is_promotion=True)

    summary = client.get(f"/products/{product['id']}").json()["price"]
    assert summary["base_sale_price"] == 20.0
    assert summary["last"] == 5.0
    assert summary["last_is_promotion"] is True


def test_dados_do_informe_cidade_e_embalagem(client, auth):
    product = new_product(client, auth)
    response = send_price(client, product, auth, price=9.9, city="  Campinas ", barcode=BARCODE)
    assert response.json()["city"] == "Campinas"

    item = client.get(f"/products/{product['id']}/prices").json()["items"][0]
    assert item == {
        "price": 9.9, "uf": "SP", "city": "Campinas", "barcode": BARCODE, "is_promotion": False,
        "contributor": "testador", "reported_at": item["reported_at"],
    }


def test_embalagem_de_outro_produto_e_uf_invalida_sao_recusadas(client, auth):
    product = new_product(client, auth)
    assert send_price(client, product, auth, price=9.9, barcode="7896004000008").status_code == 400
    assert send_price(client, product, auth, price=9.9, uf="XX").status_code == 400


def test_filtro_por_uf(client, auth):
    product = new_product(client, auth)
    send_price(client, product, auth, price=10)
    send_price(client, product, auth, price=15, uf="RJ")
    items = client.get(f"/products/{product['id']}/prices", params={"uf": "RJ"}).json()["items"]
    assert [item["price"] for item in items] == [15.0]
