"""
Sobe o site e a API juntos, num processo só, que é como roda no servidor:

    uvicorn server:app

    /          site (páginas para pessoas)
    /api/v1    API pública (JSON, para ERPs). Documentação em /api/v1/docs

São dois apps separados: a API também roda sozinha (uvicorn api.main:app),
e o site só conversa com ela por HTTP, como qualquer ERP faria.

Versões da API: uma versão publicada nunca muda de um jeito que quebre quem já usa.
Campo novo ou rota nova pode entrar na v1. Tirar, renomear ou mudar o formato de algo
exige uma /api/v2, montada aqui ao lado, com a v1 continuando no ar.
"""
from fastapi.responses import RedirectResponse

from api.main import app as api_v1
from website.main import app

API_VERSIONS = {"v1": api_v1}
CURRENT_API_VERSION = "v1"


@app.get("/api", include_in_schema=False)
@app.get("/api/docs", include_in_schema=False)
def api_documentation_of_current_version():
    return RedirectResponse(f"/api/{CURRENT_API_VERSION}/docs", status_code=302)


for version, api_app in API_VERSIONS.items():
    app.mount(f"/api/{version}", api_app)
