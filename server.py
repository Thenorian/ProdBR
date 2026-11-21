"""
Sobe o site e a API juntos, num processo só, que é como roda no servidor:

    uvicorn server:app

    /       site (páginas para pessoas)
    /api    API pública (JSON, para ERPs). Documentação em /api/docs

São dois apps separados: a API também roda sozinha (uvicorn api.main:app),
e o site só conversa com ela por HTTP, como qualquer ERP faria.
"""
from api.main import app as api_app
from website.main import app

app.mount("/api", api_app)
