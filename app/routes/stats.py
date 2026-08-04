from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_public_db
from app.models_public import FiscalRule, Product, ProductIdentifier, Revision
from app.rate_limit import limiter

router = APIRouter(tags=["stats"])


@router.get("/stats")
@limiter.limit(settings.rate_limit_read)
def get_stats(request: Request, db: DbSession = Depends(get_public_db)):
    """Contadores gerais da base publica - usado na pagina inicial."""
    return {
        "products": db.query(Product).count(),
        "identifiers": db.query(ProductIdentifier).count(),
        "fiscal_rules": db.query(FiscalRule).count(),
        "revisions": db.query(Revision).count(),
    }
