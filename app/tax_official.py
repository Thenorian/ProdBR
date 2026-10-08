"""Tributos federais oficiais por NCM -> fiscal_rules (regra nacional, BR).

Duas fontes do governo, as mesmas planilhas que contador baixa a mao:

- IPI: TIPI da Receita Federal (tipi.xlsx). Aliquota por NCM ou "NT"
  (nao tributado - fora do campo do IPI, diferente de aliquota zero).
- II: TEC do Mercosul publicada pelo MDIC/Gecex (Anexo I = aliquota da TEC,
  Anexo II = aliquota que o Brasil aplica quando e diferente da TEC). O
  link muda a cada atualizacao, entao e achado na pagina "Tarifas vigentes".

Fica de fora de proposito o que NAO depende so do NCM: ICMS/FCP (cada
UF), CST/CSOSN (regime da empresa + operacao), PIS/COFINS (regime
cumulativo/nao cumulativo/Simples), quotas e Ex-tarifarios (condicionais).
Isso continua sendo regra por UF cadastrada pela comunidade.

Cada NCM ganha UMA regra nacional "Oficial: TIPI ... + TEC ...". Quando a
aliquota muda, a regra antiga e encerrada (valid_until) e nasce outra -
o historico de aliquotas fica consultavel. Nunca apaga nada.

Leitor de xlsx feito com zipfile + ElementTree de proposito: zero
dependencia nova pra quem for hospedar uma copia.
"""

import re
import urllib.request
import zipfile
from datetime import date, timedelta
from io import BytesIO
from xml.etree import ElementTree

TIPI_URL = "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/documentos-e-arquivos/tipi.xlsx/@@download/file"
TEC_PAGE_URL = "https://www.gov.br/mdic/pt-br/assuntos/camex/se-camex/strat/tarifas/vigentes"
USER_AGENT = "ProdBR/1.0 (+https://github.com/Thenorian/ProdBR)"
SOURCE_PREFIX = "Oficial: "

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_NCM8 = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
_COL = re.compile(r"^([A-Z]+)")


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --- leitor minimo de xlsx -------------------------------------------------


def _col_index(ref: str) -> int:
    letters = _COL.match(ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(data: bytes) -> dict[str, list[list]]:
    """{nome da aba: linhas}, cada linha uma lista de valores (str, float
    ou None) na posicao da coluna."""
    with zipfile.ZipFile(BytesIO(data)) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ElementTree.fromstring(zf.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        }
        sheets = {}
        for sheet in ElementTree.fromstring(zf.read("xl/workbook.xml")).find("m:sheets", _NS):
            target = rels[sheet.get(_REL_NS)].lstrip("/")
            path = target if target.startswith("xl/") else f"xl/{target}"
            rows = []
            for row in ElementTree.fromstring(zf.read(path)).iter(f"{{{_NS['m']}}}row"):
                values = []
                for cell in row.findall("m:c", _NS):
                    idx = _col_index(cell.get("r"))
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(f"{{{_NS['m']}}}t"))
                    else:
                        raw = cell.findtext("m:v", default=None, namespaces=_NS)
                        if raw is None:
                            value = None
                        elif kind == "s":
                            value = shared[int(raw)]
                        elif kind in ("str", "b", "e"):
                            value = raw
                        else:
                            value = float(raw)
                    values.extend([None] * (idx - len(values) + 1))
                    values[idx] = value
                rows.append(values)
            sheets[sheet.get("name")] = rows
        return sheets


def _cell(row: list, idx: int):
    return row[idx] if idx < len(row) else None


def _rate(value) -> float | None:
    """12.6, "12,6" ou "16BIT"/"14BK" (TEC marca bens de informatica e de
    capital colando a sigla na aliquota) -> float."""
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)", str(value or ""))
    return round(float(match.group(1).replace(",", ".")), 2) if match else None


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _digits(code) -> str:
    return re.sub(r"\D", "", str(code or ""))


# --- TIPI (IPI) -------------------------------------------------------------


def parse_tipi(sheets: dict) -> tuple[dict[str, float | None], dict[str, list[str]], str]:
    """({ncm: aliquota ou None se NT}, {ncm: ["Ex 01 (Para caes e gatos): 6,5%"]},
    ato mais recente). Linhas de Ex sao excecoes para um produto especifico
    dentro do NCM (ex: racao completa e 0%, mas a de caes e gatos e 6,5%) -
    a aliquota do NCM e a da linha sem Ex; os Ex vao pra observacao."""
    rows = next(iter(sheets.values()))
    rates: dict[str, float | None] = {}
    exes: dict[str, list[str]] = {}
    ato = ""
    for row in rows:
        first = _text(_cell(row, 0))
        if first.startswith("Atualiza"):
            acts = [line.strip() for line in first.splitlines() if line.strip()][1:]
            ato = acts[-1] if acts else ""
        if not _NCM8.match(first):
            continue
        raw = _text(_cell(row, 3)).upper()
        rate = None if raw == "NT" else _rate(raw)
        if raw != "NT" and rate is None:
            continue
        ex = _text(_cell(row, 1))
        if ex:
            num = ex[:-2] if ex.endswith(".0") else ex
            desc = re.sub(r"\s+", " ", _text(_cell(row, 2))).rstrip(" .")
            exes.setdefault(_digits(first), []).append(f"Ex {num.zfill(2)} ({desc}): {_fmt(rate)}")
        else:
            rates[_digits(first)] = rate
    return rates, exes, _short_act(ato)


