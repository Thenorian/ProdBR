"""
Dados oficiais do governo, baixados sozinhos uma vez por dia:

    NCM  tabela vigente do Portal Único Siscomex (JSON público, sem login)
    IPI  TIPI da Receita Federal (planilha tipi.xlsx)
    II   TEC do Mercosul publicada pelo MDIC/Gecex (Anexo I = TEC, Anexo II = exceções do Brasil)

Ficam de fora de propósito os tributos que não dependem só do NCM: ICMS e FCP (cada UF),
CST/CSOSN e PIS/COFINS (regime da empresa). Esses continuam sendo regras da comunidade.

As planilhas são lidas com zipfile + ElementTree (um .xlsx é um zip de XMLs),
sem nenhuma biblioteca externa.
"""
import json
import re
import urllib.request
import zipfile
from io import BytesIO
from xml.etree import ElementTree

SISCOMEX_NCM_URL = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"
TIPI_URL = "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/documentos-e-arquivos/tipi.xlsx/@@download/file"
# O link da planilha da TEC muda a cada resolução, então é achado nesta página.
TEC_PAGE_URL = "https://www.gov.br/mdic/pt-br/assuntos/camex/se-camex/strat/tarifas/vigentes"
TEC_SPREADSHEET_LINK = re.compile(r'href="([^"]*anexos-i-a-x[^"]*\.xlsx)"')

USER_AGENT = "ProdBR/1.0 (+https://github.com/Thenorian/ProdBR)"
DOWNLOAD_TIMEOUT_IN_SECONDS = 120

SPREADSHEET_NAMESPACE = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RELATIONSHIP_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
NCM_WITH_DOTS = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
COLUMN_LETTERS = re.compile(r"^([A-Z]+)")


def download(url, timeout=DOWNLOAD_TIMEOUT_IN_SECONDS):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_ncm_table():
    """JSON da tabela NCM vigente, no mesmo formato do arquivo baixado à mão no Portal Único."""
    return json.loads(download(SISCOMEX_NCM_URL).decode("utf-8"))


def download_federal_rates():
    """
    Baixa TIPI e TEC e devolve tudo pronto para gravar:

        {
            "ipi_by_ncm":   {"22030000": 3.9, "01012100": None, ...}   None = NT (não tributado)
            "ipi_exceptions_by_ncm": {"23091000": ["Ex 01 (Para cães e gatos): 6,5%"]},
            "ii_by_ncm":    {"22030000": 16.0, ...},
            "source":       "Oficial: TIPI (Decreto nº ...) + TEC (Resolução Gecex nº 926/2026)",
        }
    """
    ipi_by_ncm, ipi_exceptions_by_ncm, tipi_act = read_tipi(read_spreadsheet(download(TIPI_URL)))

    tec_page = download(TEC_PAGE_URL, timeout=60).decode("utf-8", "replace")
    tec_link = TEC_SPREADSHEET_LINK.search(tec_page)
    if not tec_link:
        raise RuntimeError("Planilha da TEC não encontrada na página do MDIC.")
    ii_by_ncm, tec_act = read_tec(read_spreadsheet(download(tec_link.group(1))))

    return {
        "ipi_by_ncm": ipi_by_ncm,
        "ipi_exceptions_by_ncm": ipi_exceptions_by_ncm,
        "ii_by_ncm": ii_by_ncm,
        "source": official_source_label(tipi_act, tec_act),
    }


OFFICIAL_SOURCE_PREFIX = "Oficial: "


def official_source_label(tipi_act, tec_act):
    return f"{OFFICIAL_SOURCE_PREFIX}TIPI ({tipi_act or 'Receita Federal'}) + TEC ({tec_act or 'Gecex'})"[:255]


# Planilha .xlsx

def read_spreadsheet(xlsx_bytes):
    """
    Devolve {nome da aba: linhas}. Cada linha é uma lista com o valor de cada coluna
    na posição certa (texto, número ou None para célula vazia).
    """
    with zipfile.ZipFile(BytesIO(xlsx_bytes)) as xlsx:
        shared_texts = read_shared_texts(xlsx)
        sheet_file_by_id = {
            relationship.get("Id"): relationship.get("Target")
            for relationship in ElementTree.fromstring(xlsx.read("xl/_rels/workbook.xml.rels"))
        }

        sheets = {}
        workbook = ElementTree.fromstring(xlsx.read("xl/workbook.xml"))
        for sheet in workbook.find("m:sheets", SPREADSHEET_NAMESPACE):
            target = sheet_file_by_id[sheet.get(RELATIONSHIP_ID)].lstrip("/")
            sheet_path = target if target.startswith("xl/") else f"xl/{target}"
            sheets[sheet.get("name")] = read_sheet_rows(xlsx.read(sheet_path), shared_texts)

        return sheets


def read_shared_texts(xlsx):
    """O .xlsx guarda os textos repetidos numa lista à parte; as células apontam para a posição."""
    if "xl/sharedStrings.xml" not in xlsx.namelist():
        return []

    texts = []
    for item in ElementTree.fromstring(xlsx.read("xl/sharedStrings.xml")).findall("m:si", SPREADSHEET_NAMESPACE):
        texts.append("".join(part.text or "" for part in item.iter(f"{{{SPREADSHEET_NAMESPACE['m']}}}t")))
    return texts


