"""Entrada e saída das regras fiscais.

As alíquotas andam sempre em `rates`, por código do tributo do país
(GET /countries/{país}/tax-types):

    {"ncm": "23091000", "country": "BR", "uf": "SP", "rates": {"ICMS": 18, "FCP": 2}, ...}

Na edição, `"ICMS": null` remove a alíquota da regra.

Compatibilidade: até a versão 0.2 cada tributo do Brasil tinha um campo
próprio (`icms_rate`, `ipi_rate`...). Eles continuam aceitos na entrada
(viram `rates`) e saindo na resposta, calculados a partir de `rates`.
"""

from datetime import date, datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.schemas.catalog import NCM_FIELD
from app.schemas.common import REASON

LEGACY_RATE_FIELDS = {
    "icms_rate": "ICMS",
    "fcp_rate": "FCP",
    "icms_st_mva_rate": "ICMS_ST_MVA",
    "ipi_rate": "IPI",
    "ii_rate": "II",
    "pis_rate": "PIS",
    "cofins_rate": "COFINS",
    "cbs_rate": "CBS",
    "ibs_rate": "IBS",
}

RATES_DESCRIPTION = 'Alíquota por código do tributo do país (ver /countries/{país}/tax-types). Ex: {"ICMS": 18, "FCP": 2}.'


class _AcceptsLegacyRates(BaseModel):
    """Move `icms_rate`, `ipi_rate`... recebidos pra dentro de `rates`."""

    @model_validator(mode="before")
    @classmethod
    def _legacy_to_rates(cls, data):
        if not isinstance(data, dict):
            return data
        legacy = {code: data[field] for field, code in LEGACY_RATE_FIELDS.items() if field in data}
        if not legacy:
            return data
        data = {k: v for k, v in data.items() if k not in LEGACY_RATE_FIELDS}
        data["rates"] = {**legacy, **(data.get("rates") or {})}
        return data


class FiscalRuleCreate(_AcceptsLegacyRates):
    ncm: str = NCM_FIELD
    cest: str | None = Field(None, max_length=7)
    country: str = Field("BR", min_length=2, max_length=2, description="País (ISO 3166-1 alpha-2, ver /countries).")
    uf: str | None = Field(None, min_length=1, max_length=5, description="Subdivisão (ver /countries/{país}/states). Vazio = regra nacional.")
    valid_from: date
    valid_until: date | None = None
    notes: str | None = Field(None, max_length=500, description="Isenção, monofásico, redução de base de cálculo etc.")
    source: str = Field(..., min_length=1, max_length=120, description="De onde vêm as alíquotas.")
    rates: dict[str, float | None] = Field(default_factory=dict, description=RATES_DESCRIPTION)
    reason: str = REASON


class FiscalRuleUpdate(_AcceptsLegacyRates):
    """NCM e país definem a regra e não mudam - pra outro NCM/país,
    encerre esta (`valid_until`) e cadastre outra."""

    cest: str | None = Field(None, max_length=7)
    uf: str | None = Field(None, min_length=1, max_length=5)
    valid_from: date | None = None
    valid_until: date | None = None
    notes: str | None = Field(None, max_length=500)
    source: str | None = Field(None, min_length=1, max_length=120)
    rates: dict[str, float | None] | None = Field(None, description=RATES_DESCRIPTION + " null remove.")
    reason: str = REASON


class FiscalRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ncm: str
    cest: str | None = None
    country: str = Field(validation_alias=AliasChoices("country", "country_id"))
    uf: str | None = Field(None, validation_alias=AliasChoices("uf", "state_code"))
    valid_from: date
    valid_until: date | None = None
    notes: str | None = None
    source: str
    rates: dict[str, float] = {}
    created_at: datetime

    # Campos legados (ver docstring do módulo) - só leitura.
    icms_rate: float | None = None
    fcp_rate: float | None = None
    icms_st_mva_rate: float | None = None
    ipi_rate: float | None = None
    ii_rate: float | None = None
    pis_rate: float | None = None
    cofins_rate: float | None = None
    cbs_rate: float | None = None
    ibs_rate: float | None = None

    @model_validator(mode="after")
    def _fill_legacy(self):
        for field, code in LEGACY_RATE_FIELDS.items():
            setattr(self, field, self.rates.get(code))
        return self


class NcmDetail(BaseModel):
    """Ficha do NCM: classificação + todas as regras (qualquer país/UF) +
    quantos produtos usam."""

    model_config = ConfigDict(from_attributes=True)

    ncm: str
    description: str
    chapter: str
    source: str
    created_at: datetime
    updated_at: datetime
    product_count: int = 0
    fiscal_rules: list[FiscalRuleOut] = []
