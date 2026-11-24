from fastapi import APIRouter, Depends, HTTPException

from api.common import result_or_error
from api.rate_limit import limit_reads
from database.ibpt import IbptDB
from util.validation import clean_uf

router = APIRouter(tags=["IBPT"])

IBPT_NOTE = "Valores aproximados da tabela do IBPT, para a Lei 12.741/2012 (tributos na nota e no cupom)."


@router.get("/ibpt", dependencies=[Depends(limit_reads)])
def list_ibpt_versions():
    """Versão vigente da tabela do IBPT de cada UF que está na base."""
    return {"items": result_or_error(IbptDB().list_versions(), 500), "note": IBPT_NOTE}


@router.get("/ibpt/{code}", dependencies=[Depends(limit_reads)])
def get_ibpt_rates(code: str, uf: str):
    """
    Carga tributária aproximada de um NCM, NBS ou item da LC 116 numa UF.
    Taxas em percentual: federal (nacional ou importado), estadual e municipal.
    item_type: 0 = NCM (produto), 1 = NBS (serviço), 2 = LC 116 (serviço).
    """
    clean_code = "".join(character for character in code if character.isdigit())
    if not 2 <= len(clean_code) <= 9:
        raise HTTPException(status_code=400, detail="Código inválido: use de 2 a 9 dígitos.")
    if clean_uf(uf) is None:
        raise HTTPException(status_code=400, detail="UF inválida.")

    rows = result_or_error(IbptDB().list_by_code(clean_code, clean_uf(uf)), 500)
    if not rows:
        raise HTTPException(status_code=404, detail="Código não encontrado na tabela do IBPT dessa UF.")
    return {"items": rows, "note": IBPT_NOTE}