def _fmt(rate: float | None) -> str:
    return "NT" if rate is None else f"{rate:g}%".replace(".", ",")


# --- TEC (II) ---------------------------------------------------------------


def tec_url(page_html: str) -> str | None:
    match = re.search(r'href="([^"]*anexos-i-a-x[^"]*\.xlsx)"', page_html)
    return match.group(1) if match else None


def parse_tec(sheets: dict) -> tuple[dict[str, float], str]:
    """({ncm: aliquota de II que o Brasil aplica}, ato). Anexo I = TEC;
    Anexo II (quando o Brasil aplica outra aliquota) prevalece."""
    by_prefix = {name.split(" - ")[0].strip(): rows for name, rows in sheets.items()}
    rates: dict[str, float] = {}
    ato = ""
    for row in by_prefix.get("Anexo I", []):
        first = _text(_cell(row, 0))
        if "Atualizado" in first and not ato:
            ato = first
        if _NCM8.match(first) and (rate := _rate(_cell(row, 2))) is not None:
            rates[_digits(first)] = rate
    for row in by_prefix.get("Anexo II", []):
        first = _text(_cell(row, 0))
        if _NCM8.match(first) and (rate := _rate(_cell(row, 5))) is not None:
            rates[_digits(first)] = rate
    return rates, _short_act(ato)


def _short_act(text: str) -> str:
    """'*Atualizado ate Resolucao Gecex n 926, de 24 de junho de 2026' ->
    'Resolucao Gecex n 926/2026'."""
    text = re.sub(r"^\W*Atualizad[oa]\s+at[eé]\s+(a\s+)?", "", text.strip(), flags=re.I)
    match = re.match(r"(.+?n[ºo°]?\s*[\d.]+),?\s.*?(\d{4})\b", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return text[:50]


# --- gravacao ---------------------------------------------------------------


def source_label(tipi_act: str, tec_act: str) -> str:
    return f"{SOURCE_PREFIX}TIPI ({tipi_act or 'Receita Federal'}) + TEC ({tec_act or 'Gecex'})"[:120]


def _notes(ncm: str, ipi: dict, ipi_exes: dict) -> str | None:
    parts = []
    if ncm in ipi and ipi[ncm] is None:
        parts.append("IPI: NT (não tributado - fora do campo de incidência do IPI).")
    if ipi_exes.get(ncm):
        parts.append("IPI diferente para: " + "; ".join(ipi_exes[ncm]) + ".")
    text = " ".join(parts)
    return (text[:497] + "...") if len(text) > 500 else (text or None)


def apply(db, ipi: dict, ipi_exes: dict, ii: dict, source: str, today: date | None = None) -> dict:
    """Uma regra nacional oficial por NCM com IPI e II. `ipi` traz todo
    NCM da TIPI (None = NT). So mexe nas regras cujo source comeca com
    SOURCE_PREFIX - as cadastradas pela comunidade ficam intactas."""
    from app.models_public import FiscalRule

    today = today or date.today()
    current = {
        rule.ncm: rule
        for rule in db.query(FiscalRule).filter(
            FiscalRule.source.like(f"{SOURCE_PREFIX}%"),
            FiscalRule.country == "BR",
            FiscalRule.uf.is_(None),
            FiscalRule.cest.is_(None),
            FiscalRule.valid_until.is_(None),
        )
    }
    stats = {"criadas": 0, "alteradas": 0, "iguais": 0}
    for ncm in sorted(set(ipi) | set(ii)):
        values = {"ipi_rate": ipi.get(ncm), "ii_rate": ii.get(ncm), "notes": _notes(ncm, ipi, ipi_exes)}
        rule = current.get(ncm)
        if rule is not None and all(getattr(rule, k) == v for k, v in values.items()):
            if rule.source != source:
                rule.source = source
            stats["iguais"] += 1
            continue
        if rule is not None and rule.valid_from >= today:
            for key, value in values.items():
                setattr(rule, key, value)
            rule.source = source
            stats["alteradas"] += 1
            continue
        if rule is not None:
            rule.valid_until = today - timedelta(days=1)
            stats["alteradas"] += 1
        else:
            stats["criadas"] += 1
        db.add(FiscalRule(ncm=ncm, country="BR", uf=None, cest=None, valid_from=today, source=source, **values))
    db.commit()
    return stats


def update_from_official(session_factory) -> dict:
    tipi_rates, tipi_exes, tipi_act = parse_tipi(read_xlsx(_get(TIPI_URL)))
    url = tec_url(_get(TEC_PAGE_URL, timeout=60).decode("utf-8", "replace"))
    if not url:
        raise RuntimeError("Planilha da TEC não encontrada na página do MDIC.")
    tec_rates, tec_act = parse_tec(read_xlsx(_get(url)))
    db = session_factory()
    try:
        stats = apply(db, tipi_rates, tipi_exes, tec_rates, source_label(tipi_act, tec_act))
    finally:
        db.close()
    stats["ipi"], stats["ii"] = len(tipi_rates), len(tec_rates)
    return stats
