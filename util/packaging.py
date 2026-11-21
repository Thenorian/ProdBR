"""
Lê o texto da embalagem de um código de barras ("15 kg", "10,1kg", "6x350ml", "Cx c/ 12 un")
e transforma em campos padronizados: quantidade líquida, unidade e itens por embalagem.

Regra: só preenche quando dá para ter certeza. Na dúvida (duas medidas diferentes,
"1.000 g" que pode ser mil ou um, unidade desconhecida) devolve vazio. O texto original
continua guardado e a comunidade completa depois. Melhor faltar do que gravar errado
numa base que outros sistemas usam para emitir nota.
"""
import re

# Como a unidade aparece escrita  ->  unidade padronizada.
UNIT_BY_WRITTEN_FORM = {
    "mg": "mg",
    "g": "g", "gr": "g", "grs": "g", "gramas": "g",
    "kg": "kg", "kgs": "kg", "quilo": "kg", "quilos": "kg",
    "ml": "ml",
    "l": "l", "lt": "l", "lts": "l", "litro": "l", "litros": "l",
    "un": "un", "und": "un", "unid": "un", "unidade": "un", "unidades": "un",
}
VALID_UNITS = sorted(set(UNIT_BY_WRITTEN_FORM.values()))

NUMBER = r"\d+(?:[.,]\d+)?"
WRITTEN_UNIT = "(?:" + "|".join(sorted(UNIT_BY_WRITTEN_FORM, key=len, reverse=True)) + ")"

# "6x350ml", "12 x 1 l"
MULTIPACK = re.compile(rf"(?<![\d.,])(\d+)\s*[x×]\s*({NUMBER})\s*({WRITTEN_UNIT})(?![a-z])", re.IGNORECASE)
# "15 kg", "500ml"
SINGLE_MEASURE = re.compile(rf"(?<![\d.,])({NUMBER})\s*({WRITTEN_UNIT})(?![a-z])", re.IGNORECASE)
# "c/ 12", "com 24 unidades"
ITEM_COUNT = re.compile(r"(?:c/|com)\s*(\d+)\s*(?:un|und|unid|unidades?)?(?![a-z])", re.IGNORECASE)
# "1.000 g": o ponto pode ser de milhar ou decimal, então não arrisca.
AMBIGUOUS_THOUSANDS = re.compile(r"\d{1,3}\.\d{3}(?!\d)")


def read_package_text(text):
    """
    Devolve só o que deu para entender com certeza.

        read_package_text("6x350ml")     ->  {"units_per_pack": 6, "net_quantity": 350.0, "net_unit": "ml"}
        read_package_text("10,1kg")      ->  {"net_quantity": 10.1, "net_unit": "kg"}
        read_package_text("Cx c/ 12 un") ->  {"units_per_pack": 12, "net_quantity": 12.0, "net_unit": "un"}
        read_package_text("1.000 g")     ->  {}
    """
    if not text or not text.strip():
        return {}

    text = text.strip().lower()
    if AMBIGUOUS_THOUSANDS.search(text):
        return {}

    multipacks = MULTIPACK.findall(text)
    if len(multipacks) > 1:
        return {}
    if len(multipacks) == 1:
        count, quantity, unit = multipacks[0]
        text_without_multipack = MULTIPACK.sub(" ", text)
        if SINGLE_MEASURE.search(text_without_multipack):
            return {}  # "6x350ml + 1 l": mais de uma medida
        return {"units_per_pack": int(count), "net_quantity": to_number(quantity), "net_unit": standard_unit(unit)}

    measures = SINGLE_MEASURE.findall(text)
    weight_or_volume = [(quantity, unit) for quantity, unit in measures if standard_unit(unit) != "un"]
    unit_counts = [quantity for quantity, unit in measures if standard_unit(unit) == "un"]

    if len(weight_or_volume) > 1:
        return {}

    result = {}
    if len(weight_or_volume) == 1:
        quantity, unit = weight_or_volume[0]
        result = {"net_quantity": to_number(quantity), "net_unit": standard_unit(unit)}

    item_count_match = ITEM_COUNT.search(text)
    if item_count_match:
        item_count = int(item_count_match.group(1))
    elif len(unit_counts) == 1:
        item_count = int(to_number(unit_counts[0]))
    else:
        item_count = None

    if item_count is not None:
        if not result:
            return {"units_per_pack": item_count, "net_quantity": float(item_count), "net_unit": "un"}
        result["units_per_pack"] = item_count

    return result


def to_number(text):
    return float(text.replace(",", "."))


def standard_unit(written_unit):
    """ "Litros" -> "l". None se a unidade não for conhecida. """
    return UNIT_BY_WRITTEN_FORM.get(str(written_unit).strip().lower())