def read_sheet_rows(sheet_xml, shared_texts):
    rows = []
    for row in ElementTree.fromstring(sheet_xml).iter(f"{{{SPREADSHEET_NAMESPACE['m']}}}row"):
        values = []
        for cell in row.findall("m:c", SPREADSHEET_NAMESPACE):
            column = column_index(cell.get("r"))
            values.extend([None] * (column - len(values) + 1))
            values[column] = cell_value(cell, shared_texts)
        rows.append(values)
    return rows


def cell_value(cell, shared_texts):
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(part.text or "" for part in cell.iter(f"{{{SPREADSHEET_NAMESPACE['m']}}}t"))

    raw_value = cell.findtext("m:v", default=None, namespaces=SPREADSHEET_NAMESPACE)
    if raw_value is None:
        return None
    if cell_type == "s":
        return shared_texts[int(raw_value)]
    if cell_type in ("str", "b", "e"):
        return raw_value
    return float(raw_value)


def column_index(cell_reference):
    """ "A1" -> 0, "C7" -> 2, "AA3" -> 26 """
    letters = COLUMN_LETTERS.match(cell_reference).group(1)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def cell(row, column):
    return row[column] if column < len(row) else None


def cell_text(row, column):
    value = cell(row, column)
    return "" if value is None else str(value).strip()


def rate_from(value):
    """
    12.6, "12,6" ou "16BIT" (a TEC cola a sigla de bens de informática na alíquota) -> 12.6 / 16.0.
    None se não tiver número.
    """
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)", str(value or ""))
    return round(float(match.group(1).replace(",", ".")), 2) if match else None


def only_digits(text):
    return re.sub(r"\D", "", str(text or ""))


# TIPI (IPI)

def read_tipi(sheets):
    """
    Colunas da TIPI: A = NCM, B = Ex, C = descrição, D = alíquota ("NT" = não tributado).

    Linha com Ex é uma exceção para um produto específico dentro do NCM (ex: ração em geral 0%,
    mas a de cães e gatos 6,5%). A alíquota do NCM é a da linha sem Ex; as exceções vão nas observações.
    """
    rows = next(iter(sheets.values()))
    ipi_by_ncm = {}
    exceptions_by_ncm = {}
    latest_act = ""

    for row in rows:
        first_column = cell_text(row, 0)
        if first_column.startswith("Atualiza"):
            acts = [line.strip() for line in first_column.splitlines() if line.strip()][1:]
            latest_act = acts[-1] if acts else ""
        if not NCM_WITH_DOTS.match(first_column):
            continue

        written_rate = cell_text(row, 3).upper()
        not_taxed = written_rate == "NT"
        rate = None if not_taxed else rate_from(written_rate)
        if not not_taxed and rate is None:
            continue

        ncm = only_digits(first_column)
        exception_number = cell_text(row, 1)
        if exception_number:
            exception_number = exception_number.removesuffix(".0").zfill(2)
            description = " ".join(cell_text(row, 2).split()).rstrip(" .")
            exceptions_by_ncm.setdefault(ncm, []).append(f"Ex {exception_number} ({description}): {rate_as_text(rate)}")
        else:
            ipi_by_ncm[ncm] = rate

    return ipi_by_ncm, exceptions_by_ncm, short_act_name(latest_act)


def rate_as_text(rate):
    return "NT" if rate is None else f"{rate:g}%".replace(".", ",")


# TEC (II)

def read_tec(sheets):
    """
    Anexo I: coluna C = alíquota da TEC do Mercosul.
    Anexo II: coluna F = alíquota que o Brasil aplica quando é diferente da TEC (prevalece).
    """
    rows_by_annex = {name.split(" - ")[0].strip(): rows for name, rows in sheets.items()}
    ii_by_ncm = {}
    act = ""

    for row in rows_by_annex.get("Anexo I", []):
        first_column = cell_text(row, 0)
        if "Atualizado" in first_column and not act:
            act = first_column
        rate = rate_from(cell(row, 2))
        if NCM_WITH_DOTS.match(first_column) and rate is not None:
            ii_by_ncm[only_digits(first_column)] = rate

    for row in rows_by_annex.get("Anexo II", []):
        first_column = cell_text(row, 0)
        rate = rate_from(cell(row, 5))
        if NCM_WITH_DOTS.match(first_column) and rate is not None:
            ii_by_ncm[only_digits(first_column)] = rate

    return ii_by_ncm, short_act_name(act)


def short_act_name(text):
    """ "*Atualizado até Resolução Gecex nº 926, de 24 de junho de 2026" -> "Resolução Gecex nº 926/2026" """
    text = re.sub(r"^\W*Atualizad[oa]\s+at[eé]\s+(a\s+)?", "", text.strip(), flags=re.IGNORECASE)
    match = re.match(r"(.+?n[ºo°]?\s*[\d.]+),?\s.*?(\d{4})\b", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return text[:50]
