"""Tabela NCM oficial (Siscomex) -> ncm_classifications.

Fonte: Portal Unico Siscomex, JSON publico da nomenclatura vigente (o mesmo
arquivo do "download da tabela NCM" do governo). Traz ~15 mil codigos de
todos os niveis (capitulo, posicao, subposicao, item, subitem), com data de
inicio/fim de vigencia e o ato legal.

So os codigos de 8 digitos vigentes viram linha na base. A descricao de um
subitem sozinha costuma ser inutil ("- - Outras"), entao a gravada e a
hierarquia inteira: "Preparacoes do tipo utilizado na alimentacao de
animais > Outras > Preparacoes destinadas a fornecer...".

Usado pelo comando `python -m scripts.import_ncm` e pela atualizacao
automática diária (ver app/jobs.py). Nunca apaga NCM que saiu da tabela -
produto pode estar usando - so cria e atualiza.
"""

import json
import re
import urllib.request
from datetime import date, datetime

from app.models import NcmClassification

SISCOMEX_URL = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"
USER_AGENT = "ProdBR/1.0 (+https://github.com/Thenorian/ProdBR)"
_DASHES = re.compile(r"^[\s\-–—]+")
_TAGS = re.compile(r"<[^>]+>")


def fetch(url: str = SISCOMEX_URL, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean(text: str) -> str:
    text = _TAGS.sub("", text or "")
    text = _DASHES.sub("", text).strip()
    return text[:-1] if text.endswith(".") and not text.endswith("...") else text


def _vigente(item: dict, today: date) -> bool:
    fim = item.get("Data_Fim") or "31/12/9999"
    try:
        return datetime.strptime(fim, "%d/%m/%Y").date() >= today
    except ValueError:
        return True


def parse(data: dict, today: date | None = None) -> list[dict]:
    """[{ncm, description}] dos códigos de 8 dígitos vigentes."""
    today = today or date.today()
    by_digits = {}
    for item in data.get("Nomenclaturas", []):
        if _vigente(item, today):
            by_digits[re.sub(r"\D", "", item["Codigo"])] = _clean(item["Descricao"])

    result = []
    for digits, leaf in by_digits.items():
        if len(digits) != 8:
            continue
        # Ancestrais: posicao (4), subposicao (5 e 6), item (7). Capitulo (2)
        # fica de fora - e generico demais ("Residuos e desperdicios...").
        parts = []
        for size in (4, 5, 6, 7):
            desc = by_digits.get(digits[:size])
            if desc and desc not in parts:
                parts.append(desc)
        if leaf not in parts:
            parts.append(leaf)
        result.append({"ncm": digits, "description": " > ".join(parts)[:500]})
    return result


def source_label(data: dict) -> str:
    ato = (data.get("Ato") or "").strip()
    return f"Tabela NCM oficial (Siscomex){' - ' + ato if ato else ''}"[:120]


def apply(db, items: list[dict], source: str) -> dict:
    """Cria/atualiza ncm_classifications. Nunca apaga. Devolve a contagem
    de criados/atualizados/iguais."""
    existing = {row.ncm: row for row in db.query(NcmClassification).all()}
    stats = {"criados": 0, "atualizados": 0, "iguais": 0}
    for item in items:
        row = existing.get(item["ncm"])
        if row is None:
            db.add(NcmClassification(source=source, **item))
            stats["criados"] += 1
        elif row.description != item["description"] or row.source != source:
            row.description, row.source = item["description"], source
            stats["atualizados"] += 1
        else:
            stats["iguais"] += 1
    db.commit()
    return stats


def update_from_siscomex(session_factory, url: str = SISCOMEX_URL) -> dict:
    data = fetch(url)
    db = session_factory()
    try:
        stats = apply(db, parse(data), source_label(data))
    finally:
        db.close()
    stats["vigencia"] = data.get("Data_Ultima_Atualizacao_NCM")
    return stats
