"""Textos e formatos usados nas páginas: datas, dinheiro e os nomes em português dos códigos."""
from database.contributor import contributor_level

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
    "category": "Categoria",
    "path": "Categoria",
    "uf": "UF",
    "tax_regime": "Regime",
}

ACTION_NAMES = {"create": "criou", "update": "alterou", "delete": "removeu"}

PENDING_ACTION_NAMES = {
    "create_product": "Novo produto",
    "update_product": "Alteração de produto",
    "create_fiscal_rule": "Nova regra fiscal",
    "update_fiscal_rule": "Alteração de regra fiscal",
    "create_category": "Nova categoria",
    "update_category": "Alteração de categoria",
    "delete_category": "Apagar categoria",
}



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


def number_to_copy(value, decimals=None):
    """
    Número do jeito que se digita num ERP brasileiro: vírgula decimal, sem símbolo.

        number_to_copy(1.65)       ->  "1,65"
        number_to_copy(18.0)       ->  "18"
        number_to_copy(93.25, 2)   ->  "93,25"
    """
    if value is None:
        return ""
    text = f"{value:.{decimals}f}" if decimals is not None else f"{value:g}"
    return text.replace(".", ",")


def origin_name(code):
    return ORIGIN_NAMES.get(code, "")


def tax_regime_name(code):
    return TAX_REGIME_NAMES.get(code, "Todos")


def field_name(field):
    return FIELD_NAMES.get(field, field or "")


def action_name(action):
    return ACTION_NAMES.get(action, action)


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


def pending_action_name(action):
    return PENDING_ACTION_NAMES.get(action, action)


def proposed_value(value):
    """
    Valor que alguém propôs na fila, em texto.

        None                                              ->  "vazio"
        ["7891000100103", {"barcode": "7896...", ...}]    ->  "7891000100103, 7896..."
    """
    if value is None or value == "":
        return "vazio"
    if isinstance(value, list):
        return ", ".join(item["barcode"] if isinstance(item, dict) else str(item) for item in value) or "vazio"
    return str(value)


def register_filters(jinja_environment):
    jinja_environment.filters["agrupar"] = group_revisions
    jinja_environment.filters["data_br"] = brazilian_date
    jinja_environment.filters["reais"] = money
    jinja_environment.filters["porcento"] = percent
    jinja_environment.filters["para_copiar"] = number_to_copy
    jinja_environment.filters["origem"] = origin_name
    jinja_environment.filters["regime"] = tax_regime_name
    jinja_environment.filters["campo"] = field_name
    jinja_environment.filters["acao"] = action_name
    jinja_environment.filters["nivel"] = contributor_level
    jinja_environment.filters["acao_da_fila"] = pending_action_name
    jinja_environment.filters["valor_proposto"] = proposed_value
