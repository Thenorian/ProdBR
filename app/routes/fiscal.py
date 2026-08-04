from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.auth import require_user
from app.changes import propose_or_apply
from app.config import settings
from app.database import get_community_db, get_public_db
from app.fiscal import resolve_fiscal_rule
from app.models_community import User
from app.models_public import FiscalRule, Product
from app.rate_limit import limiter
from app.routes.common import apply_or_400, get_or_404, write_response
from app.schemas import FiscalRuleCreate, FiscalRuleOut, FiscalRuleUpdate

router = APIRouter(tags=["fiscal"])


@router.get("/fiscal-rules", response_model=FiscalRuleOut)
@limiter.limit(settings.rate_limit_read)
def get_fiscal_rule(
    request: Request,
    ncm: str,
    uf: str | None = None,
    cest: str | None = None,
    on_date: date | None = None,
    db: DbSession = Depends(get_public_db),
):
    """Resolve a regra fiscal mais especifica e vigente para o NCM (e UF,
    se informada) na data pedida (padrao: hoje)."""
    rule = resolve_fiscal_rule(db, ncm.strip(), uf.strip().upper() if uf else None, on_date or date.today(), cest)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma regra fiscal vigente para esse NCM/UF/data.")
    return rule


@router.get("/fiscal-rules/history", response_model=list[FiscalRuleOut])
@limiter.limit(settings.rate_limit_read)
def fiscal_rule_history(
    request: Request,
    ncm: str,
    uf: str | None = None,
    limit: int = settings.max_page_size,
    db: DbSession = Depends(get_public_db),
):
    """Todas as regras cadastradas para um NCM (opcionalmente filtrando por
    UF), mais recentes primeiro - para auditoria de mudanca de aliquota."""
    limit = max(1, min(limit, settings.max_page_size))
    query = db.query(FiscalRule).filter(FiscalRule.ncm == ncm.strip())
    if uf:
        query = query.filter(FiscalRule.uf == uf.strip().upper())
    return query.order_by(FiscalRule.valid_from.desc()).limit(limit).all()


@router.get("/products/{product_id}/fiscal", response_model=FiscalRuleOut)
@limiter.limit(settings.rate_limit_read)
def get_product_fiscal_rule(
    request: Request,
    product_id: str,
    uf: str | None = None,
    on_date: date | None = None,
    db: DbSession = Depends(get_public_db),
):
    product = get_or_404(db, Product, product_id, "Produto")
    rule = resolve_fiscal_rule(
        db, product.ncm, uf.strip().upper() if uf else None, on_date or date.today(), product.cest
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma regra fiscal vigente para o NCM desse produto.",
        )
    return rule


@router.post("/fiscal-rules", status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_fiscal_rule(
    request: Request,
    payload: FiscalRuleCreate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    data = payload.model_dump(mode="json", exclude={"reason"})
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "fiscal_rule", None, data, payload.reason
    )
    return write_response(result, 201, FiscalRuleOut)


@router.put("/fiscal-rules/{rule_id}", status_code=200)
@limiter.limit(settings.rate_limit_write)
def update_fiscal_rule(
    request: Request,
    rule_id: int,
    payload: FiscalRuleUpdate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    get_or_404(db_public, FiscalRule, rule_id, "Regra fiscal")
    data = payload.model_dump(mode="json", exclude={"reason"}, exclude_unset=True)
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "fiscal_rule", str(rule_id), data, payload.reason
    )
    return write_response(result, 200, FiscalRuleOut)
