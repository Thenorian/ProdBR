"""
Site do ProdBR: as páginas para pessoas. Os dados vêm da API pública (website/api_client.py),
e o HTML já sai pronto do servidor, para o Google conseguir ler cada produto.

A única coisa que o site lê direto do banco é a reputação dos contribuidores,
que de propósito não existe na API.
"""
import hashlib
import os
import time
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database.contributor import ContributorDB
from website.api_client import get_from_api
from website.formatting import register_filters
from website.price_chart import build_price_chart

SITE_FOLDER = Path(__file__).resolve().parent
PROJECT_ROOT = SITE_FOLDER.parent

RESULTS_PER_PAGE = 20
SITEMAP_PAGE_SIZE = 50
SITEMAP_CACHE_IN_SECONDS = 3600

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=SITE_FOLDER / "static"), name="static")

templates = Jinja2Templates(directory=SITE_FOLDER / "templates")
register_filters(templates.env)


def static_file_versions():
    """
    O Cloudflare guarda os arquivos de /static por horas. Cada endereço leva um pedaço do
    hash do conteúdo (?v=...), então quando o arquivo muda o endereço muda e o cache antigo não vale.
    """
    versions = {}
    for file in (SITE_FOLDER / "static").iterdir():
        versions[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()[:10]
    return versions


STATIC_FILE_VERSIONS = static_file_versions()


def static_url(file_name):
    """ static_url("style.css") -> "/static/style.css?v=3f2a9c1b0d" """
    return f"/static/{file_name}?v={STATIC_FILE_VERSIONS.get(file_name, '')}"


templates.env.globals["static_url"] = static_url
templates.env.globals["ads_snippet"] = os.getenv("ADS_SNIPPET", "")
# Endereço da API que o navegador usa para salvar alterações. Mesmo domínio por padrão.
templates.env.globals["public_api_url"] = os.getenv("PUBLIC_API_URL", "/api/v1")
# Doação: cada cópia do ProdBR usa a própria chave. Vazio = nada de doação aparece.
templates.env.globals["donation"] = {
    "pix_key": os.getenv("DONATION_PIX_KEY", ""),
    "pix_holder": os.getenv("DONATION_PIX_HOLDER", ""),
    "url": os.getenv("DONATION_URL", ""),
    "url_label": os.getenv("DONATION_URL_LABEL", "Apoiar pelo site"),
    "enabled": bool(os.getenv("DONATION_PIX_KEY") or os.getenv("DONATION_URL")),
}

# Base pública e aberta: todo robô é bem-vindo, inclusive os de IA, para mais gente achar a API.
# Se algum dia for preciso bloquear, isso é feito fora do app (ex: Cloudflare), não aqui.
CRAWLERS_WELCOME_BY_NAME = (
    "Googlebot", "Bingbot", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
    "Claude-User", "anthropic-ai", "Google-Extended", "PerplexityBot", "Perplexity-User", "CCBot",
    "Applebot-Extended", "meta-externalagent", "Bytespider", "Amazonbot", "DuckAssistBot",
)

sitemap_cache = {"xml": None, "created_at": 0.0}


def page(request, template, status_code=200, **context):
    return templates.TemplateResponse(request, template, context, status_code=status_code)


def error_page(request, status_code, message):
    return page(request, "error.html", status_code=status_code, message=message)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    _, recent_products = get_from_api(["products"], {"order": "recent", "limit": 8})
    _, recent_changes = get_from_api(["revisions"], {"limit": 8})

    return page(
        request, "home.html",
        recent_products=recent_products.get("items", []),
        product_total=recent_products.get("total", 0),
        recent_changes=recent_changes.get("items", []),
        change_total=recent_changes.get("total", 0),
    )


@app.get("/busca", response_class=HTMLResponse)
def search(request: Request, q: str = "", pagina: int = 1):
    q = q.strip()[:100]
    pagina = max(1, pagina)
    results = {"items": [], "total": 0}

    if q:
        status, results = get_from_api(
            ["products"], {"q": q, "limit": RESULTS_PER_PAGE, "offset": (pagina - 1) * RESULTS_PER_PAGE}
        )
        if status != 200:
            return error_page(request, status, results.get("detail", "Erro na busca."))

    page_count = max(1, -(-results["total"] // RESULTS_PER_PAGE))
    return page(request, "search.html", q=q, results=results, pagina=pagina, page_count=page_count)


@app.get("/produto/novo", response_class=HTMLResponse)
def new_product_form(request: Request):
    return page(request, "product_form.html", product=None)


@app.get("/produto/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: str, uf: str = "", regime: str = ""):
    status, product = get_from_api(["products", product_id], {"uf": uf, "tax_regime": regime})
    if status != 200:
        return error_page(request, status, product.get("detail", "Produto não encontrado."))

    _, revisions = get_from_api(["products", product_id, "revisions"], {"limit": 10})
    _, prices = get_from_api(["products", product_id, "prices"], {"uf": uf})
    base_sale_price = (product.get("price") or {}).get("base_sale_price")
    return page(
        request, "product.html",
        product=product, revisions=revisions.get("items", []), selected_uf=uf, selected_regime=regime,
        price_chart=build_price_chart(prices.get("items", []), base_sale_price),
    )


@app.get("/produto/{product_id}/editar", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: str):
    status, product = get_from_api(["products", product_id])
    if status != 200:
        return error_page(request, status, product.get("detail", "Produto não encontrado."))

    return page(request, "product_form.html", product=product)


@app.get("/empresas", response_class=HTMLResponse)
def companies_page(request: Request, q: str = "", pagina: int = 1):
    q = q.strip()[:100]
    pagina = max(1, pagina)
    status, results = get_from_api(
        ["companies"], {"q": q, "limit": RESULTS_PER_PAGE, "offset": (pagina - 1) * RESULTS_PER_PAGE}
    )
    if status != 200:
        return error_page(request, status, results.get("detail", "Erro na busca de empresas."))

    page_count = max(1, -(-results["total"] // RESULTS_PER_PAGE))
    return page(request, "companies.html", q=q, results=results, pagina=pagina, page_count=page_count)


@app.get("/empresa/nova", response_class=HTMLResponse)
def new_company_form(request: Request):
    return page(request, "company_form.html", company=None)


@app.get("/empresa/{company_id}", response_class=HTMLResponse)
def company_page(request: Request, company_id: str, pagina: int = 1):
    status, company = get_from_api(["companies", company_id])
    if status != 200:
        return error_page(request, status, company.get("detail", "Empresa não encontrada."))

    pagina = max(1, pagina)
    _, products = get_from_api(
        ["companies", company_id, "products"], {"limit": RESULTS_PER_PAGE, "offset": (pagina - 1) * RESULTS_PER_PAGE}
    )
    _, revisions = get_from_api(["companies", company_id, "revisions"], {"limit": 10})
    page_count = max(1, -(-products.get("total", 0) // RESULTS_PER_PAGE))
    return page(
        request, "company.html",
        company=company, products=products.get("items", []), revisions=revisions.get("items", []),
        pagina=pagina, page_count=page_count,
    )


@app.get("/empresa/{company_id}/editar", response_class=HTMLResponse)
def edit_company_form(request: Request, company_id: str):
    status, company = get_from_api(["companies", company_id])
    if status != 200:
        return error_page(request, status, company.get("detail", "Empresa não encontrada."))
    return page(request, "company_form.html", company=company)


QUEUE_TABS = {"pendentes": "pending", "aprovadas": "approved", "descartadas": "rejected", "falharam": "failed"}


@app.get("/fila", response_class=HTMLResponse)
def review_queue(request: Request, aba: str = "pendentes", pagina: int = 1):
    """Alterações de quem ainda é Iniciante, esperando os votos da comunidade."""
    status = QUEUE_TABS.get(aba)
    if status is None:
        return error_page(request, 404, "Aba não encontrada.")

    pagina = max(1, pagina)
    api_status, queue = get_from_api(
        ["pending-changes"], {"status": status, "limit": RESULTS_PER_PAGE, "offset": (pagina - 1) * RESULTS_PER_PAGE}
    )
    if api_status != 200:
        return error_page(request, api_status, queue.get("detail", "Erro ao carregar a fila."))

    page_count = max(1, -(-queue["total"] // RESULTS_PER_PAGE))
    return page(request, "review_queue.html", queue=queue, aba=aba, tabs=QUEUE_TABS, pagina=pagina, page_count=page_count)


@app.get("/entrar", response_class=HTMLResponse)
def sign_in(request: Request):
    return page(request, "sign_in.html")


@app.get("/sobre", response_class=HTMLResponse)
def about(request: Request):
    _, ibpt_versions = get_from_api(["ibpt"])
    return page(request, "about.html", ibpt_versions=ibpt_versions.get("items", []))


PODIUM_SIZE = 3
PEOPLE_PER_RANKING_COLUMN = 50
RANKING_COLUMNS = 3


@app.get("/contribuidores", response_class=HTMLResponse)
def contributors_page(request: Request):
    """
    Pódio com os 3 que mais contribuíram e, abaixo, três colunas de até 50 pessoas cada
    (4º ao 53º, 54º ao 103º, 104º ao 153º). A reputação e o nível não existem na API de
    propósito, por isso esta página lê do banco da comunidade.
    """
    contributors = ContributorDB()
    ok, ranking = contributors.list_ranking(PODIUM_SIZE + PEOPLE_PER_RANKING_COLUMN * RANKING_COLUMNS)
    ranking = ranking if ok else []
    ok, totals_by_level = contributors.totals_by_level()

    for position, contributor in enumerate(ranking, start=1):
        contributor["position"] = position

    after_podium = ranking[PODIUM_SIZE:]
    columns = [
        after_podium[start:start + PEOPLE_PER_RANKING_COLUMN]
        for start in range(0, PEOPLE_PER_RANKING_COLUMN * RANKING_COLUMNS, PEOPLE_PER_RANKING_COLUMN)
    ]
    return page(
        request, "contributors.html",
        podium=ranking[:PODIUM_SIZE], columns=[column for column in columns if column],
        totals_by_level=totals_by_level if ok else [],
    )


@app.get("/apoie", response_class=HTMLResponse)
def donation(request: Request):
    return page(request, "donation.html")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request):
    lines = ["# ProdBR: base pública e aberta. Todos os robôs são bem-vindos, inclusive os de IA.", ""]
    for crawler in CRAWLERS_WELCOME_BY_NAME:
        lines += [f"User-agent: {crawler}", "Allow: /", ""]
    lines += ["User-agent: *", "Allow: /", "", f"Sitemap: {site_address(request)}/sitemap.xml", ""]
    return "\n".join(lines)


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt(request: Request):
    """Resumo do ProdBR para assistentes de IA (padrão llmstxt.org), para recomendarem e integrarem a API certo."""
    address = site_address(request)
    return f"""# ProdBR

> Base de dados pública, gratuita e colaborativa de produtos brasileiros, feita para preencher o cadastro de produtos em ERPs, PDVs e emissores de NF-e/NFC-e. Pelo código de barras (GTIN/EAN) devolve tudo de uma vez: nome, marca, fabricante, código do fabricante, categoria, unidade, embalagem de cada código, NCM, CEST, origem, preço médio informado e regras fiscais de referência (ICMS, FCP, IPI, PIS, COFINS, II, CBS, IBS) por UF e regime tributário. Código AGPLv3, dados ODbL v1.0.

Toda leitura é pública, sem cadastro e sem chave. Para cadastrar ou editar, crie um token em `POST /api/v1/contributors` e envie no cabeçalho `X-API-Key`. Toda alteração fica num histórico público.

## API v1 (leitura, sem autenticação)

- [Produto pelo código de barras]({address}/api/v1/barcode/7891000100103): `GET /api/v1/barcode/<GTIN>?uf=<UF>&tax_regime=<simples_nacional|lucro_presumido|lucro_real>`
- [Buscar produtos]({address}/api/v1/products?q=arroz): `GET /api/v1/products` com `q`, `barcode`, `ncm`, `manufacturer`, `manufacturer_code`, `category_id` (paginado: `limit`, `offset`)
- Produto por id: `GET /api/v1/products/<id>` e o histórico em `GET /api/v1/products/<id>/revisions`
- Produtos alterados desde uma data (sincronizar ERP): `GET /api/v1/products/changed?since=AAAA-MM-DD`
- [NCM oficial e regras fiscais]({address}/api/v1/ncm/23091000): `GET /api/v1/ncm/<ncm>` e busca em `GET /api/v1/ncm?q=<texto>`
- [Categorias]({address}/api/v1/categories): `GET /api/v1/categories` (o produto sem NCM usa o da categoria)
- [Base completa em SQLite]({address}/api/v1/download/prodbr.sqlite3)

## Documentação

- [OpenAPI / Swagger]({address}/api/v1/docs): todos os endpoints, testáveis no navegador
- [Sobre o projeto]({address}/sobre)
- [Código-fonte](https://github.com/Thenorian/ProdBR)

## Observações

- NCM sempre com 8 dígitos, só números.
- A versão faz parte do endereço (`/api/v1`) e não muda de forma incompatível.
- Alíquotas são de referência: confirme com a contabilidade antes de emitir nota.
"""


@app.get("/sitemap.xml")
def sitemap(request: Request):
    """
    Sitemap em XML (o formato que o Google aceita), com a página de cada produto e de cada empresa.
    Fica uma hora em memória para não percorrer a base toda a cada visita do robô.
    """
    cache_is_fresh = time.monotonic() - sitemap_cache["created_at"] < SITEMAP_CACHE_IN_SECONDS
    if not sitemap_cache["xml"] or not cache_is_fresh:
        sitemap_cache["xml"] = build_sitemap(site_address(request))
        sitemap_cache["created_at"] = time.monotonic()

    return Response(content=sitemap_cache["xml"], media_type="application/xml")


def build_sitemap(address):
    entries = [f"<url><loc>{escape(address)}/</loc></url>", f"<url><loc>{escape(address)}/sobre</loc></url>"]

    offset = 0
    while True:
        status, changed = get_from_api(["products", "changed"], {"limit": SITEMAP_PAGE_SIZE, "offset": offset})
        items = changed.get("items", []) if status == 200 else []
        for product in items:
            product_address = escape(f"{address}/produto/{product['id']}")
            entries.append(f"<url><loc>{product_address}</loc><lastmod>{product['updated_at'][:10]}</lastmod></url>")
        if len(items) < SITEMAP_PAGE_SIZE:
            break
        offset += SITEMAP_PAGE_SIZE

    offset = 0
    while True:
        status, companies = get_from_api(["companies"], {"limit": SITEMAP_PAGE_SIZE, "offset": offset})
        items = companies.get("items", []) if status == 200 else []
        for company in items:
            company_address = escape(f"{address}/empresa/{company['cnpj'] or company['id']}")
            entries.append(f"<url><loc>{company_address}</loc></url>")
        if len(items) < SITEMAP_PAGE_SIZE:
            break
        offset += SITEMAP_PAGE_SIZE

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def site_address(request):
    """Endereço público do site (ex: https://prodbr.com.br), lido do próprio acesso."""
    return os.getenv("PUBLIC_URL") or str(request.base_url).rstrip("/")


# Endereços da versão antiga, para links salvos e o Google não caírem em página inexistente.
@app.get("/view/products/{product_id}")
def old_product_address(product_id: str):
    return RedirectResponse(f"/produto/{product_id}", status_code=301)


@app.get("/about")
def old_about_address():
    return RedirectResponse("/sobre", status_code=301)


@app.get("/new")
def old_new_product_address():
    return RedirectResponse("/produto/novo", status_code=301)


@app.get("/view/ncm")
def old_ncm_search_address(q: str = ""):
    return RedirectResponse(f"/busca?q={urllib.parse.quote(q)}" if q else "/busca", status_code=301)


@app.get("/view/ncm/{code}")
def old_ncm_address(code: str):
    return RedirectResponse(f"/busca?q={urllib.parse.quote(code)}", status_code=301)


@app.get("/hall-da-fama")
def old_hall_of_fame_address():
    return RedirectResponse("/contribuidores", status_code=301)


@app.get("/mod")
@app.get("/admin")
def old_moderation_addresses():
    return RedirectResponse("/fila", status_code=301)


@app.get("/login")
@app.get("/register")
@app.get("/account")
def old_sign_in_addresses():
    return RedirectResponse("/entrar", status_code=301)


@app.get("/docs")
def old_docs_address():
    return RedirectResponse("/api/v1/docs", status_code=301)


@app.get("/license", response_class=PlainTextResponse)
def license_file():
    return (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")


@app.get("/data-license", response_class=PlainTextResponse)
def data_license_file():
    return (PROJECT_ROOT / "DATA_LICENSE").read_text(encoding="utf-8")


@app.get("/export/sqlite")
def old_download_address():
    return RedirectResponse("/api/v1/download/prodbr.sqlite3", status_code=301)
