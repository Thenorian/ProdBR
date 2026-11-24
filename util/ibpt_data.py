"""
Tabela do IBPT (Lei 12.741/2012): carga tributária aproximada por NCM/NBS e UF,
que o ERP imprime na nota e no cupom fiscal.

O IBPT publica uma tabela por UF. Ela é baixada já em JSON, uma UF por vez,
de um espelho público e gratuito (IBPT_SOURCE_URL no .env para trocar).
O que vem de fora é conferido linha por linha antes de gravar: código só com dígitos,
taxas numéricas entre 0 e 100 e datas no formato AAAA-MM-DD. Linha fora disso é ignorada.
"""
import gzip
import json
import os
import re
import time
import urllib.parse
import urllib.request

from database.ibpt import IbptDB
from util.validation import BRAZILIAN_STATES

DEFAULT_IBPT_SOURCE_URL = "https://api-ibpt.seunegocionanuvem.com.br/api_ibpt_json.php"
USER_AGENT = "ProdBR/1.0 (+https://github.com/Thenorian/ProdBR)"
DOWNLOAD_TIMEOUT_IN_SECONDS = 120
MAXIMUM_DOWNLOAD_SIZE_IN_BYTES = 50 * 1024 * 1024
SECONDS_BETWEEN_STATES = 2

CODE = re.compile(r"^\d{2,9}$")
EX = re.compile(r"^\d{0,3}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSION = re.compile(r"^[\w.\-]{1,20}$")
ITEM_TYPES = (0, 1, 2)


def download_state_table(uf):
    """JSON da tabela vigente de uma UF: {"versao": "26.2.C", "uf": "SP", "total": 12162, "ncm": [...]}"""
    source_url = os.getenv("IBPT_SOURCE_URL") or DEFAULT_IBPT_SOURCE_URL
    url = f"{source_url}?{urllib.parse.urlencode({'uf': uf})}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})

    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_IN_SECONDS) as response:
        content = response.read(MAXIMUM_DOWNLOAD_SIZE_IN_BYTES + 1)
        if len(content) > MAXIMUM_DOWNLOAD_SIZE_IN_BYTES:
            raise RuntimeError(f"Tabela do IBPT de {uf} maior que o limite de segurança.")
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            content = gzip.decompress(content)

    return json.loads(content.decode("utf-8"))


def read_state_table(content, uf):
    """
    Confere o JSON baixado e devolve (versão, linhas prontas para gravar).
    Levanta ValueError se o arquivo inteiro não serve (UF errada, sem versão, sem linhas).
    """
    if not isinstance(content, dict) or content.get("uf") != uf:
        raise ValueError(f"A tabela baixada não é da UF {uf}.")

    version = str(content.get("versao") or "")
    if not VERSION.match(version):
        raise ValueError(f"Versão inválida na tabela do IBPT de {uf}: {version!r}")

    rows = []
    for item in content.get("ncm") or []:
        row = read_row(item)
        if row is not None:
            rows.append(row)

    if not rows:
        raise ValueError(f"A tabela do IBPT de {uf} veio sem nenhuma linha válida.")
    return version, rows


def read_row(item):
    """Uma linha da tabela, conferida. None se algum campo não estiver no formato esperado."""
    if not isinstance(item, dict):
        return None

    code = str(item.get("codigo") or "")
    ex = str(item.get("ex") or "")
    if not CODE.match(code) or not EX.match(ex):
        return None

    try:
        item_type = int(item.get("tipo") or 0)
        rates = {
            "federal_national_rate": float(item["nacionalfederal"]),
            "federal_imported_rate": float(item["importadosfederal"]),
            "state_rate": float(item["estadual"]),
            "municipal_rate": float(item["municipal"]),
        }
    except (KeyError, TypeError, ValueError):
        return None

    if item_type not in ITEM_TYPES or not all(0 <= rate <= 100 for rate in rates.values()):
        return None

    return {
        "code": code,
        "ex": ex,
        "item_type": item_type,
        "description": " ".join(str(item.get("descricao") or "").split())[:1000] or None,
        **rates,
        "valid_from": date_or_none(item.get("vigenciainicio")),
        "valid_until": date_or_none(item.get("vigenciafim")),
        "source": " ".join(str(item.get("fonte") or "IBPT").split())[:100],
    }


def date_or_none(value):
    value = str(value or "")
    return value if DATE.match(value) else None


def update_state(uf):
    """
    Baixa e grava a tabela de uma UF, só se a versão mudou.
    Devolve (True, "SP: 26.2.C, 12162 linhas"), (True, "SP: sem novidade (26.2.C)") ou (False, erro).
    """
    version, rows = read_state_table(download_state_table(uf), uf)

    ibpt = IbptDB()
    ok, current_version = ibpt.current_version(uf)
    if not ok:
        return False, current_version
    if current_version == version:
        return True, f"{uf}: sem novidade ({version})"

    ok, saved = ibpt.replace_state_table(uf, version, rows)
    if not ok:
        return False, f"{uf}: erro ao gravar: {saved}"
    return True, f"{uf}: {version}, {saved} linhas"


def update_all_states():
    """Atualiza as 27 UFs, uma de cada vez. A falha de uma não impede as outras."""
    for uf in BRAZILIAN_STATES:
        try:
            ok, message = update_state(uf)
            print(f"[IBPT] {message}")
        except Exception as error:
            print(f"[IBPT] {uf}: não foi possível atualizar: {error}")
        time.sleep(SECONDS_BETWEEN_STATES)
