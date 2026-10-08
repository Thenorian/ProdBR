from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import CommunityBase, PublicBase, community_engine, ensure_column, public_engine
from app.rate_limit import limiter
from app.routes import admin, admin_taxes, auth, export, fiscal, geo, lookup, moderation, ncm, products, revisions, stats, users

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

PublicBase.metadata.create_all(bind=public_engine)
CommunityBase.metadata.create_all(bind=community_engine)
ensure_column(community_engine, "users", "tier_override", "VARCHAR(20)")
ensure_column(community_engine, "users", "auto_approve", "BOOLEAN NOT NULL DEFAULT 0")
for _col, _ddl in (
    ("description", "VARCHAR(120)"),
    ("net_quantity", "FLOAT"),
    ("net_unit", "VARCHAR(5)"),
    ("units_per_pack", "INTEGER"),
):
    ensure_column(public_engine, "product_identifiers", _col, _ddl)
ensure_column(public_engine, "countries", "language", "VARCHAR(10)")
ensure_column(public_engine, "countries", "subdivision_label", "VARCHAR(30)")
ensure_column(public_engine, "fiscal_rules", "rates", "JSON")


def _seed_reference_data():
    """Paises, UFs/provincias e tributos de fabrica - instalacao nova ja
    sobe pronta pra consulta. So insere o que falta."""
    from app.database import PublicSession
    from app.reference_data import ensure_reference_data

    db = PublicSession()
    try:
        ensure_reference_data(db)
    finally:
        db.close()


_seed_reference_data()


def _start_ncm_auto_update():
    """Tabela NCM oficial + IPI (TIPI) e II (TEC) sempre em dia sem cron:
    thread em segundo plano que atualiza 1x por dia (a primeira 1 min
    depois de subir, pra nao atrasar o boot). Falha de rede so loga -
    tenta de novo no dia seguinte."""
    if not settings.ncm_auto_update:
        return
    import logging
    import threading
    import time

    from app.database import PublicSession
    from app.ncm_official import update_from_siscomex
    from app.tax_official import update_from_official

    log = logging.getLogger("prodbr.ncm")

    def loop():
        time.sleep(60)
        while True:
            try:
                log.warning("NCM oficial atualizado: %s", update_from_siscomex(PublicSession))
            except Exception as exc:  # noqa: BLE001 - nunca derruba o app
                log.warning("Falha ao atualizar a tabela NCM oficial: %s", exc)
            try:
                log.warning("IPI/II oficiais atualizados: %s", update_from_official(PublicSession))
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha ao atualizar IPI (TIPI) / II (TEC): %s", exc)
            time.sleep(24 * 3600)

    threading.Thread(target=loop, name="ncm-auto-update", daemon=True).start()

@asynccontextmanager
async def lifespan(app):
    _start_ncm_auto_update()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="ProdBR API",
    description=(
        "Base publica e colaborativa de produtos brasileiros: identificacao "
        "(GTIN e outros codigos), classificacao NCM (nomenclatura do "
        "Mercosul, consultavel independente de produto em /ncm) e regras "
        "fiscais de referencia (ICMS+FCP+MVA-ST, IPI, PIS, COFINS, II, "
        "CBS/IBS) por pais, UF e vigencia. Sem precos, custos ou "
        "fornecedores. Toda alteracao gera uma revisao publica rastreavel. "
        "Software sob AGPLv3, dados sob ODbL v1.0 - ver LICENSE e "
        "DATA_LICENSE."
    ),
    version="0.2.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(products.router)
