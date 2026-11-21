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
