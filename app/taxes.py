"""Tributos por pais: validacao do que se grava numa FiscalRule e montagem
da resposta "estilo ViaCEP" (lista de tributos traduzida, com aliquota,
fonte e observacao).

Um tributo (TaxType) guarda a aliquota numa coluna propria de FiscalRule
(os do Brasil, `column`) ou em `FiscalRule.rates[code]` (qualquer outro).
Quem grava pode mandar tudo em `rates` - ex: {"ICMS": 18, "IPI": 6.5} -
que os codigos com coluna propria sao movidos pra coluna certa aqui.
"""

from app.models_public import Country, FiscalRule, State, TaxType


class TaxValidationError(ValueError):
    pass


def country_tax_types(db, country_id: str, only_active: bool = True) -> list[TaxType]:
    query = db.query(TaxType).filter(TaxType.country_id == country_id)
    if only_active:
        query = query.filter(TaxType.active.is_(True))
    return query.order_by(TaxType.sort_order, TaxType.code).all()


def normalize_rule_payload(db, payload: dict, current: FiscalRule | None = None) -> dict:
    """Confere pais/UF/codigos de `rates` e move os tributos com coluna
    propria pra ela. `current` = regra sendo editada (pais/UF/rates que
    nao vieram no payload saem dela). Levanta TaxValidationError."""
    payload = dict(payload)
    country_id = (payload.get("country") or (current.country if current else None) or "BR").upper()
    if "country" in payload:
        payload["country"] = country_id
    country = db.get(Country, country_id)
    if country is None:
        raise TaxValidationError(f"País '{country_id}' não cadastrado. Veja /countries.")

    uf = payload.get("uf") if "uf" in payload else (current.uf if current else None)
    if uf:
        uf = uf.strip().upper()
        if "uf" in payload:
            payload["uf"] = uf
        exists = db.query(State).filter(State.country_id == country_id, State.code == uf).first()
        if exists is None:
            label = country.subdivision_label or "UF"
            raise TaxValidationError(f"{label} '{uf}' não existe em {country.name}. Veja /countries/{country_id}/states.")

    if payload.get("rates") is None:
        return payload
    types = {t.code.upper(): t for t in country_tax_types(db, country_id, only_active=False)}
    rates = dict(current.rates or {}) if current is not None else {}
    for code, value in payload["rates"].items():
        code = code.strip().upper()
        tax = types.get(code)
        if tax is None:
            known = ", ".join(sorted(types)) or "nenhum"
            raise TaxValidationError(f"Tributo '{code}' não existe em {country.name} (cadastrados: {known}).")
        if value is not None and value < 0:
            raise TaxValidationError(f"Alíquota de {code} não pode ser negativa.")
        if tax.column:
            payload[tax.column] = value
        elif value is None:
            rates.pop(code, None)
        else:
            rates[code] = value
    payload["rates"] = rates or None
    return payload


def rule_value(rule: FiscalRule | None, tax: TaxType):
    if rule is None:
        return None
    if tax.column:
        return getattr(rule, tax.column, None)
    return (rule.rates or {}).get(tax.code)


def language_of(country: Country, lang: str | None) -> str:
    """"pt", "es", "en"... - o pedido (?lang=) ou o idioma do pais."""
    chosen = (lang or country.language or "pt").strip()
    return chosen.split("-")[0].lower()


def tax_name(tax: TaxType, country: Country, lang: str) -> str:
    if lang == language_of(country, None):
        return tax.name
    return (tax.translations or {}).get(lang) or tax.name


def build_taxes(rule: FiscalRule | None, types: list[TaxType], country: Country, lang: str) -> list[dict]:
    """Um item por tributo ativo do pais, na ordem do cadastro. Sem regra
    pro NCM, usa a aliquota geral do tributo (`default_rate`) e marca
    `general_rate: true`; sem nenhuma das duas, `rate` sai null - quem
    consome sabe que o tributo existe mas ainda nao tem dado."""
    items = []
    for tax in types:
        value = rule_value(rule, tax)
        general = False
        source = rule.source if (rule is not None and value is not None) else None
        if value is None and tax.default_rate is not None:
            value, general, source = tax.default_rate, True, tax.default_source
        items.append(
            {
                "code": tax.code,
                "name": tax_name(tax, country, lang),
                "local_name": tax.name,
                "level": tax.level,
                "unit": tax.unit,
                "rate": value,
                "general_rate": general,
                "source": source,
                "description": tax.description,
            }
        )
    return items
