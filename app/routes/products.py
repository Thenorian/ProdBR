from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApiKey, ChangeLog, Product, ProductBarcode
from app.schemas import ProductCreate, ProductList, ProductOut, ProductUpdate
from app.security import limiter, require_api_key

router = APIRouter(prefix="/products", tags=["products"])

PRODUCT_FIELDS = [
    "ncm",
    "cest",
    "description",
    "unit",
    "gross_weight",
    "net_weight",
    "origin",
    "icms_rate",
    "ipi_rate",
    "pis_rate",
    "cofins_rate",
    "cbs_rate",
    "ibs_rate",
]


def serialize_product(product: Product) -> ProductOut:
    data = {field: getattr(product, field) for field in PRODUCT_FIELDS}
    return ProductOut(
        id=product.id,
        barcodes=[b.barcode for b in product.barcodes],
        created_at=product.created_at,
        updated_at=product.updated_at,
        **data,
    )


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto nao encontrado.")
    return product


def apply_barcodes(db: Session, product: Product, barcodes: list[str]) -> None:
    normalized = {code.strip() for code in barcodes if code.strip()}
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe ao menos um codigo de barras valido.",
        )
    existing = (
        db.query(ProductBarcode)
        .filter(ProductBarcode.barcode.in_(normalized), ProductBarcode.product_id != product.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Codigo de barras '{existing.barcode}' ja pertence a outro produto.",
        )
    product.barcodes = [ProductBarcode(barcode=code) for code in normalized]


@router.get("", response_model=ProductList)
@limiter.limit(settings.rate_limit_read)
def search_products(
    request: Request,
    barcode: str | None = None,
    ncm: str | None = None,
    q: str | None = None,
    limit: int = settings.max_page_size,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Busca produtos por codigo de barras, NCM ou descricao.

    Limite maximo de itens por requisicao: veja MAX_PAGE_SIZE. Requisicoes
    pedindo mais que isso sao silenciosamente limitadas ao teto.
    """
    limit = max(1, min(limit, settings.max_page_size))
    offset = max(0, offset)

    query = db.query(Product)
    if barcode:
        query = query.join(Product.barcodes).filter(ProductBarcode.barcode == barcode.strip())
    if ncm:
        query = query.filter(Product.ncm == ncm.strip())
    if q:
        query = query.filter(or_(Product.description.ilike(f"%{q}%")))

    total = query.distinct().count()
    products = query.distinct().order_by(Product.id).offset(offset).limit(limit).all()

    return ProductList(
        items=[serialize_product(p) for p in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductOut)
@limiter.limit(settings.rate_limit_read)
def get_product(request: Request, product_id: int, db: Session = Depends(get_db)):
    product = get_product_or_404(db, product_id)
    return serialize_product(product)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_write)
def create_product(
    request: Request,
    payload: ProductCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    product = Product(**payload.model_dump(exclude={"barcodes"}))
    db.add(product)
    db.flush()
    apply_barcodes(db, product, payload.barcodes)

    db.add(
        ChangeLog(
            product_id=product.id,
            api_key_id=api_key.id,
            action="create",
            diff={"new": payload.model_dump()},
        )
    )
    db.commit()
    db.refresh(product)
    return serialize_product(product)


@router.put("/{product_id}", response_model=ProductOut)
@limiter.limit(settings.rate_limit_write)
def update_product(
    request: Request,
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    product = get_product_or_404(db, product_id)

    changes = payload.model_dump(exclude_unset=True, exclude={"barcodes"})
    diff: dict = {"before": {}, "after": {}}
    for field, new_value in changes.items():
        old_value = getattr(product, field)
        if old_value != new_value:
            diff["before"][field] = old_value
            diff["after"][field] = new_value
            setattr(product, field, new_value)

    if payload.barcodes is not None:
        old_barcodes = sorted(b.barcode for b in product.barcodes)
        new_barcodes = sorted({c.strip() for c in payload.barcodes if c.strip()})
        if old_barcodes != new_barcodes:
            diff["before"]["barcodes"] = old_barcodes
            diff["after"]["barcodes"] = new_barcodes
            apply_barcodes(db, product, payload.barcodes)

    if not diff["before"]:
        return serialize_product(product)

    db.add(
        ChangeLog(
            product_id=product.id,
            api_key_id=api_key.id,
            action="update",
            diff=diff,
        )
    )
    db.commit()
    db.refresh(product)
    return serialize_product(product)
