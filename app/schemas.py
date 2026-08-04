from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    ncm: str = Field(..., min_length=8, max_length=8, description="NCM com 8 digitos, sem pontuacao.")
    cest: str | None = Field(None, max_length=7)
    description: str = Field(..., min_length=1, max_length=255)
    unit: str = Field("UN", max_length=10)

    gross_weight: float | None = None
    net_weight: float | None = None

    origin: int | None = Field(None, ge=0, le=8, description="Codigo de origem ICMS (0 a 8).")
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=100)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100)
    ibs_rate: float | None = Field(None, ge=0, le=100)


class ProductCreate(ProductBase):
    barcodes: list[str] = Field(..., min_length=1, description="Um ou mais codigos de barras/GTIN.")


class ProductUpdate(BaseModel):
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    description: str | None = Field(None, min_length=1, max_length=255)
    unit: str | None = Field(None, max_length=10)
    gross_weight: float | None = None
    net_weight: float | None = None
    origin: int | None = Field(None, ge=0, le=8)
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=100)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100)
    ibs_rate: float | None = Field(None, ge=0, le=100)
    barcodes: list[str] | None = Field(None, min_length=1)


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcodes: list[str]
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
    note: str = "Limite maximo de itens por requisicao. Use offset para paginar."


class ChangeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    action: str
    diff: dict
    created_at: datetime
