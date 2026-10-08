"""Consulta "estilo ViaCEP": uma URL, uma resposta pronta pra usar.

    GET /v1/BR/SP/23091000         tributos do NCM em SP
    GET /v1/BR/23091000            só os nacionais
    GET /v1/AR/B/7898242031936     por código de barras: produto + tributos
    GET /v1/AR                     o país: subdivisões e tributos

A resposta traz um item por tributo ativo do país, com o nome traduzido.
Sem regra pro NCM, usa a alíquota geral do país (`general_rate: true`);
sem nenhuma das duas, `rate` sai null - o tributo existe, mas ainda não
tem dado.
"""

import re
from datetime import date

from sqlalchemy.orm import Session as DbSession

from app.models import Country, NcmClassification, Product, ProductIdentifier, State, TaxType
from app.services.errors import InvalidDataError, NotFoundError
from app.services.fiscal import FiscalRuleResolver, ResolvedFiscalRule
from app.services.taxes import TaxCatalog, language_of, tax_name


def _country_json(country: Country) -> dict:
    return {
        "code": country.id,
        "name": country.name,
        "language": country.language,
        "subdivision_label": country.subdivision_label,
    }


class TaxLookup:
    def __init__(self, db: DbSession):
        self.db = db
        self.catalog = TaxCatalog(db)
        self.resolver = FiscalRuleResolver(db)

    def country_info(self, country_code: str, lang: str | None) -> dict:
        country = self.catalog.country(country_code)
        language = language_of(country, lang)
        return {
            "country": _country_json(country),
            "lang": language,
            "states": [{"code": s.code, "name": s.name} for s in self.catalog.states(country.id)],
            "taxes": [
                {
                    "code": t.code,
                    "name": tax_name(t, country, language),
                    "local_name": t.name,
                    "level": t.level,
                    "unit": t.unit,
                    "general_rate": t.default_rate,
                    "general_rate_source": t.default_source,
                    "description": t.description,
                }
                for t in self.catalog.tax_types(country.id)
            ],
        }

    def lookup(
        self,
        country_code: str,
        state_code: str | None,
        code: str,
        lang: str | None = None,
        on_date: date | None = None,
        cest: str | None = None,
    ) -> dict:
        country = self.catalog.country(country_code)
        state = self.catalog.state(country, state_code) if state_code else None
        ncm, classification, product, identifier = self._find(code)
        cest = cest or (product.cest if product else None)
        on_date = on_date or date.today()

        rule = self.resolver.resolve(ncm, country.id, state.code if state else None, on_date, cest)
        language = language_of(country, lang)
        result = {
            "ncm": ncm,
            "ncm_description": classification.description if classification else None,
            "country": _country_json(country),
            "state": {"code": state.code, "name": state.name} if state else None,
            "date": on_date.isoformat(),
            "lang": language,
            "taxes": self._taxes(rule, self.catalog.tax_types(country.id), country, language),
            "notes": rule.notes if rule else None,
            "sources": rule.sources if rule else [],
        }
        if product is not None:
            result["product"] = {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "cest": product.cest,
                "barcode": identifier.value,
                "package": identifier.description,
            }
        return result

    def _find(self, code: str):
        """NCM de 8 dígitos ou código de barras -> (ncm, classificação,
        produto, identificador)."""
        digits = re.sub(r"\D", "", code)
        if not digits:
            raise InvalidDataError("Informe um NCM (8 dígitos) ou um código de barras.")

        classification = self.db.get(NcmClassification, digits) if len(digits) == 8 else None
        if classification is not None:
            return digits, classification, None, None

        identifier = self.db.query(ProductIdentifier).filter(ProductIdentifier.value == digits).first()
        if identifier is None:
            raise NotFoundError(f"'{code}' não é um NCM nem um código de barras cadastrado.")
        product = self.db.get(Product, identifier.product_id)
        if not product.ncm:
            raise NotFoundError("Produto encontrado, mas ainda sem NCM cadastrado.")
        return product.ncm, self.db.get(NcmClassification, product.ncm), product, identifier

    @staticmethod
    def _taxes(rule: ResolvedFiscalRule | None, types: list[TaxType], country: Country, lang: str) -> list[dict]:
        items = []
        for tax in types:
            rate = rule.rates.get(tax.code) if rule else None
            source = rule.source if rate is not None else None
            general = rate is None and tax.default_rate is not None
            if general:
                rate, source = tax.default_rate, tax.default_source
            items.append(
                {
                    "code": tax.code,
                    "name": tax_name(tax, country, lang),
                    "local_name": tax.name,
                    "level": tax.level,
                    "unit": tax.unit,
                    "rate": rate,
                    "general_rate": general,
                    "source": source,
                    "description": tax.description,
                }
            )
        return items
