"""Admin: paises, subdivisoes (UF/provincia/departamento) e tributos.

E o que deixa o ProdBR valer pra qualquer pais: o admin cadastra o pais,
as subdivisoes e os tributos (com traducao); depois a comunidade cadastra
as aliquotas por NCM em /fiscal-rules (`rates: {"IVA": 21}`) e a consulta
/v1/{pais}/{uf}/{ncm} passa a responder sozinha.

Tributo nao e apagado (regras antigas podem usar) - desativa com
`active: false`. Tributo de fabrica com coluna propria (ICMS, IPI...) nao
muda de codigo nem de coluna.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.auth import require_admin
from app.config import settings
from app.database import get_public_db
from app.models_community import User
from app.models_public import Country, FiscalRule, State, TaxType
from app.rate_limit import limiter
from app.schemas import (
    CountryCreate,
    CountryOut,
    CountryUpdate,
    StateCreate,
    StateOut,
    TaxTypeCreate,
    TaxTypeOut,
    TaxTypeUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _country(db: DbSession, country_id: str) -> Country:
    country = db.get(Country, country_id.strip().upper())
    if country is None:
        raise HTTPException(status_code=404, detail=f"País '{country_id.upper()}' não cadastrado.")
    return country


@router.post("/countries", response_model=CountryOut, status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_country(request: Request, payload: CountryCreate, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)):
    code = payload.id.strip().upper()
    if db.get(Country, code) is not None:
        raise HTTPException(status_code=409, detail=f"País '{code}' já existe.")
    country = Country(id=code, name=payload.name.strip(), language=payload.language, subdivision_label=payload.subdivision_label)
    db.add(country)
    db.commit()
    db.refresh(country)
    return country


@router.put("/countries/{country_id}", response_model=CountryOut)
@limiter.limit(settings.rate_limit_write)
def update_country(
    request: Request, country_id: str, payload: CountryUpdate, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)
):
    country = _country(db, country_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(country, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(country)
    return country


@router.post("/countries/{country_id}/states", response_model=StateOut, status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_state(
    request: Request, country_id: str, payload: StateCreate, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)
):
    country = _country(db, country_id)
    state = State(country_id=country.id, code=payload.code.strip().upper(), name=payload.name.strip())
    db.add(state)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"'{state.code}' já existe em {country.name}.")
    db.refresh(state)
    return state


@router.delete("/countries/{country_id}/states/{code}", status_code=204)
@limiter.limit(settings.rate_limit_write)
def delete_state(request: Request, country_id: str, code: str, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)):
    country = _country(db, country_id)
    code = code.strip().upper()
    state = db.query(State).filter(State.country_id == country.id, State.code == code).first()
    if state is None:
        raise HTTPException(status_code=404, detail=f"'{code}' não existe em {country.name}.")
    if db.query(FiscalRule).filter(FiscalRule.country == country.id, FiscalRule.uf == code).first():
        raise HTTPException(status_code=409, detail=f"Há regras fiscais usando '{code}' - não dá pra remover.")
    db.delete(state)
    db.commit()


@router.post("/tax-types", response_model=TaxTypeOut, status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_tax_type(request: Request, payload: TaxTypeCreate, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)):
    country = _country(db, payload.country_id)
    tax = TaxType(**{**payload.model_dump(), "country_id": country.id, "code": payload.code.strip().upper()})
    db.add(tax)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"{country.name} já tem o tributo '{tax.code}'.")
    db.refresh(tax)
    return tax


@router.put("/tax-types/{tax_id}", response_model=TaxTypeOut)
@limiter.limit(settings.rate_limit_write)
def update_tax_type(
    request: Request, tax_id: int, payload: TaxTypeUpdate, db: DbSession = Depends(get_public_db), admin: User = Depends(require_admin)
):
    tax = db.get(TaxType, tax_id)
    if tax is None:
        raise HTTPException(status_code=404, detail="Tributo não encontrado.")
    # default_rate/translations/description podem ser zerados (null) de
    # proposito; os demais so mudam quando vem valor.
    nullable = {"default_rate", "default_source", "translations", "description"}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field not in nullable:
            continue
        setattr(tax, field, value)
    db.commit()
    db.refresh(tax)
    return tax
