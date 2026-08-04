from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.models_public import Revision
from app.rate_limit import limiter
from app.schemas import RevisionOut

router = APIRouter(tags=["revisions"])


def _query_revisions(db: DbSession, entity_type: str | None, entity_id: str | None, limit: int):
    limit = max(1, min(limit, settings.max_page_size))
    query = db.query(Revision)
    if entity_type:
        query = query.filter(Revision.entity_type == entity_type)
    if entity_id:
        query = query.filter(Revision.entity_id == entity_id)
    return query.order_by(Revision.id.desc()).limit(limit).all()


@router.get("/revisions", response_model=list[RevisionOut])
@limiter.limit(settings.rate_limit_read)
def list_revisions(
    request: Request,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = settings.max_page_size,
    db: DbSession = Depends(get_public_db),
):
    """Historico de alteracoes, tipo `git log` publico. Filtre por
    entity_type (product/identifier/fiscal_rule) e/ou entity_id."""
    return _query_revisions(db, entity_type, entity_id, limit)


@router.get("/products/{product_id}/revisions", response_model=list[RevisionOut])
@limiter.limit(settings.rate_limit_read)
def product_revisions(
    request: Request,
    product_id: str,
    limit: int = settings.max_page_size,
    db: DbSession = Depends(get_public_db),
):
    return _query_revisions(db, "product", product_id, limit)
