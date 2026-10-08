"""Leitura da descricao de embalagem de um identificador (ex: "15 kg",
"10,1kg", "6x350ml", "Cx c/ 12 un") para campos padronizados - quantidade
liquida, unidade e itens por embalagem.

A mesma informacao aparece de muitos jeitos (virgula ou ponto, maiuscula,
com/sem espaco, "lt"/"litros"...). Regra: so preenche quando da pra ter
certeza. Na duvida (duas quantidades diferentes, separador de milhar
ambiguo, unidade desconhecida) devolve vazio - o texto original continua
guardado em `description` e a comunidade completa depois. Melhor faltar
do que gravar errado numa base que outros sistemas usam pra emitir nota.
"""

import re

# Unidade escrita -> unidade padronizada.
UNITS = {
    "mg": "mg",
    "g": "g",
    "gr": "g",
    "grs": "g",
    "gramas": "g",
    "kg": "kg",
    "kgs": "kg",
    "quilo": "kg",
    "quilos": "kg",
    "ml": "ml",
    "l": "l",
    "lt": "l",
    "lts": "l",
    "litro": "l",
    "litros": "l",
    "un": "un",
    "und": "un",
    "unid": "un",
    "unidade": "un",
    "unidades": "un",
}
VALID_UNITS = sorted(set(UNITS.values()))

_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")"
_MULTI = re.compile(rf"(?<![\d.,])(\d+)\s*[x×]\s*({_NUM})\s*({_UNIT})(?![a-z])", re.I)
_SINGLE = re.compile(rf"(?<![\d.,])({_NUM})\s*({_UNIT})(?![a-z])", re.I)
_COUNT = re.compile(r"(?:c/|com)\s*(\d+)\s*(?:un|und|unid|unidades?)?(?![a-z])", re.I)
# "1.000 g" - ponto pode ser milhar ou decimal; nao arrisca.
_AMBIGUOUS_THOUSANDS = re.compile(r"\d{1,3}\.\d{3}(?!\d)")


def _to_number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_package(text: str | None) -> dict:
    """{} quando nao da pra ter certeza; senao net_quantity/net_unit e/ou
    units_per_pack."""
    if not text or not text.strip():
        return {}
    t = text.strip().lower()
    if _AMBIGUOUS_THOUSANDS.search(t):
        return {}

    multi = _MULTI.findall(t)
    if len(multi) == 1:
        count, qty, unit = multi[0]
        rest = _MULTI.sub(" ", t)
        if _SINGLE.search(rest):
            return {}  # "6x350ml + 1 l" - mais de uma medida
        return {"units_per_pack": int(count), "net_quantity": _to_number(qty), "net_unit": UNITS[unit.lower()]}
    if len(multi) > 1:
        return {}

    singles = [(q, u) for q, u in _SINGLE.findall(t) if UNITS[u.lower()] != "un"]
    count_match = _COUNT.search(t)
    unit_count = [q for q, u in _SINGLE.findall(t) if UNITS[u.lower()] == "un"]

    result: dict = {}
    if len(singles) == 1:
        qty, unit = singles[0]
        result = {"net_quantity": _to_number(qty), "net_unit": UNITS[unit.lower()]}
    elif len(singles) > 1:
        return {}

    count = count_match.group(1) if count_match else (unit_count[0] if len(unit_count) == 1 else None)
    if count is not None:
        if not result:
            # "Cx c/ 12 un" - so contagem, sem medida por item.
            return {"units_per_pack": int(count), "net_quantity": float(count), "net_unit": "un"}
        result["units_per_pack"] = int(count)
    return result


PACKAGE_FIELDS = ("description", "net_quantity", "net_unit", "units_per_pack")


def package_fields(given: dict) -> dict:
    """Campos de embalagem pra gravar: o que veio explicito vale; o que
    faltar e lido da `description` (so com certeza). So devolve chaves que
    tem valor - nunca apaga um campo que o usuario nao mandou."""
    result = {k: given[k] for k in PACKAGE_FIELDS if given.get(k) is not None}
    if "description" in result:
        result["description"] = result["description"].strip()
        for key, value in parse_package(result["description"]).items():
            result.setdefault(key, value)
    unit = result.get("net_unit")
    if unit is not None:
        normalized = UNITS.get(str(unit).strip().lower())
        if normalized is None:
            raise ValueError(f"Unidade invalida: '{unit}'. Use uma de: {', '.join(VALID_UNITS)}.")
        result["net_unit"] = normalized
    return result
