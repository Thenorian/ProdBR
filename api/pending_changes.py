"""
Fila de votação, no estilo do Reddit.

Quem ainda é Iniciante não grava direto: a alteração fica aqui esperando votos.
Qualquer contribuidor com conta de mais de 24 horas vota a favor (1) ou contra (-1),
menos o próprio autor. Saldo +3 aplica a alteração em nome do autor; saldo -3 descarta.
O voto de um moderador decide sozinho.

Cada voto também mexe na reputação do autor: +1 a favor, -1 contra. É assim que um
Iniciante chega a Editor e passa a gravar direto.
"""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from api import categories, companies, fiscal, products
from api.auth import require_contributor
from api.common import DEFAULT_PAGE_SIZE, found_or_404, page_limits, result_or_error
from api.rate_limit import limit_reads, limit_writes
from database.contributor import ContributorDB
from database.pending_change import PendingChangeDB

router = APIRouter(tags=["Fila de votação"])

SCORE_TO_APPROVE = 3
SCORE_TO_REJECT = -3
MINIMUM_ACCOUNT_AGE_TO_VOTE = timedelta(hours=24)
LISTABLE_STATUSES = ("pending", "approved", "rejected", "failed")

# O que cada alteração da fila faz quando é aprovada: o formulário que ela usou
# e a mesma função que a rota chama quando a pessoa grava direto.
ACTIONS = {
    "create_product": (products.ProductInput, products.apply_new_product),
    "update_product": (products.ProductInput, products.apply_product_changes),
    "create_fiscal_rule": (fiscal.FiscalRuleInput, fiscal.apply_new_fiscal_rule),
    "update_fiscal_rule": (fiscal.FiscalRuleInput, fiscal.apply_fiscal_rule_changes),
    "create_category": (categories.NewCategoryInput, categories.apply_new_category),
    "update_category": (categories.CategoryChangesInput, categories.apply_category_changes),
    "delete_category": (categories.DeleteCategoryInput, categories.apply_category_deletion),
    "create_company": (companies.CompanyInput, companies.apply_new_company),
    "update_company": (companies.CompanyInput, companies.apply_company_changes),
}


class VoteInput(BaseModel):
    vote: int = Field(..., ge=-1, le=1, description="1 a favor, -1 contra, 0 retira o seu voto.")


@router.get("/pending-changes", dependencies=[Depends(limit_reads)])
def list_pending_changes(status: str = "pending", limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """
    Alterações esperando votos (status=pending), da mais antiga para a mais nova.
    Também lista as já decididas: approved, rejected ou failed (aprovada, mas não deu para aplicar).
    """
    if status not in LISTABLE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status deve ser um de: {', '.join(LISTABLE_STATUSES)}.")

    limit, offset = page_limits(limit, offset)
    found = result_or_error(PendingChangeDB().list_by_status(status, limit, offset), 500)
    return {**found, "limit": limit, "offset": offset}


@router.get("/pending-changes/{pending_change_id}", dependencies=[Depends(limit_reads)])
def get_pending_change(pending_change_id: str):
    pending_change = result_or_error(PendingChangeDB().get(pending_change_id), 500)
    return found_or_404(pending_change, "Alteração não encontrada na fila.")


@router.post("/pending-changes/{pending_change_id}/votes", dependencies=[Depends(limit_writes)])
def vote_on_pending_change(pending_change_id: str, payload: VoteInput, voter=Depends(require_contributor)):
    """
    Vota numa alteração da fila: 1 a favor, -1 contra, 0 retira o voto. Pode trocar o voto
    enquanto ela estiver pendente. Saldo +3 aplica, -3 descarta. Devolve a alteração atualizada.
    """
    queue = PendingChangeDB()
    pending_change = result_or_error(queue.get_internal(pending_change_id), 500)
    found_or_404(pending_change, "Alteração não encontrada na fila.")

    if pending_change["status"] != "pending":
        raise HTTPException(status_code=409, detail="Essa alteração já foi decidida.")
    if pending_change["contributor_id"] == voter["id"]:
        raise HTTPException(status_code=403, detail="Você não pode votar na sua própria alteração.")
    if not voter["moderator"] and not account_is_old_enough_to_vote(voter):
        raise HTTPException(status_code=403, detail="Contas com menos de 24 horas ainda não votam.")
    if voter["moderator"] and payload.vote == 0:
        raise HTTPException(status_code=400, detail="Moderador decide com 1 (aprova) ou -1 (descarta).")

    vote_result = result_or_error(queue.save_vote(pending_change_id, voter["id"], payload.vote), 500)
    if vote_result["difference"]:
        ContributorDB().add_reputation(pending_change["contributor_id"], vote_result["difference"])

    if voter["moderator"]:
        decide(pending_change, approved=payload.vote == 1)
    elif vote_result["score"] >= SCORE_TO_APPROVE:
        decide(pending_change, approved=True)
    elif vote_result["score"] <= SCORE_TO_REJECT:
        decide(pending_change, approved=False)

    return result_or_error(queue.get(pending_change_id), 500)


def account_is_old_enough_to_vote(contributor):
    """
    created_at está em UTC. O SQLite grava "2026-11-24 18:13:53"; contas importadas da
    versão antiga podem vir como "2026-08-08T15:03:11.123456". Os 19 primeiros caracteres bastam.
    """
    created_at_text = str(contributor["created_at"])[:19].replace("T", " ")
    created_at = datetime.strptime(created_at_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created_at >= MINIMUM_ACCOUNT_AGE_TO_VOTE


def decide(pending_change, approved):
    """
    Aplica (em nome do autor) ou descarta a alteração.
    Se a aplicação falhar (ex: o produto foi apagado nesse meio tempo), ela fica como
    failed, com o motivo em result_message, e nada é gravado pela metade.
    """
    queue = PendingChangeDB()
    pending_change_id = pending_change["id"]

    ok, this_request_decides = queue.take_for_decision(pending_change_id)
    if not ok or not this_request_decides:
        return

    if not approved:
        queue.finish(pending_change_id, "rejected")
        return

    try:
        input_model, apply_change = ACTIONS[pending_change["action"]]
        author = result_or_error(ContributorDB().get_by_id(pending_change["contributor_id"]), 500)
        sent_fields = json.loads(pending_change["payload"])
        payload = input_model(**sent_fields, reason=pending_change["reason"])

        apply_change(pending_change["target_id"], payload, author)
        queue.finish(pending_change_id, "approved")

    except HTTPException as error:
        queue.finish(pending_change_id, "failed", str(error.detail))
    except ValidationError as error:
        queue.finish(pending_change_id, "failed", f"Os dados enviados não são mais válidos: {error.error_count()} erro(s).")
    except Exception:
        queue.finish(pending_change_id, "failed", "Erro inesperado ao aplicar a alteração.")
        raise
