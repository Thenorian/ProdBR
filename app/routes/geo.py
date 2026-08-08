"""Dados de referencia (bibliografia) de pais/estado - usados pra montar
seletores reais no formulario de regra fiscal, em vez de campos de texto
livre. Somente leitura: pais/estado nao sao editados via API, so
consultados (ver scripts/seed_geo.py para a carga inicial)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.models_public import Country, State
from app.rate_limit import limiter
from app.schemas import CountryOut, StateOut

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