app.include_router(fiscal.router)
app.include_router(ncm.router)
app.include_router(geo.router)
app.include_router(revisions.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(moderation.router)
app.include_router(admin.router)
app.include_router(admin_taxes.router)
app.include_router(lookup.router)
app.include_router(export.router)
app.include_router(stats.router)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
# Disponivel em todo template sem precisar passar no contexto de cada rota.
templates.env.globals["ads_snippet"] = settings.ads_snippet


def _static_version() -> str:
    """Hash do conteudo de app/static - entra como ?v= em todo CSS/JS dos
    templates. Muda sozinho a cada deploy que mexe num arquivo estatico, e
    o Cloudflare (que guarda /static por 4h) passa a tratar como arquivo
    novo. Sem isso, depois do redesign de 2026-10-07 o HTML novo chegava com
    o style.css velho do cache e a pagina quebrava."""
    import hashlib

    digest = hashlib.sha1()
    for path in sorted((APP_DIR / "static").rglob("*")):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


templates.env.globals["static_v"] = _static_version()
templates.env.globals["donation"] = {
    "pix_key": settings.donation_pix_key,
    "pix_holder": settings.donation_pix_holder,
    "url": settings.donation_url,
    "url_label": settings.donation_url_label,
    "enabled": bool(settings.donation_pix_key or settings.donation_url),
}


def _base_url(request: Request) -> str:
    if settings.public_url:
        return settings.public_url.rstrip("/")
    # Atras de proxy (nginx/Cloudflare) o app ve http - respeita o esquema
    # que o proxy informa.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{proto}://{request.url.netloc}"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/new", response_class=HTMLResponse, include_in_schema=False)
def new_product_page(request: Request):
    return templates.TemplateResponse("new_product.html", {"request": request})


@app.get("/mod", response_class=HTMLResponse, include_in_schema=False)
def moderation_page(request: Request):
    return templates.TemplateResponse("moderation.html", {"request": request})


@app.get("/view/products/{product_id}", response_class=HTMLResponse, include_in_schema=False)
def product_page(request: Request, product_id: str):
    return templates.TemplateResponse(
        "product_detail.html", {"request": request, "product_id": product_id}
    )


@app.get("/view/ncm", response_class=HTMLResponse, include_in_schema=False)
def ncm_search_page(request: Request):
    return templates.TemplateResponse("ncm_search.html", {"request": request})


@app.get("/view/ncm/{code}", response_class=HTMLResponse, include_in_schema=False)
def ncm_detail_page(request: Request, code: str):
    return templates.TemplateResponse("ncm_detail.html", {"request": request, "ncm_code": code})


@app.get("/about", response_class=HTMLResponse, include_in_schema=False)
def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/hall-da-fama", response_class=HTMLResponse, include_in_schema=False)
def hall_of_fame_page(request: Request):
    return templates.TemplateResponse("hall_of_fame.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_users_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})


@app.get("/admin/tributos", response_class=HTMLResponse, include_in_schema=False)
def admin_taxes_page(request: Request):
    return templates.TemplateResponse("admin_taxes.html", {"request": request})


@app.get("/account", response_class=HTMLResponse, include_in_schema=False)
def account_page(request: Request):
    return templates.TemplateResponse("account.html", {"request": request})


@app.get("/api", response_class=HTMLResponse, include_in_schema=False)
def api_page(request: Request):
    return templates.TemplateResponse("api.html", {"request": request, "base_url": _base_url(request)})


@app.get("/apoie", response_class=HTMLResponse, include_in_schema=False)
def donation_page(request: Request):
    return templates.TemplateResponse("apoie.html", {"request": request})


# Base publica e aberta: TODO robo e bem-vindo, inclusive os de IA (Google,
# OpenAI, Anthropic, Perplexity, Common Crawl...) - quanto mais gente e
# sistema encontrar e usar os dados, melhor (pedido do mantenedor,
# 2026-10-08). Bloqueio que exista vem de fora do app (ex: "Block AI bots"
# do Cloudflare), nao daqui.
AI_CRAWLERS = (
    "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
    "anthropic-ai", "Google-Extended", "Googlebot", "Bingbot", "PerplexityBot", "Perplexity-User",
    "CCBot", "Applebot-Extended", "meta-externalagent", "Bytespider", "Amazonbot", "DuckAssistBot",
)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt(request: Request):
    lines = ["# ProdBR - base publica e aberta. Todos os robos sao bem-vindos, inclusive os de IA.", ""]
    for bot in AI_CRAWLERS:
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    lines += ["User-agent: *", "Allow: /", "", f"Sitemap: {_base_url(request)}/sitemap.xml", ""]
    return "\n".join(lines)


@app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
def llms_txt(request: Request):
    """Resumo pra LLMs (padrao llmstxt.org): o que e o ProdBR e como usar a
    API - ajuda assistentes de IA a responder e integrar certo."""
    base = _base_url(request)
    return f"""# ProdBR

> Base de dados publica, gratuita e colaborativa de produtos brasileiros: dado um codigo de barras (GTIN/EAN), NCM ou nome, devolve identificacao do produto (nome, marca, fabricante, categoria, unidade), embalagens (um GTIN por tamanho, ex: 1 kg, 15 kg) e a classificacao fiscal (NCM, CEST) com aliquotas de referencia (ICMS, FCP, IPI, PIS, COFINS, II, CBS/IBS). Feita para ERPs, PDVs e emissores de NF-e/NFC-e. Software AGPLv3, dados ODbL v1.0.

Toda leitura e publica, sem autenticacao e sem chave. Escrita (cadastrar/editar) exige conta e o header `X-API-Key`; contribuicoes de contas novas passam por moderacao ou votacao da comunidade.

## Consulta de tributos (estilo ViaCEP)

- [Tributos de um NCM numa UF]({base}/v1/BR/SP/23091000): `GET /v1/<pais>/<uf>/<ncm ou GTIN>` - lista `taxes` com codigo, nome traduzido (`?lang=pt|es|en`), aliquota (`rate`), esfera e fonte
- [So os nacionais]({base}/v1/AR/23091000): `GET /v1/<pais>/<ncm>`
- [Paises, UFs/provincias e tributos]({base}/v1/UY): `GET /v1/<pais>` (paises: `GET /countries`)
- `general_rate: true` = aliquota geral do pais (sem regra especifica pro NCM); `rate: null` = tributo existe mas ainda sem dado
- Pagina com exemplos: {base}/api

## API (leitura, sem autenticacao)

- [Buscar produto por codigo de barras]({base}/products?identifier=7898242031967): `GET /products?identifier=<GTIN>`
- [Buscar por NCM]({base}/products?ncm=23091000): `GET /products?ncm=<8 digitos>`
- [Buscar por texto]({base}/products?q=special%20dog): `GET /products?q=<texto>` (paginado: `limit`, `offset`)
- Produto por id: `GET /products/<id>`
- [Classificacao NCM]({base}/ncm/23091000): `GET /ncm/<ncm>`
- [Regras fiscais vigentes]({base}/fiscal-rules?ncm=23091000&uf=PR): `GET /fiscal-rules?ncm=<ncm>&uf=<UF>`
- Aliquotas aplicaveis a um produto: `GET /products/<id>/fiscal?uf=<UF>`
- [Base completa (SQLite)]({base}/export/sqlite): `GET /export/sqlite`

## Documentacao

- [Swagger / OpenAPI]({base}/docs): todos os endpoints, testaveis no navegador
- [Sobre o projeto]({base}/about)
- [Codigo-fonte](https://github.com/Thenorian/ProdBR)

## Observacoes

- Aliquotas sao de referencia; confirme com o contador antes de emitir nota.
- Mesmo produto em embalagens diferentes = um produto com varios GTINs (campos `description`, `net_quantity`, `net_unit`, `units_per_pack` em cada identificador).
"""


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request):
    from xml.sax.saxutils import escape

    from app.database import PublicSession
    from app.models_public import Product

    base = _base_url(request)
    urls = [f"{base}/", f"{base}/about", f"{base}/view/ncm", f"{base}/hall-da-fama", f"{base}/docs"]
    db = PublicSession()
    try:
        # Limite do protocolo de sitemap: 50.000 URLs por arquivo.
        ids = [row[0] for row in db.query(Product.id).limit(49_000).all()]
    finally:
        db.close()
    urls += [f"{base}/view/products/{pid}" for pid in ids]
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(content=xml, media_type="application/xml")


@app.get("/license", include_in_schema=False)
def license_file():
    return FileResponse(PROJECT_ROOT / "LICENSE", media_type="text/plain")


@app.get("/data-license", include_in_schema=False)
def data_license_file():
    return FileResponse(PROJECT_ROOT / "DATA_LICENSE", media_type="text/plain")
