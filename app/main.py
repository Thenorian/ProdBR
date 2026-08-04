from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import CommunityBase, PublicBase, community_engine, public_engine
from app.rate_limit import limiter
from app.routes import auth, export, fiscal, moderation, products, revisions, stats, users

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

PublicBase.metadata.create_all(bind=public_engine)
CommunityBase.metadata.create_all(bind=community_engine)

app = FastAPI(
    title="ProdBR API",
    description=(
        "Base publica e colaborativa de produtos brasileiros: identificacao "
        "(GTIN e outros codigos), classificacao (NCM/CEST) e regras fiscais "
        "de referencia (ICMS, IPI, PIS, COFINS, CBS/IBS) por UF e vigencia. "
        "Sem precos, custos ou fornecedores. Toda alteracao gera uma revisao "
        "publica rastreavel. Software sob AGPLv3, dados sob ODbL v1.0 - "
        "ver LICENSE e DATA_LICENSE."
    ),
    version="0.2.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(products.router)
app.include_router(fiscal.router)
app.include_router(revisions.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(moderation.router)
app.include_router(export.router)
app.include_router(stats.router)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
# Disponivel em todo template sem precisar passar no contexto de cada rota.
templates.env.globals["ads_snippet"] = settings.ads_snippet


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


@app.get("/license", include_in_schema=False)
def license_file():
    return FileResponse(PROJECT_ROOT / "LICENSE", media_type="text/plain")


@app.get("/data-license", include_in_schema=False)
def data_license_file():
    return FileResponse(PROJECT_ROOT / "DATA_LICENSE", media_type="text/plain")
