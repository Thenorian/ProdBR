import pytest

from app import main


def test_robots_allows_everyone_including_ai(client):
    res = client.get("/robots.txt")
    assert res.status_code == 200
    body = res.text
    for bot in ("GPTBot", "ClaudeBot", "Google-Extended", "PerplexityBot", "CCBot"):
        assert f"User-agent: {bot}\nAllow: /" in body
    assert "Disallow" not in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_llms_txt_documents_public_api(client):
    res = client.get("/llms.txt")
    assert res.status_code == 200
    assert res.text.startswith("# ProdBR")
    assert "/products?identifier=" in res.text and "/fiscal-rules?ncm=" in res.text


def test_sitemap_lists_products(client, moderator_headers):
    product = client.post(
        "/products", json={"name": "Produto no sitemap", "ncm": "23091000", "source": "Teste", "reason": "Teste"},
        headers=moderator_headers,
    ).json()
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert f"/view/products/{product['id']}</loc>" in res.text


def test_donation_hidden_unless_configured(client, monkeypatch):
    monkeypatch.setitem(main.templates.env.globals, "donation", {"enabled": False, "pix_key": "", "url": ""})
    assert "Apoie o projeto" not in client.get("/").text
    assert "não recebe doações" in client.get("/apoie").text

    monkeypatch.setitem(
        main.templates.env.globals,
        "donation",
        {"enabled": True, "pix_key": "pix@exemplo.com", "pix_holder": "Fulano", "url": "", "url_label": ""},
    )
    assert "Apoie o projeto" in client.get("/").text
    page = client.get("/apoie").text
    assert "pix@exemplo.com" in page and "Fulano" in page
