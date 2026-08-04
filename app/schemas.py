from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models_public import IDENTIFIER_TYPES

REASON = Field(..., min_length=3, max_length=300, description="Motivo da alteracao (obrigatorio).")


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    ncm: str = Field(..., min_length=8, max_length=8, description="NCM com 8 digitos, sem pontuacao.")
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=120)
    commercial_unit: str = Field("UN", max_length=10)
    description: str | None = Field(None, max_length=1000)
    manufacturer: str | None = Field(None, max_length=120)
    source: str = Field(..., min_length=1, max_length=120, description="De onde veio esse cadastro.")


class ProductCreate(ProductBase):
    reason: str = REASON


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=120)
    commercial_unit: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=1000)
    manufacturer: str | None = Field(None, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class IdentifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value: str


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    # Nullable so de leitura: importacao em lote pode gerar produtos com
    # NCM pendente de revisao (ver importers/). Escrita via API continua
    # exigindo NCM normalmente (ProductCreate/ProductUpdate acima).
    ncm: str | None = Field(None, min_length=8, max_length=8)
    identifiers: list[IdentifierOut] = []
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
    note: str = "Limite maximo de itens por requisicao. Use offset para paginar."


class IdentifierCreate(BaseModel):
    product_id: str
    type: str = Field(..., description=f"Um de: {', '.join(IDENTIFIER_TYPES)}")
    value: str = Field(..., min_length=1, max_length=64)
    reason: str = REASON


class IdentifierDelete(BaseModel):
    reason: str = REASON


class FiscalRuleBase(BaseModel):
    ncm: str = Field(..., min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    uf: str | None = Field(None, min_length=2, max_length=2, description="Sigla do estado, ou nulo para regra nacional/default.")
    origin: int | None = Field(None, ge=0, le=8)
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=100)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100)
    ibs_rate: float | None = Field(None, ge=0, le=100)
    valid_from: date
    valid_until: date | None = None
    source: str = Field(..., min_length=1, max_length=120)


class FiscalRuleCreate(FiscalRuleBase):
    reason: str = REASON


class FiscalRuleUpdate(BaseModel):
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    uf: str | None = Field(None, min_length=2, max_length=2)
    origin: int | None = Field(None, ge=0, le=8)
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=100)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100)
    ibs_rate: float | None = Field(None, ge=0, le=100)
    valid_from: date | None = None
    valid_until: date | None = None
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class FiscalRuleOut(FiscalRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    contributor: str | None
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str
    created_at: datetime
