"""
O site não acessa o banco de produtos: ele busca tudo na API pública, igual a qualquer ERP.
Usa o urllib que já vem no Python, sem biblioteca externa.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

# No servidor o site e a API rodam no mesmo processo (ver server.py), então a API está no próprio endereço.
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
TIMEOUT_IN_SECONDS = 10


def get_from_api(path_parts, params=None):
    """
    Faz um GET na API e devolve (status, dados).

        get_from_api(["products", product_id], {"uf": "SP"})  ->  (200, {...produto...})
        get_from_api(["barcode", "000"])                     ->  (404, {"detail": "..."})

    Cada parte do caminho é codificada, então um id malicioso não muda a rota chamada.
    """
    path = "/".join(urllib.parse.quote(str(part), safe="") for part in path_parts)
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = f"{API_URL}/{path}" + (f"?{query}" if query else "")

    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_IN_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except ValueError:
            return error.code, {"detail": "Erro na API."}

    except (urllib.error.URLError, TimeoutError, ValueError):
        return 503, {"detail": "A API não respondeu."}
