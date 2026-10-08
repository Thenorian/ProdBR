"""Entrada e saída da API do catálogo: produto, código de barras,
categoria e classificação NCM."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import IDENTIFIER_TYPES
from app.schemas.common import REASON

NCM_FIELD = Field(..., min_length=8, max_length=8, pattern=r"^\d{8}$", description="NCM com 8 dígitos, sem ponto.")


# +--------------------------------------------------------------------+
# |  Produto                                                           |
# +--------------------------------------------------------------------+
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    ncm: str = NCM_FIELD
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=150, description='Texto livre, ex: "Pet > Ração para Cães".')
    commercial_unit: str = Field("UN", max_length=10)
    description: str | None = Field(None, max_length=1000)
    source: str = Field(..., min_length=1, max_length=120, description="De onde veio esse cadastro.")


class ProductCreate(ProductBase):
    reason: str = REASON


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    manufacturer: str | None = Field(None, max_length=120)
    ncm: str | None = Field(None, min_length=8, max_length=8, pattern=r"^\d{8}$")
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=150)
    commercial_unit: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=1000)
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


# +--------------------------------------------------------------------+
# |  Código de barras / identificador                                  |
# +--------------------------------------------------------------------+
# Grafias aceitas na entrada -> tipo gravado. EAN-13 e UPC-A são GTIN-13 e
# GTIN-12 com outro nome; "GTIN-13" e "gtin_13" viram "gtin13".
IDENTIFIER_ALIASES = {"ean": "gtin13", "ean13": "gtin13", "ean8": "gtin8", "upc": "gtin12", "upca": "gtin12"}


def normalize_identifier_type(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    if key != "manufacturer_code":
        key = IDENTIFIER_ALIASES.get(key.replace("-", "").replace("_", ""), key.replace("-", "").replace("_", ""))
    if key not in IDENTIFIER_TYPES:
        raise ValueError(f"Tipo inválido. Use um de: {', '.join(IDENTIFIER_TYPES)}.")
    return key


PACKAGE_DESCRIPTION = "Embalagem como o fabricante escreve, ex: 'Pacote 15 kg'. Quantidade e unidade vazias são lidas daqui quando dá pra ter certeza."


class IdentifierFields(BaseModel):
    description: str | None = Field(None, max_length=120, description=PACKAGE_DESCRIPTION)
    net_quantity: float | None = Field(None, gt=0)
    net_unit: str | None = Field(None, description="g, kg, mg, ml, l ou un")
    units_per_pack: int | None = Field(None, ge=1)


class IdentifierCreate(IdentifierFields):
    product_id: str
    type: str = Field(..., description=f"Um de: {', '.join(IDENTIFIER_TYPES)}")
    value: str = Field(..., min_length=1, max_length=64)
    reason: str = REASON

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str | None) -> str | None:
        return normalize_identifier_type(value)


class IdentifierUpdate(IdentifierFields):
    type: str | None = Field(None, description=f"Um de: {', '.join(IDENTIFIER_TYPES)}")
    value: str | None = Field(None, min_length=1, max_length=64)
    reason: str = REASON

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str | None) -> str | None:
        return normalize_identifier_type(value)


class IdentifierDelete(BaseModel):
    reason: str = REASON


class IdentifierOut(IdentifierFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value: str


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    # Na leitura o NCM pode faltar: importação em lote grava produto com
    # NCM pendente de revisão. A escrita pela API sempre exige.
    ncm: str | None = None
    identifiers: list[IdentifierOut] = []
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
    note: str = "Limite máximo de itens por requisição. Use offset para paginar."


# +--------------------------------------------------------------------+
# |  NCM                                                               |
# +--------------------------------------------------------------------+
class NcmCreate(BaseModel):
    ncm: str = NCM_FIELD
    description: str = Field(..., min_length=1, max_length=500, description="Texto oficial da classificação.")
    source: str = Field(..., min_length=1, max_length=120)
    reason: str = REASON


class NcmUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=500)
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class NcmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ncm: str
    description: str
    chapter: str = Field(..., description="Capítulo: os 2 primeiros dígitos do NCM.")
    source: str
    created_at: datetime
    updated_at: datetime
