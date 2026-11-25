import urllib.parse

import pytest
from fastapi.testclient import TestClient

from website import main as website_main


@pytest.fixture
def site(client, monkeypatch):
    """O site busca os dados na API por HTTP. No teste, a chamada vai direto para a API de teste."""
    def get_from_test_api(path_parts, params=None):
        path = "/" + "/".join(urllib.parse.quote(str(part), safe="") for part in path_parts)
        response = client.get(path, params={key: value for key, value in (params or {}).items() if value not in (None, "")})
        return response.status_code, response.json()

    monkeypatch.setattr(website_main, "get_from_api", get_from_test_api)
    website_main.sitemap_cache["xml"] = None
    return TestClient(website_main.app)


def new_product(client, auth, name="Café Torrado 500g"):
    response = client.post("/products", json={"name": name, "barcodes": ["7891000100103"], "reason": "teste"}, headers=auth)
    return response.json()


def test_home_abre(site):
    response = site.get("/")
    assert response.status_code == 200
    assert "ProdBR" in response.text


def test_pagina_do_produto_ja_vem_com_os_dados_no_html(site, client, auth):
    product = new_product(client, auth)
    response = site.get(f"/produto/{product['id']}")
    assert response.status_code == 200
    assert "Café Torrado 500g" in response.text
    assert "7891000100103" in response.text
    assert "application/ld+json" in response.text


def test_nome_com_html_sai_escapado(site, client, auth):
    product = new_product(client, auth, name="<script>alert(1)</script>")
    page = site.get(f"/produto/{product['id']}").text
    assert "<script>alert(1)</script>" not in page


def test_produto_inexistente_da_404(site):
    assert site.get("/produto/nao-existe").status_code == 404


def test_busca(site, client, auth):
    new_product(client, auth)
    assert "Café Torrado 500g" in site.get("/busca", params={"q": "café"}).text


def test_sitemap_e_xml_com_os_produtos(site, client, auth):
    product = new_product(client, auth)
    response = site.get("/sitemap.xml")
    assert response.headers["content-type"].startswith("application/xml")
    assert response.text.startswith('<?xml version="1.0"')
    assert f"/produto/{product['id']}</loc>" in response.text


def test_robots_aponta_para_o_sitemap(site):
    assert "Sitemap: http://testserver/sitemap.xml" in site.get("/robots.txt").text


def test_endereco_antigo_redireciona(site):
    response = site.get("/view/products/prod_abc", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/produto/prod_abc"


def test_api_fica_na_versao_v1():
    from fastapi.testclient import TestClient as ServerClient
    from server import app as server_app

    server = ServerClient(server_app)
    assert server.get("/api/v1/products").status_code == 200
    response = server.get("/api/docs", follow_redirects=False)
    assert response.headers["location"] == "/api/v1/docs"


def test_robots_libera_robos_de_ia(site):
    robots = site.get("/robots.txt").text
    assert "User-agent: ClaudeBot\nAllow: /" in robots
    assert "User-agent: GPTBot\nAllow: /" in robots


def test_llms_txt_explica_a_api_v1(site):
    response = site.get("/llms.txt")
    assert response.status_code == 200
    assert "/api/v1/barcode/" in response.text


def test_apoie_sem_chave_configurada(site):
    assert "não recebe doações" in site.get("/apoie").text


def test_enderecos_do_sitemap_antigo_redirecionam(site):
    for old_address in ("/about", "/view/ncm", "/view/ncm/22030000", "/hall-da-fama", "/docs", "/mod"):
        assert site.get(old_address, follow_redirects=False).status_code == 301, old_address


def test_arquivos_estaticos_levam_a_versao_no_endereco(site):
    home = site.get("/").text
    assert '/static/style.css?v=' in home
    assert '/static/site.js?v=' in home


def test_fila_mostra_alteracao_pendente_com_botoes_de_voto(site, client, beginner_auth):
    response = client.post(
        "/products", json={"name": "<b>Café</b> Novo", "barcodes": ["7891000100103"], "reason": "produto novo"},
        headers=beginner_auth,
    )
    pending_change_id = response.json()["pending_change"]["id"]

    page = site.get("/fila")
    assert page.status_code == 200
    assert "Novo produto" in page.text
    assert "&lt;b&gt;Café&lt;/b&gt; Novo" in page.text
    assert "7891000100103" in page.text
    assert f'data-pending-change="{pending_change_id}"' in page.text

    assert "Nada por aqui" in site.get("/fila?aba=aprovadas").text
    assert site.get("/fila?aba=inventada").status_code == 404


def test_perfil_da_empresa_lista_marcas_e_produtos(site, client, auth):
    company = client.post(
        "/companies",
        json={"name": "<i>Nestlé</i>", "cnpj": "60409075000152", "brands": ["Nescau"], "website": "https://www.nestle.com.br", "reason": "nova"},
        headers=auth,
    ).json()
    product = client.post("/products", json={"name": "Achocolatado", "brand": "Nescau", "reason": "teste"}, headers=auth).json()

    page = site.get(f"/empresa/{company['id']}")
    assert page.status_code == 200
    assert "&lt;i&gt;Nestlé&lt;/i&gt;" in page.text
    assert "60.409.075/0001-52" in page.text
    assert f'href="/produto/{product["id"]}"' in page.text
    assert 'href="https://www.nestle.com.br"' in page.text

    product_page = site.get(f"/produto/{product['id']}")
    assert f'href="/empresa/{company["id"]}"' in product_page.text

    website_main.sitemap_cache["xml"] = None
    assert f"/empresa/{company['id']}</loc>" in site.get("/sitemap.xml").text

    listing = site.get("/empresas", params={"q": "Nescau"})
    assert f'href="/empresa/{company["id"]}"' in listing.text

    assert site.get("/empresa/nova").status_code == 200
    assert site.get(f"/empresa/{company['id']}/editar").status_code == 200
    assert site.get("/empresa/nao-existe").status_code == 404


def test_titulo_da_pagina_mostra_so_o_numero_do_codigo_de_barras(site, client, auth):
    product = new_product(client, auth)
    page = site.get(f"/produto/{product['id']}")
    assert "<title>Café Torrado 500g · 7891000100103 · ProdBR</title>" in page.text
