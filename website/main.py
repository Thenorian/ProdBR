"""
Site do ProdBR: as páginas para pessoas. Os dados vêm da API pública (website/api_client.py),
e o HTML já sai pronto do servidor, para o Google conseguir ler cada produto.

A única coisa que o site lê direto do banco é a reputação dos contribuidores,
que de propósito não existe na API.
"""
import os
import time
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database.contributor import ContributorDB
from website.api_client import get_from_api
from website.formatting import register_filters

SITE_FOLDER = Path(__file__).resolve().parent
PROJECT_ROOT = SITE_FOLDER.parent

RESULTS_PER_PAGE = 20
SITEMAP_PAGE_SIZE = 50
SITEMAP_CACHE_IN_SECONDS = 3600

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=SITE_FOLDER / "static"), name="static")

templates = Jinja2Templates(directory=SITE_FOLDER / "templates")
register_filters(templates.env)
templates.env.globals["ads_snippet"] = os.getenv("ADS_SNIPPET", "")
# Endereço da API que o navegador usa para salvar alterações. Mesmo domínio por padrão.
templates.env.globals["public_api_url"] = os.getenv("PUBLIC_API_URL", "/api/v1")

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
    return page(
        request, "product.html",
        product=product, revisions=revisions.get("items", []), selected_uf=uf, selected_regime=regime,
    )


@app.get("/produto/{product_id}/editar", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: str):
    status, product = get_from_api(["products", product_id])
    if status != 200:
        return error_page(request, status, product.get("detail", "Produto não encontrado."))

    return page(request, "product_form.html", product=product)


@app.get("/entrar", response_class=HTMLResponse)
def sign_in(request: Request):
    return page(request, "sign_in.html")


@app.get("/sobre", response_class=HTMLResponse)
def about(request: Request):
    ok, ranking = ContributorDB().list_ranking(30)
    return page(request, "about.html", ranking=ranking if ok else [])


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request):
    return f"User-agent: *\nAllow: /\nDisallow: /produto/novo\n\nSitemap: {site_address(request)}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap(request: Request):
    """
    Sitemap em XML (o formato que o Google aceita), com a página de cada produto.
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
