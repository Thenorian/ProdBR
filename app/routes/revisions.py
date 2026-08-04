from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.models_public import FiscalRule, Product, ProductIdentifier, Revision
from app.rate_limit import limiter
from app.schemas import RevisionOut

router = APIRouter(tags=["revisions"])


def _entity_names(db: DbSession, revisions: list[Revision]) -> dict[str, str]:
    """Resolve um rotulo legivel por (entity_type, entity_id) - usado para
    mostrar o nome do produto em vez do ID cru nas listas de mudancas."""
    ids_by_type: dict[str, set[str]] = {}
    for r in revisions:
        ids_by_type.setdefault(r.entity_type, set()).add(r.entity_id)

    names: dict[str, str] = {}

    product_ids = ids_by_type.get("product")
    if product_ids:
        for p in db.query(Product).filter(Product.id.in_(product_ids)).all():
            names[f"product:{p.id}"] = p.name

    identifier_ids = ids_by_type.get("identifier")
    if identifier_ids:
        int_ids = [int(i) for i in identifier_ids if i.isdigit()]
        for i in db.query(ProductIdentifier).filter(ProductIdentifier.id.in_(int_ids)).all():
            names[f"identifier:{i.id}"] = i.value

    fiscal_ids = ids_by_type.get("fiscal_rule")
    if fiscal_ids:
        int_ids = [int(i) for i in fiscal_ids if i.isdigit()]
        for f in db.query(FiscalRule).filter(FiscalRule.id.in_(int_ids)).all():
            names[f"fiscal_rule:{f.id}"] = f"NCM {f.ncm}"

    return names


def _to_out(db: DbSession, revisions: list[Revision]) -> list[RevisionOut]:
    names = _entity_names(db, revisions)
    out = []
    for r in revisions:
        item = RevisionOut.model_validate(r)
        item.entity_name = names.get(f"{r.entity_type}:{r.entity_id}")
        out.append(item)
    return out


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
    return _to_out(db, _query_revisions(db, entity_type, entity_id, limit))


@router.get("/products/{product_id}/revisions", response_model=list[RevisionOut])
@limiter.limit(settings.rate_limit_read)
def product_revisions(
    request: Request,
    product_id: str,
    limit: int = settings.max_page_size,
    db: DbSession = Depends(get_public_db),
):
    return _to_out(db, _query_revisions(db, "product", product_id, limit))
