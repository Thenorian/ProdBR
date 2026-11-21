from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import register_contribution, require_contributor
from api.common import found_or_404, result_or_error
from api.rate_limit import limit_reads, limit_writes
from database.fiscal import FiscalDB
from util.validation import clean_cest, clean_ncm, clean_tax_regime, clean_uf

router = APIRouter(tags=["Regras fiscais"])

RATE = Field(None, ge=0, le=100)


class FiscalRuleInput(BaseModel):
    """
    Regra fiscal de referência para um NCM. uf, tax_regime e cest vazios valem para todos.
    Na criação, ncm, valid_from e source são obrigatórios. Na edição, mande só o que quer mudar.
    """
    ncm: str | None = None
    cest: str | None = None
    uf: str | None = Field(None, description="Sigla da UF. Vazio = todas.")
    tax_regime: str | None = Field(None, description="simples_nacional, lucro_presumido ou lucro_real. Vazio = todos.")
    icms_cst: str | None = Field(None, max_length=3)
    csosn: str | None = Field(None, max_length=3)
    icms_rate: float | None = RATE
    fcp_rate: float | None = RATE
    icms_st_mva_rate: float | None = Field(None, ge=0, le=1000)
    ipi_cst: str | None = Field(None, max_length=2)
    ipi_rate: float | None = Field(None, ge=0, le=1000, description="Até 1000%: cigarro tem IPI de 300%.")
    pis_cofins_cst: str | None = Field(None, max_length=2)
    pis_rate: float | None = RATE
    cofins_rate: float | None = RATE
    cbs_rate: float | None = RATE
    ibs_rate: float | None = RATE
    ii_rate: float | None = RATE
    notes: str | None = Field(None, max_length=500)
    valid_from: date | None = None
    valid_until: date | None = None
    source: str | None = Field(None, max_length=255, description="De onde veio a regra. Ex: TIPI, RICMS-SP")
    reason: str = Field(..., min_length=3, max_length=300)


@router.get("/fiscal-rules/{rule_id}", dependencies=[Depends(limit_reads)])
def get_fiscal_rule(rule_id: str):
    return found_or_404(result_or_error(FiscalDB().get(rule_id), 500), "Regra fiscal não encontrada.")


@router.post("/fiscal-rules", status_code=201, dependencies=[Depends(limit_writes)])
def create_fiscal_rule(payload: FiscalRuleInput, contributor=Depends(require_contributor)):
    data = clean_fiscal_rule_input(payload, payload.model_fields_set)
    for required_field, message in (("ncm_code", "Informe o NCM."), ("valid_from", "Informe valid_from."), ("source", "Informe a fonte (source).")):
        if not data.get(required_field):
            raise HTTPException(status_code=400, detail=message)

    fiscal = FiscalDB()
    rule_id = result_or_error(fiscal.create(data, contributor["username"], payload.reason))
    register_contribution(contributor, [field for field in data if data[field] is not None])
    return result_or_error(fiscal.get(rule_id), 500)


@router.put("/fiscal-rules/{rule_id}", dependencies=[Depends(limit_writes)])
def update_fiscal_rule(rule_id: str, payload: FiscalRuleInput, contributor=Depends(require_contributor)):
    changes = clean_fiscal_rule_input(payload, payload.model_fields_set - {"reason"})
    for required_field in ("ncm_code", "valid_from", "source"):
        if required_field in changes and not changes[required_field]:
            raise HTTPException(status_code=400, detail=f"{required_field} não pode ficar vazio.")

    fiscal = FiscalDB()
    changed_fields = result_or_error(fiscal.update(rule_id, changes, contributor["username"], payload.reason))
    register_contribution(contributor, changed_fields)
    return {"changed_fields": changed_fields, "fiscal_rule": result_or_error(fiscal.get(rule_id), 500)}


def clean_fiscal_rule_input(payload, sent_fields):
    """Converte os campos enviados para as colunas do banco, validando NCM, CEST, UF e regime."""
    data = {}

    checks = {
        "ncm": ("ncm_code", clean_ncm, "NCM inválido: use 8 dígitos."),
        "cest": ("cest", clean_cest, "CEST inválido: use 7 dígitos."),
        "uf": ("uf", clean_uf, "UF inválida."),
        "tax_regime": ("tax_regime", clean_tax_regime, "Regime inválido: use simples_nacional, lucro_presumido ou lucro_real."),
    }
    for field, (column, clean, error_message) in checks.items():
        if field in sent_fields:
            value = getattr(payload, field)
            data[column] = clean(value) if value else None
            if value and data[column] is None:
                raise HTTPException(status_code=400, detail=error_message)

    for field in ("icms_cst", "csosn", "ipi_cst", "pis_cofins_cst", "notes", "source"):
        if field in sent_fields:
            value = " ".join(str(getattr(payload, field) or "").split())
            data[field] = value or None

    for field in ("icms_rate", "fcp_rate", "icms_st_mva_rate", "ipi_rate", "pis_rate", "cofins_rate", "cbs_rate", "ibs_rate", "ii_rate"):
        if field in sent_fields:
            data[field] = getattr(payload, field)

    for field in ("valid_from", "valid_until"):
        if field in sent_fields:
            value = getattr(payload, field)
            data[field] = value.isoformat() if value else None

    return data
