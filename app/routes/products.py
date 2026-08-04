from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.auth import require_user
from app.changes import propose_or_apply
from app.config import settings
from app.database import get_community_db, get_public_db
from app.models_community import User
from app.models_public import Product, ProductIdentifier
from app.rate_limit import limiter
from app.routes.common import apply_or_400, get_or_404, write_response
from app.schemas import (
    IdentifierCreate,
    IdentifierDelete,
    IdentifierOut,
    ProductCreate,
    ProductList,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(tags=["products"])


@router.get("/products", response_model=ProductList)
@limiter.limit(settings.rate_limit_read)
def search_products(
    request: Request,
    identifier: str | None = None,
    ncm: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = settings.max_page_size,
    offset: int = 0,
    db: DbSession = Depends(get_public_db),
):
    """Busca por identificador (codigo de barras/GTIN/etc), NCM, categoria
    ou texto livre (nome/marca/fabricante/descricao)."""
    limit = max(1, min(limit, settings.max_page_size))
    offset = max(0, offset)

    query = db.query(Product)
    if identifier:
        query = query.join(Product.identifiers).filter(ProductIdentifier.value == identifier.strip())
    if ncm:
        query = query.filter(Product.ncm == ncm.strip())
    if category:
        query = query.filter(Product.category == category.strip())
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Product.name.ilike(like),
                Product.brand.ilike(like),
                Product.manufacturer.ilike(like),
                Product.description.ilike(like),
            )
        )

    total = query.distinct().count()
    products = query.distinct().order_by(Product.id).offset(offset).limit(limit).all()

    return ProductList(
        items=[ProductOut.model_validate(p) for p in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
@limiter.limit(settings.rate_limit_read)
def get_product(request: Request, product_id: str, db: DbSession = Depends(get_public_db)):
    return get_or_404(db, Product, product_id, "Produto")


@router.post("/products", status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_product(
    request: Request,
    payload: ProductCreate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    data = payload.model_dump(mode="json", exclude={"reason"})
    result = apply_or_400(propose_or_apply, db_public, db_community, user, "product", None, data, payload.reason)
    return write_response(result, 201, ProductOut)


@router.put("/products/{product_id}", status_code=200)
@limiter.limit(settings.rate_limit_write)
def update_product(
    request: Request,
    product_id: str,
    payload: ProductUpdate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    get_or_404(db_public, Product, product_id, "Produto")
    data = payload.model_dump(mode="json", exclude={"reason"}, exclude_unset=True)
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "product", product_id, data, payload.reason
    )
    return write_response(result, 200, ProductOut)


@router.post("/identifiers", status_code=201)
@limiter.limit(settings.rate_limit_write)
def create_identifier(
    request: Request,
    payload: IdentifierCreate,
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    get_or_404(db_public, Product, payload.product_id, "Produto")
    data = {"product_id": payload.product_id, "type": payload.type, "value": payload.value.strip()}
    result = apply_or_400(
        propose_or_apply, db_public, db_community, user, "identifier", None, data, payload.reason
    )
    return write_response(result, 201, IdentifierOut)


@router.delete("/identifiers/{identifier_id}", status_code=200)
@limiter.limit(settings.rate_limit_write)
def delete_identifier(
    request: Request,
    identifier_id: int,
    payload: IdentifierDelete = Body(...),
    db_public: DbSession = Depends(get_public_db),
    db_community: DbSession = Depends(get_community_db),
    user: User = Depends(require_user),
):
    get_or_404(db_public, ProductIdentifier, identifier_id, "Identificador")
    result = apply_or_400(
        propose_or_apply,
        db_public,
        db_community,
        user,
        "identifier",
        str(identifier_id),
        {},
        payload.reason,
    )
    return write_response(result, 200, None)
