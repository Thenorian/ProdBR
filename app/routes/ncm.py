from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.auth import require_user
from app.changes import propose_or_apply
from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import User
from app.models_public import FiscalRule, NcmClassification, Product
from app.rate_limit import limiter
from app.routes.common import apply_or_400, get_or_404, write_response
from app.schemas import FiscalRuleOut, NcmCreate, NcmDetail, NcmOut, NcmUpdate

router = APIRouter(prefix="/ncm", tags=["ncm"])


@router.get("", response_model=list[NcmOut])
@limiter.limit(settings.rate_limit_read)
def search_ncm(
    request: Request,
    q: str | None = None,
    limit: int = settings.max_page_size,
    offset: int = 0,
    db: DbSession = Depends(get_public_db),
):
    """Busca classificacoes de NCM por codigo (prefixo) ou texto da
    descricao - independente de qualquer produto cadastrado."""
    limit = max(1, min(limit, settings.max_page_size))
    offset = max(0, offset)

    query = db.query(NcmClassification)
    if q:
        stripped = q.strip()
        query = query.filter(
            or_(NcmClassification.ncm.like(f"{stripped}%"), NcmClassification.description.ilike(f"%{stripped}%"))
        )
    return query.order_by(NcmClassification.ncm).offset(offset).limit(limit).all()


@router.get("/{code}", response_model=NcmDetail)
@limiter.limit(settings.rate_limit_read)
def get_ncm(request: Request, code: str, db: DbSession = Depends(get_public_db)):
    """Ficha completa de um NCM: descricao oficial + todas as regras
    fiscais ja cadastradas (qualquer pais/UF) + quantos produtos usam
    essa classificacao. Nao exige nenhum produto cadastrado."""
    code = code.strip()
    classification = get_or_404(db, NcmClassification, code, "NCM")
    product_count = db.query(Product).filter(Product.ncm == code).count()
    fiscal_rules = (
        db.query(FiscalRule)
        .filter(FiscalRule.ncm == code)
        .order_by(FiscalRule.country, FiscalRule.valid_from.desc())
        .all()
    )
    detail = NcmDetail.model_validate(classification)
    detail.product_count = product_count
    detail.fiscal_rules = [FiscalRuleOut.model_validate(f) for f in fiscal_rules]
    return detail


@router.post("", status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_ncm(
    request: Request,
    payload: NcmCreate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    data = payload.model_dump(mode="json", exclude={"reason"})
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "ncm_classification", None, data, payload.reason
    )
    return write_response(result, 201, NcmOut)


@router.put("/{code}", status_code=200)
@limiter.limit(settings.rate_limit_write)
def update_ncm(
    request: Request,
    code: str,
    payload: NcmUpdate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    code = code.strip()
    get_or_404(db_public, NcmClassification, code, "NCM")
    data = payload.model_dump(mode="json", exclude={"reason"}, exclude_unset=True)
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "ncm_classification", code, data, payload.reason
    )
    return write_response(result, 200, NcmOut)
