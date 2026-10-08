"""Consulta "estilo ViaCEP": uma URL, uma resposta JSON pronta pra usar.

    GET /v1/BR/SP/23091000         tributos do NCM em SP
    GET /v1/BR/23091000            so os nacionais (sem UF)
    GET /v1/AR/B/7898242031936     por codigo de barras: produto + tributos
    GET /v1/AR                     o pais: provincias e tributos cadastrados
    ?lang=pt|es|en                 idioma dos nomes (padrao: o do pais)
    ?date=2027-01-01               tributos vigentes em outra data
    ?cest=0000000                  regra especifica de um CEST

Sem login, sem chave. O mesmo endpoint funciona em qualquer copia do
ProdBR rodando local.
"""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.fiscal import resolve_fiscal_rule
from app.models_public import Country, NcmClassification, Product, ProductIdentifier, State
from app.rate_limit import limiter
from app.taxes import build_taxes, country_tax_types, language_of, tax_name

router = APIRouter(prefix="/v1", tags=["consulta"])


def _country_or_404(db: DbSession, code: str) -> Country:
    country = db.get(Country, code.strip().upper())
    if country is None:
        raise HTTPException(status_code=404, detail=f"País '{code.upper()}' não cadastrado. Veja /countries.")
    return country


def _state_or_404(db: DbSession, country: Country, code: str) -> State:
    state = db.query(State).filter(State.country_id == country.id, State.code == code.strip().upper()).first()
    if state is None:
        label = country.subdivision_label or "UF"
        raise HTTPException(
            status_code=404, detail=f"{label} '{code.upper()}' não existe em {country.name}. Veja /v1/{country.id}."
        )
    return state


def _country_json(country: Country) -> dict:
    return {
        "code": country.id,
        "name": country.name,
        "language": country.language,
        "subdivision_label": country.subdivision_label,
    }


@router.get("/{country_code}")
@limiter.limit(settings.rate_limit_read)
def country_info(request: Request, country_code: str, lang: str | None = None, db: DbSession = Depends(get_public_db)):
    """O pais: subdivisoes (UF/provincias) e os tributos cadastrados."""
    country = _country_or_404(db, country_code)
    language = language_of(country, lang)
    states = db.query(State).filter(State.country_id == country.id).order_by(State.name).all()
    return {
        "country": _country_json(country),
        "lang": language,
        "states": [{"code": s.code, "name": s.name} for s in states],
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
            for t in country_tax_types(db, country.id)
        ],
    }


def _lookup(db: DbSession, country: Country, state: State | None, code: str, lang, on_date, cest) -> dict:
    digits = re.sub(r"\D", "", code)
    if not digits:
        raise HTTPException(status_code=400, detail="Informe um NCM (8 dígitos) ou um código de barras.")

    product = None
    identifier = None
    classification = db.get(NcmClassification, digits) if len(digits) == 8 else None
    if classification is None:
        identifier = db.query(ProductIdentifier).filter(ProductIdentifier.value == digits).first()
        if identifier is None:
            raise HTTPException(status_code=404, detail=f"'{code}' não é um NCM nem um código de barras cadastrado.")
        product = db.get(Product, identifier.product_id)
        if not product or not product.ncm:
            raise HTTPException(status_code=404, detail="Produto encontrado, mas ainda sem NCM cadastrado.")
        classification = db.get(NcmClassification, product.ncm)
        cest = cest or product.cest

    ncm = product.ncm if product else digits
    on_date = on_date or date.today()
    rule = resolve_fiscal_rule(db, ncm, state.code if state else None, on_date, cest, country.id)
    language = language_of(country, lang)
    result = {
        "ncm": ncm,
        "ncm_description": classification.description if classification else None,
        "country": _country_json(country),
        "state": {"code": state.code, "name": state.name} if state else None,
        "date": on_date.isoformat(),
        "lang": language,
        "taxes": build_taxes(rule, country_tax_types(db, country.id), country, language),
        "notes": rule.notes if rule else None,
        "sources": rule.source.split(" + ") if rule and rule.source else [],
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


@router.get("/{country_code}/{code}")
@limiter.limit(settings.rate_limit_read)
def lookup_national(
    request: Request,
    country_code: str,
    code: str,
    lang: str | None = None,
    date: date | None = None,
    cest: str | None = None,
    db: DbSession = Depends(get_public_db),
):
    """Tributos de um NCM (ou código de barras) no país, sem UF."""
    return _lookup(db, _country_or_404(db, country_code), None, code, lang, date, cest)


@router.get("/{country_code}/{state_code}/{code}")
@limiter.limit(settings.rate_limit_read)
def lookup_state(
    request: Request,
    country_code: str,
    state_code: str,
    code: str,
    lang: str | None = None,
    date: date | None = None,
    cest: str | None = None,
    db: DbSession = Depends(get_public_db),
):
    """Tributos de um NCM (ou código de barras) na UF/província do país."""
    country = _country_or_404(db, country_code)
    return _lookup(db, country, _state_or_404(db, country, state_code), code, lang, date, cest)
