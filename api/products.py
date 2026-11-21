from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import register_contribution, require_contributor
from api.common import DEFAULT_PAGE_SIZE, found_or_404, page_limits, result_or_error
from api.rate_limit import limit_reads, limit_writes
from database.category import CategoryDB
from database.product import ProductDB
from database.revision import RevisionDB
from util.packaging import VALID_UNITS, read_package_text, standard_unit
from util.validation import (
    clean_barcode, clean_category_path, clean_cest, clean_ncm, clean_tax_regime, clean_uf,
)

router = APIRouter(tags=["Produtos"])

REASON_FIELD = Field(..., min_length=3, max_length=300, description="Motivo da alteração, como uma mensagem de commit.")


class BarcodeInput(BaseModel):
    """Código de barras com a embalagem. Os números da embalagem são lidos do texto quando não vêm."""
    barcode: str
    package: str | None = Field(None, max_length=120, description='Embalagem como o fabricante escreve. Ex: "6x350ml", "15 kg"')
    net_quantity: float | None = Field(None, gt=0)
    net_unit: str | None = Field(None, description=f"Uma de: {', '.join(VALID_UNITS)}")
    units_per_pack: int | None = Field(None, ge=1)


class ProductInput(BaseModel):
    """Na criação, name é obrigatório. Na edição, mande só o que quer mudar (null apaga o campo)."""
    name: str | None = Field(None, max_length=255)
    brand: str | None = Field(None, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    manufacturer_code: str | None = Field(None, max_length=60, description="Código interno do fabricante. Ex: BPR6ES")
    description: str | None = Field(None, max_length=2000)
    category: str | None = Field(None, max_length=600, description='Caminho da categoria. Ex: "Bebidas > Cervejas"')
    barcodes: list[str | BarcodeInput] | None = Field(
        None, max_length=50,
        description='Códigos de barras GTIN-8, 12, 13 ou 14. Só o código ("7891000100103") ou com a embalagem.',
    )
    ncm: str | None = Field(None, description="NCM com 8 dígitos. Vazio = usa o da categoria.")
    cest: str | None = Field(None, description="CEST com 7 dígitos. Vazio = usa o da categoria.")
    origin: int | None = Field(None, ge=0, le=8, description="Origem da mercadoria (0 a 8, tabela do ICMS).")
    commercial_unit: str | None = Field(None, max_length=10, description="Ex: UN, KG, CX")
    source: str | None = Field(None, max_length=255, description="De onde veio a informação.")
    reason: str = REASON_FIELD


class PriceInput(BaseModel):
    price: float = Field(..., gt=0, lt=10_000_000, description="Preço em reais. Ex: 12.90")
    uf: str | None = Field(None, description="UF onde o preço foi praticado.")


@router.get("/products", dependencies=[Depends(limit_reads)])
def search_products(
    barcode: str | None = None,
    ncm: str | None = None,
    manufacturer_code: str | None = None,
    manufacturer: str | None = None,
    category_id: str | None = None,
    q: str | None = None,
    uf: str | None = None,
    tax_regime: str | None = None,
    order: str = "name",
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
):
    """
    Busca produtos e devolve cada um completo (o mesmo de /products/{id}).

    Filtros (todos opcionais, se somam): barcode, ncm, manufacturer_code,
    manufacturer, category_id e q (texto livre: nome, marca, fabricante,
    descrição ou qualquer código).

    uf e tax_regime (simples_nacional, lucro_presumido, lucro_real) filtram
    as regras fiscais de cada produto. order: name ou recent.
    """
    limit, offset = page_limits(limit, offset)
    filters = {
        "barcode": (barcode or "").strip(),
        "ncm_code": clean_ncm(ncm) if ncm else None,
        "manufacturer_code": (manufacturer_code or "").strip(),
        "manufacturer": (manufacturer or "").strip(),
        "category_id": (category_id or "").strip(),
        "text": (q or "").strip()[:100],
    }
    if ncm and not filters["ncm_code"]:
        raise HTTPException(status_code=400, detail="NCM inválido: use 8 dígitos.")

    products = ProductDB()
    found = result_or_error(products.search(filters, limit, offset, "recent" if order == "recent" else "name"), 500)

    items = []
    for product_id in found["ids"]:
        items.append(result_or_error(products.get_full(product_id, clean_uf(uf), clean_tax_regime(tax_regime)), 500))

    return {"items": items, "total": found["total"], "limit": limit, "offset": offset}


@router.get("/products/changed", dependencies=[Depends(limit_reads)])
def list_changed_products(since: str = "2000-01-01", limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """
    Ids dos produtos alterados a partir de uma data (AAAA-MM-DD), do mais antigo para o mais novo.
    Para o ERP sincronizar só o que mudou desde a última vez.
    """
    limit, offset = page_limits(limit, offset)
    items = result_or_error(ProductDB().list_changed_since(since[:19], limit, offset), 500)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/barcode/{barcode}", dependencies=[Depends(limit_reads)])
def get_product_by_barcode(barcode: str, uf: str | None = None, tax_regime: str | None = None):
    """
    O jeito mais rápido de preencher um cadastro: manda o código de barras e recebe o produto completo.

        GET /api/barcode/7891000100103?uf=SP&tax_regime=simples_nacional
    """
    products = ProductDB()
    product_id = result_or_error(products.find_id_by_barcode(barcode.strip()), 500)
    found_or_404(product_id, "Nenhum produto com esse código de barras.")
    return result_or_error(products.get_full(product_id, clean_uf(uf), clean_tax_regime(tax_regime)), 500)


@router.get("/products/{product_id}", dependencies=[Depends(limit_reads)])
def get_product(product_id: str, uf: str | None = None, tax_regime: str | None = None):
    """Produto completo: códigos de barras, NCM, categoria, preço médio e regras fiscais."""
    product = result_or_error(ProductDB().get_full(product_id, clean_uf(uf), clean_tax_regime(tax_regime)), 500)
    return found_or_404(product, "Produto não encontrado.")


@router.get("/products/{product_id}/revisions", dependencies=[Depends(limit_reads)])
def list_product_revisions(product_id: str, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Histórico de alterações do produto, do mais novo para o mais antigo."""
    limit, offset = page_limits(limit, offset)
    revisions = result_or_error(RevisionDB().list_for("product", product_id, limit, offset), 500)
    return {**revisions, "limit": limit, "offset": offset}


@router.post("/products", status_code=201, dependencies=[Depends(limit_writes)])
def create_product(payload: ProductInput, contributor=Depends(require_contributor)):
    """Cadastra um produto. Só o nome é obrigatório; NCM, CEST e origem vazios vêm da categoria."""
    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome do produto.")

    data, barcodes = clean_product_input(payload, payload.model_fields_set, contributor["username"])
    product_id = result_or_error(ProductDB().create(data, barcodes or [], contributor["username"], payload.reason))

    register_contribution(contributor, [field for field in data if data[field] is not None])
    return result_or_error(ProductDB().get_full(product_id), 500)


@router.put("/products/{product_id}", dependencies=[Depends(limit_writes)])
def update_product(product_id: str, payload: ProductInput, contributor=Depends(require_contributor)):
    """Altera um produto. Mande só os campos que quer mudar; barcodes substitui a lista inteira."""
    sent_fields = payload.model_fields_set - {"reason"}
    if "name" in sent_fields and not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="O nome do produto não pode ficar vazio.")

    data, barcodes = clean_product_input(payload, sent_fields, contributor["username"])
    changed_fields = result_or_error(
        ProductDB().update(product_id, data, barcodes, contributor["username"], payload.reason)
    )

    register_contribution(contributor, changed_fields)
    product = result_or_error(ProductDB().get_full(product_id), 500)
    return {"changed_fields": changed_fields, "product": product}


@router.post("/products/{product_id}/prices", status_code=201, dependencies=[Depends(limit_writes)])
def report_price(product_id: str, payload: PriceInput, contributor=Depends(require_contributor)):
    """Informa um preço praticado. A API devolve a média e a mediana dos últimos 12 meses no produto."""
    products = ProductDB()
    product_exists = result_or_error(products.exists("products", {"id": product_id}), 500)
    if not product_exists:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    price_cents = round(payload.price * 100)
    result_or_error(products.add_price_report(product_id, price_cents, clean_uf(payload.uf), contributor["username"]))
    return {"product_id": product_id, "price": price_cents / 100}


def clean_product_input(payload, sent_fields, contributor_username):
    """
    Valida e converte os campos enviados para as colunas do banco.
    Só entra o que foi enviado, para a edição não apagar o que ficou de fora.
    Devolve (dados, códigos de barras ou None se não foram enviados).
    """
    data = {}
    errors = []

    def text_or_none(value):
        value = " ".join(str(value).split()) if value is not None else ""
        return value or None

    for field in ("name", "brand", "manufacturer", "manufacturer_code", "description", "source"):
        if field in sent_fields:
            data[field] = text_or_none(getattr(payload, field))

    if "commercial_unit" in sent_fields:
        data["commercial_unit"] = (text_or_none(payload.commercial_unit) or "UN").upper()

    if "origin" in sent_fields:
        data["origin"] = payload.origin

    if "ncm" in sent_fields:
        data["ncm_code"] = clean_ncm(payload.ncm) if payload.ncm else None
        if payload.ncm and not data["ncm_code"]:
            errors.append("NCM inválido: use 8 dígitos.")

    if "cest" in sent_fields:
        data["cest"] = clean_cest(payload.cest) if payload.cest else None
        if payload.cest and not data["cest"]:
            errors.append("CEST inválido: use 7 dígitos.")

    barcodes = None
    if "barcodes" in sent_fields:
        barcodes = []
        for item in payload.barcodes or []:
            ok, barcode = clean_barcode_input(item)
            if not ok:
                errors.append(barcode)
            elif barcode["barcode"] not in [already["barcode"] for already in barcodes]:
                barcodes.append(barcode)

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))

    # A categoria é criada só depois de tudo validado, para um erro não deixar categoria sobrando.
    if "category" in sent_fields:
        data["category_id"] = None
        category_names = clean_category_path(payload.category)
        if category_names:
            data["category_id"] = result_or_error(
                CategoryDB().find_or_create_path(category_names, contributor_username, payload.reason), 500
            )

    return data, barcodes


def clean_barcode_input(item):
    """
    Valida um código de barras e completa a embalagem lendo o texto dela.
    O que veio explícito vale mais que o lido do texto.

        "7891000100103"                                ->  {"barcode": "7891000100103", ...vazio}
        {"barcode": "7891000100103", "package": "6x350ml"}
            ->  {"barcode": ..., "package_description": "6x350ml", "units_per_pack": 6, "net_quantity": 350.0, "net_unit": "ml"}
    """
    if isinstance(item, str):
        item = BarcodeInput(barcode=item)

    barcode = clean_barcode(item.barcode)
    if barcode is None:
        return False, f"Código de barras inválido: {item.barcode} (confira o dígito verificador)."

    package_description = " ".join((item.package or "").split()) or None
    read_from_text = read_package_text(package_description)

    net_unit = item.net_unit or read_from_text.get("net_unit")
    if net_unit is not None and standard_unit(net_unit) is None:
        return False, f"Unidade de embalagem inválida: {net_unit}. Use uma de: {', '.join(VALID_UNITS)}."

    return True, {
        "barcode": barcode,
        "package_description": package_description,
        "net_quantity": item.net_quantity or read_from_text.get("net_quantity"),
        "net_unit": standard_unit(net_unit) if net_unit else None,
        "units_per_pack": item.units_per_pack or read_from_text.get("units_per_pack"),
    }
