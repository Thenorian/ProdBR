"""
API pública do ProdBR. Funciona sozinha, sem o site:

    uvicorn api.main:app

Leitura é livre e sem chave. Escrita exige o token do contribuidor no cabeçalho X-API-Key.
"""
from fastapi import FastAPI

from api import categories, contributors, download, fiscal, ncm, products, revisions
from database.setup import prepare_databases
from util.daily_update import start_daily_official_update

prepare_databases()
start_daily_official_update()

app = FastAPI(
    title="ProdBR API",
    version="1.0.0",
    # Versão da API no endereço: /api/v1. Ver a regra de versões em server.py.
    description=(
        "Base pública e colaborativa de produtos brasileiros, feita para preencher o cadastro "
        "de produtos em ERPs. Pelo código de barras (GET /barcode/{código}) vem tudo de uma vez: "
        "nome, marca, fabricante, NCM, CEST, categoria, preço médio e regras fiscais "
        "(ICMS, IPI, PIS, COFINS, CBS, IBS) por UF e regime tributário.\n\n"
        "Leitura livre, sem chave. Para contribuir, crie um token em POST /contributors e envie no "
        "cabeçalho X-API-Key. Toda alteração fica no histórico público. "
        "Código sob AGPLv3, dados sob ODbL v1.0."
    ),
)

app.include_router(products.router)
app.include_router(categories.router)
app.include_router(ncm.router)
app.include_router(fiscal.router)
app.include_router(revisions.router)
app.include_router(contributors.router)
app.include_router(download.router)
