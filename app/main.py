from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import CommunityBase, PublicBase, community_engine, public_engine
from app.rate_limit import limiter
from app.routes import auth, export, fiscal, moderation, products, revisions, users

APP_DIR = Path(__file__).resolve().parent

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

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
