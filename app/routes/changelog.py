from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ChangeLog
from app.routes.products import get_product_or_404
from app.schemas import ChangeLogOut
from app.security import limiter

router = APIRouter(tags=["changelog"])


@router.get("/products/{product_id}/changelog", response_model=list[ChangeLogOut])
@limiter.limit(settings.rate_limit_read)
def product_changelog(
    request: Request,
    product_id: int,
    limit: int = settings.max_page_size,
    db: Session = Depends(get_db),
):
    """Historico de alteracoes de um produto, tipo um `git log` publico."""
    get_product_or_404(db, product_id)
    limit = max(1, min(limit, settings.max_page_size))
    entries = (
        db.query(ChangeLog)
        .filter(ChangeLog.product_id == product_id)
        .order_by(ChangeLog.id.desc())
        .limit(limit)
        .all()
    )
    return entries


@router.get("/changelog", response_model=list[ChangeLogOut])
@limiter.limit(settings.rate_limit_read)
def global_changelog(
    request: Request,
    limit: int = settings.max_page_size,
    db: Session = Depends(get_db),
):
    """Ultimas alteracoes feitas na base, em qualquer produto."""
    limit = max(1, min(limit, settings.max_page_size))
    entries = db.query(ChangeLog).order_by(ChangeLog.id.desc()).limit(limit).all()
    return entries
