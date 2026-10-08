"""Entrada e saída dos dados de referência: país, subdivisão e tributo."""

from pydantic import BaseModel, ConfigDict, Field

TAX_LEVELS = ("national", "state")
TAX_UNITS = ("percent", "amount")


class CountryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    language: str
    subdivision_label: str


class CountryCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (ex: CL).")
    name: str = Field(..., min_length=1, max_length=50)
    language: str = Field("pt-BR", min_length=2, max_length=10, description="Idioma padrão das respostas (BCP 47, ex: es-CL).")
    subdivision_label: str = Field("UF", min_length=1, max_length=30, description="Como o país chama a subdivisão (UF, Provincia, Región...).")


class CountryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    language: str | None = Field(None, min_length=2, max_length=10)
    subdivision_label: str | None = Field(None, min_length=1, max_length=30)


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    country_id: str


class StateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=5)
    name: str = Field(..., min_length=1, max_length=80)


class TaxTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    country_id: str
    code: str
    name: str
    translations: dict[str, str] | None = None
    description: str | None = None
    level: str
    unit: str
    default_rate: float | None = None
    default_source: str | None = None
    sort_order: int
    active: bool


class TaxTypeCreate(BaseModel):
    country_id: str = Field(..., min_length=2, max_length=2)
    code: str = Field(..., min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_]+$", description="Sigla do tributo (ex: IVA, IIBB).")
    name: str = Field(..., min_length=1, max_length=120, description="Nome oficial no idioma do país.")
    translations: dict[str, str] | None = Field(None, description='Nome em outros idiomas: {"pt": ..., "es": ..., "en": ...}.')
    description: str | None = Field(None, max_length=500)
    level: str = Field("national", pattern="^(national|state)$")
    unit: str = Field("percent", pattern="^(percent|amount)$")
    default_rate: float | None = Field(None, ge=0)
    default_source: str | None = Field(None, max_length=120)
    sort_order: int = 0
    active: bool = True


class TaxTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    translations: dict[str, str] | None = None
    description: str | None = Field(None, max_length=500)
    level: str | None = Field(None, pattern="^(national|state)$")
    unit: str | None = Field(None, pattern="^(percent|amount)$")
    default_rate: float | None = Field(None, ge=0)
    default_source: str | None = Field(None, max_length=120)
    sort_order: int | None = None
    active: bool | None = None
