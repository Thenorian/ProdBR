"""
Envio para a fila de votação. Usado pelas rotas de escrita quando quem envia ainda é Iniciante:
em vez de gravar, a alteração fica esperando a comunidade votar (ver api/pending_changes.py).
"""
from fastapi.responses import JSONResponse

from api.common import result_or_error
from database.pending_change import PendingChangeDB


def send_to_review(action, target_id, payload, contributor):
    """
    Guarda na fila exatamente os campos que a pessoa enviou e responde 202 (aceito, mas ainda não gravado).

        send_to_review("update_product", product_id, payload, contributor)
        ->  202 {"status": "pending", "detail": "...", "pending_change": {...}}
    """
    sent_fields = payload.model_dump(mode="json", include=payload.model_fields_set - {"reason"})

    queue = PendingChangeDB()
    pending_change_id = result_or_error(
        queue.create(action, target_id, sent_fields, payload.reason, contributor["id"]), 500
    )
    pending_change = result_or_error(queue.get(pending_change_id), 500)

    return JSONResponse(status_code=202, content={
        "status": "pending",
        "detail": "Alteração enviada para a votação da comunidade. Ela é aplicada quando for aprovada.",
        "pending_change": pending_change,
    })
