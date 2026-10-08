from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import CommunityBase, PublicBase, community_engine, ensure_column, public_engine
from app.rate_limit import limiter
from app.routes import admin, auth, export, fiscal, geo, moderation, ncm, products, revisions, stats, users

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

app = FastAPI(
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


@app.get("/account", response_class=HTMLResponse, include_in_schema=False)
def account_page(request: Request):
    return templates.TemplateResponse("account.html", {"request": request})


@app.get("/license", include_in_schema=False)
def license_file():
    return FileResponse(PROJECT_ROOT / "LICENSE", media_type="text/plain")


@app.get("/data-license", include_in_schema=False)
def data_license_file():
    return FileResponse(PROJECT_ROOT / "DATA_LICENSE", media_type="text/plain")
