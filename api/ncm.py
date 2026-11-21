from fastapi import APIRouter, Depends, HTTPException

from api.common import DEFAULT_PAGE_SIZE, found_or_404, page_limits, result_or_error
from api.rate_limit import limit_reads
from database.fiscal import FiscalDB, summarize_fiscal_rules
from database.ncm import NcmDB
from util.validation import clean_ncm, clean_tax_regime, clean_uf

router = APIRouter(tags=["NCM"])


@router.get("/ncm", dependencies=[Depends(limit_reads)])
def search_ncm(q: str, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Busca na tabela oficial de NCM (Siscomex) pelo começo do código ou por palavra. Ex: q=cerveja"""
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Digite ao menos 2 caracteres.")

    limit, offset = page_limits(limit, offset)
    items = result_or_error(NcmDB().search(q.strip()[:100], limit, offset), 500)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/ncm/{code}", dependencies=[Depends(limit_reads)])
def get_ncm(code: str, uf: str | None = None, tax_regime: str | None = None):
    """NCM da tabela oficial com as regras fiscais em vigor para ele."""
    ncm_code = clean_ncm(code)
    if not ncm_code:
        raise HTTPException(status_code=400, detail="NCM inválido: use 8 dígitos.")

    ncm = found_or_404(result_or_error(NcmDB().get(ncm_code), 500), "NCM não está na tabela oficial.")
    uf, tax_regime = clean_uf(uf), clean_tax_regime(tax_regime)
    ncm["fiscal_rules"] = result_or_error(FiscalDB().list_applicable(ncm_code, uf, tax_regime), 500)
    ncm["fiscal_summary"] = summarize_fiscal_rules(ncm["fiscal_rules"], uf, tax_regime)
    return ncm
