"""Dados de referencia de pais/estado/tributo - usados pra montar os
seletores e campos do formulario de regra fiscal. Leitura publica; quem
cadastra/edita e o admin (ver app/routes/admin_taxes.py). A carga de
fabrica fica em app/reference_data.py."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.models_public import Country, State, TaxType
from app.rate_limit import limiter
from app.schemas import CountryOut, StateOut, TaxTypeOut

router = APIRouter(prefix="/countries", tags=["geo"])


@router.get("", response_model=list[CountryOut])
@limiter.limit(settings.rate_limit_read)
def list_countries(request: Request, db: DbSession = Depends(get_public_db)):
    return db.query(Country).order_by(Country.name).all()


@router.get("/{country_id}/states", response_model=list[StateOut])
@limiter.limit(settings.rate_limit_read)
def list_states(request: Request, country_id: str, db: DbSession = Depends(get_public_db)):
    return (
        db.query(State)
        .filter(State.country_id == country_id.strip().upper())
        .order_by(State.name)
        .all()
    )


@router.get("/{country_id}/tax-types", response_model=list[TaxTypeOut])
@limiter.limit(settings.rate_limit_read)
def list_tax_types(request: Request, country_id: str, include_inactive: bool = False, db: DbSession = Depends(get_public_db)):
    query = db.query(TaxType).filter(TaxType.country_id == country_id.strip().upper())
    if not include_inactive:
        query = query.filter(TaxType.active.is_(True))
    return query.order_by(TaxType.sort_order, TaxType.code).all()
