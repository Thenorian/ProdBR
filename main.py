"""Ponto de entrada na raiz do projeto - rode a partir daqui (`python
main.py`), nao de dentro de app/. `uvicorn app.main:app` precisa que o
diretorio de trabalho seja a raiz (ProdBR), senao o Python nao acha o
pacote `app`.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
