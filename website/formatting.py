"""Textos e formatos usados nas páginas: datas, dinheiro e os nomes em português dos códigos."""

ORIGIN_NAMES = {
    0: "Nacional",
    1: "Estrangeira, importação direta",
    2: "Estrangeira, adquirida no mercado interno",
    3: "Nacional, com mais de 40% de conteúdo importado",
    4: "Nacional, produzida conforme processos básicos",
    5: "Nacional, com até 40% de conteúdo importado",
    6: "Estrangeira, importação direta, sem similar nacional",
    7: "Estrangeira, mercado interno, sem similar nacional",
    8: "Nacional, com mais de 70% de conteúdo importado",
}

TAX_REGIME_NAMES = {
    "simples_nacional": "Simples Nacional",
    "lucro_presumido": "Lucro Presumido",
    "lucro_real": "Lucro Real",
}

FIELD_NAMES = {
    "name": "Nome",
    "brand": "Marca",
    "manufacturer": "Fabricante",
    "manufacturer_code": "Código do fabricante",
    "description": "Descrição",
    "category_id": "Categoria",
    "ncm_code": "NCM",
    "ncm": "NCM",
    "cest": "CEST",
    "origin": "Origem",
    "commercial_unit": "Unidade",
    "source": "Fonte",
    "barcodes": "Códigos de barras",
    "uf": "UF",
    "tax_regime": "Regime",
}

ACTION_NAMES = {"create": "criou", "update": "alterou", "delete": "removeu"}

# Níveis públicos de contribuidor, pela quantidade de campos alterados.
CONTRIBUTOR_LEVELS = (
    (1_000_000, "Supremo"),
    (10_000, "Mestre"),
    (1_000, "Renomado"),
    (100, "Editor"),
    (0, "Iniciante"),
)


def brazilian_date(value):
    """ "2026-11-21 17:42:17" -> "21/11/2026" """
    if not value:
        return ""
    year, month, day = str(value)[:10].split("-")
    return f"{day}/{month}/{year}"


def money(value):
    """ 1234.5 -> "R$ 1.234,50" """
    if value is None:
        return ""
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def percent(value):
    """ 7.6 -> "7,6%" """
    if value is None:
        return "—"
    return f"{value:g}%".replace(".", ",")


def origin_name(code):
    return ORIGIN_NAMES.get(code, "")


def tax_regime_name(code):
    return TAX_REGIME_NAMES.get(code, "Todos")


def field_name(field):
    return FIELD_NAMES.get(field, field or "")


def action_name(action):
    return ACTION_NAMES.get(action, action)


def contributor_level(edit_count):
    for minimum_edits, level in CONTRIBUTOR_LEVELS:
        if (edit_count or 0) >= minimum_edits:
            return level
    return "Iniciante"


def group_revisions(revisions):
    """
    O histórico tem uma linha por campo. Para mostrar, junta as linhas da mesma alteração
    (mesmo item, pessoa, ação e motivo, em sequência) num grupo só.

        [criou Nome, criou Marca, criou NCM]  ->  [{"action": "create", "changes": [Nome, Marca, NCM]}]
    """
    groups = []

    for revision in revisions:
        key = (revision["entity_type"], revision["entity_id"], revision["action"], revision["contributor"], revision["reason"])
        if groups and groups[-1]["key"] == key:
            groups[-1]["changes"].append(revision)
            continue

        groups.append({
            "key": key,
            "entity_id": revision["entity_id"],
            "product_name": revision.get("product_name"),
            "contributor": revision["contributor"],
            "action": revision["action"],
            "reason": revision["reason"],
            "created_at": revision["created_at"],
            "changes": [revision],
        })

    return groups


def register_filters(jinja_environment):
    jinja_environment.filters["agrupar"] = group_revisions
    jinja_environment.filters["data_br"] = brazilian_date
    jinja_environment.filters["reais"] = money
    jinja_environment.filters["porcento"] = percent
    jinja_environment.filters["origem"] = origin_name
    jinja_environment.filters["regime"] = tax_regime_name
    jinja_environment.filters["campo"] = field_name
    jinja_environment.filters["acao"] = action_name
    jinja_environment.filters["nivel"] = contributor_level
