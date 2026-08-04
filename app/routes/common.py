from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession


def apply_or_400(fn, *args, **kwargs):
    """Converte um ValueError de negocio (ex: conflito, entidade sumiu
    entre a proposta e a aprovacao) em HTTP 400 com a mensagem original."""
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def get_or_404(db: DbSession, model, entity_id, label: str):
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} nao encontrado.")
    return entity


def write_response(result: dict, applied_status: int, out_model: type[BaseModel] | None):
    """Uniformiza a resposta do motor de contribuicoes (app/changes.py):
    mudanca aplicada direto -> `applied_status` com a entidade; mudanca
    que foi para a fila de moderacao -> 202 com o id do PendingChange."""
    if result["status"] == "applied":
        entity = result["entity"]
        if entity is not None and out_model is not None:
            content = jsonable_encoder(out_model.model_validate(entity))
        else:
            content = {"status": "deleted"}
        return JSONResponse(status_code=applied_status, content=content)

    pending = result["pending_change"]
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "pending",
            "pending_change_id": pending.id,
            "message": (
                "Reputacao insuficiente para aplicacao automatica - "
                "contribuicao enviada para a fila de moderacao."
            ),
        },
    )
