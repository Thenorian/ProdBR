"""
Versão 0: as rotas da API antiga do ProdBR, sem versão no endereço, só para sistemas que
já estão instalados e ainda não foram atualizados (OS-Mechanical nas máquinas dos clientes,
Simple ERP até a versão que usa /api/v1).

Nada novo entra aqui. Cada rota traduz o formato antigo para a v1 e responde no formato
antigo, usando o mesmo banco e as mesmas validações. Quando nenhum sistema usar mais,
este arquivo e a linha dele em server.py podem ser apagados.

    GET  /products?identifier=...   POST /products   GET/PUT /products/{id}
    POST /identifiers               GET  /ncm/{código}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import register_contribution, require_contributor
from api.common import DEFAULT_PAGE_SIZE, found_or_404, page_limits, result_or_error
from api.products import BarcodeInput, ProductInput, clean_barcode_input, clean_product_input
from api.rate_limit import limit_reads, limit_writes
from database.contributor import can_write_directly
from database.ncm import NcmDB
from database.product import ProductDB
from util.validation import clean_ncm

router = APIRouter(include_in_schema=False)


class OldIdentifierInput(BaseModel):
    product_id: str
    type: str = "other"
    value: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=3, max_length=300)
    description: str | None = Field(None, max_length=120)
    units_per_pack: int | None = Field(None, ge=1)


def product_in_old_format(product):
    """Produto da v1 no formato da API antiga: ncm e category como texto, identifiers com value."""
    return {
        "id": product["id"],
        "name": product["name"],
        "brand": product["brand"],
        "ncm": product["ncm"]["code"] if product["ncm"] else None,
        "cest": product["cest"],
        "category": product["category"]["path"] if product["category"] else None,
        "commercial_unit": product["commercial_unit"],
        "description": product["description"],
        "manufacturer": product["manufacturer"],
        "source": product["source"],
        "identifiers": [
            {
                "id": item["barcode"],
                "type": f"gtin{len(item['barcode'])}",
                "value": item["barcode"],
                "description": item["package_description"],
                "net_quantity": item["net_quantity"],
                "net_unit": item["net_unit"],
                "units_per_pack": item["units_per_pack"],
            }
            for item in product["barcodes"]
        ],
        "created_at": product["created_at"],
        "updated_at": product["updated_at"],
    }


def full_product_or_404(product_id):
    product = result_or_error(ProductDB().get_full(product_id), 500)
    return found_or_404(product, "Produto não encontrado.")


@router.get("/products", dependencies=[Depends(limit_reads)])
def old_search_products(
    identifier: str | None = None,
    ncm: str | None = None,
    q: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
):
    limit, offset = page_limits(limit, offset)
    identifier = (identifier or "").strip()

    # Na API antiga "identifier" servia tanto para código de barras quanto para código do fabricante.
    filters = {"ncm_code": clean_ncm(ncm) if ncm else None, "text": (q or "").strip()[:100]}
    if identifier.isdigit():
        filters["barcode"] = identifier
    elif identifier:
        filters["manufacturer_code"] = identifier

    products = ProductDB()
    found = result_or_error(products.search(filters, limit, offset), 500)
    items = [product_in_old_format(full_product_or_404(product_id)) for product_id in found["ids"]]
    return {"items": items, "total": found["total"], "limit": limit, "offset": offset}


@router.get("/products/{product_id}", dependencies=[Depends(limit_reads)])
def old_get_product(product_id: str):
    return product_in_old_format(full_product_or_404(product_id))


@router.post("/products", status_code=201, dependencies=[Depends(limit_writes)])
def old_create_product(payload: ProductInput, contributor=Depends(require_contributor)):
    refuse_contributor_without_direct_write(contributor)
    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome do produto.")

    data, barcodes = clean_product_input(payload, payload.model_fields_set, contributor["username"])
    product_id = result_or_error(ProductDB().create(data, barcodes or [], contributor["username"], payload.reason))
    register_contribution(contributor, [field for field in data if data[field] is not None])
    return product_in_old_format(full_product_or_404(product_id))


@router.put("/products/{product_id}", dependencies=[Depends(limit_writes)])
def old_update_product(product_id: str, payload: ProductInput, contributor=Depends(require_contributor)):
    refuse_contributor_without_direct_write(contributor)
    sent_fields = payload.model_fields_set - {"reason"}
    data, barcodes = clean_product_input(payload, sent_fields, contributor["username"])
    changed_fields = result_or_error(
        ProductDB().update(product_id, data, barcodes, contributor["username"], payload.reason)
    )
    register_contribution(contributor, changed_fields)
    return product_in_old_format(full_product_or_404(product_id))


@router.post("/identifiers", status_code=201, dependencies=[Depends(limit_writes)])
def old_create_identifier(payload: OldIdentifierInput, contributor=Depends(require_contributor)):
    refuse_contributor_without_direct_write(contributor)
    """Na API antiga o código de barras era cadastrado à parte; aqui ele entra na lista do produto."""
    products = ProductDB()
    product = full_product_or_404(payload.product_id)

    if payload.type == "manufacturer_code":
        changes = {"manufacturer_code": " ".join(payload.value.split())[:60]}
        changed_fields = result_or_error(
            products.update(payload.product_id, changes, None, contributor["username"], payload.reason)
        )
    else:
        ok, new_barcode = clean_barcode_input(
            BarcodeInput(barcode=payload.value, package=payload.description, units_per_pack=payload.units_per_pack)
        )
        if not ok:
            raise HTTPException(status_code=400, detail=new_barcode)

        other_barcodes = [item for item in product["barcodes"] if item["barcode"] != new_barcode["barcode"]]
        changed_fields = result_or_error(products.update(
            payload.product_id, {}, other_barcodes + [new_barcode], contributor["username"], payload.reason
        ))

    register_contribution(contributor, changed_fields)
    return {"id": payload.value.strip(), "type": payload.type, "value": payload.value.strip()}


def refuse_contributor_without_direct_write(contributor):
    """A API antiga não conhece a fila de votação. Quem ainda é Iniciante usa a /api/v1."""
    if not can_write_directly(contributor):
        raise HTTPException(
            status_code=403,
            detail="Contribuidor novo usa a API /api/v1, onde as alterações passam pela votação da comunidade.",
        )


@router.get("/ncm/{code}", dependencies=[Depends(limit_reads)])
def old_get_ncm(code: str):
    ncm_code = clean_ncm(code)
    ncm = result_or_error(NcmDB().get(ncm_code), 500) if ncm_code else None
    ncm = found_or_404(ncm, "NCM não está na tabela oficial.")

    ok, product_count = ProductDB().count("products", {"ncm_code": ncm_code})
    return {
        "ncm": ncm["code"],
        "description": ncm["full_description"],
        "chapter": ncm["code"][:2],
        "source": "Siscomex",
        "product_count": product_count if ok else 0,
        "fiscal_rules": [],
    }
