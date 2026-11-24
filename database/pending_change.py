import json
from datetime import datetime, timezone
from uuid import uuid4

from database.database import CommunityDatabase

PENDING_CHANGE_PUBLIC_COLUMNS = """
    pending_changes.id, pending_changes.action, pending_changes.target_id, pending_changes.payload,
    pending_changes.reason, pending_changes.status, pending_changes.score, pending_changes.result_message,
    pending_changes.created_at, pending_changes.resolved_at, contributors.username AS contributor
"""


def now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def readable_pending_change(row):
    """Linha do banco -> formato da API, com o payload já como objeto em vez de texto JSON."""
    if row is None:
        return None
    return {**row, "payload": json.loads(row["payload"])}


class PendingChangeDB(CommunityDatabase):
    """
    Fila de votação: as alterações de quem ainda é Iniciante esperam aqui até a comunidade decidir.
    Funciona como no Reddit: cada voto a favor soma 1, cada voto contra tira 1.
    """

    def __init__(self):
        super().__init__()

    def create(self, action, target_id, payload, reason, contributor_id):
        """
        Coloca uma alteração na fila e devolve o id dela.

            PendingChangeDB().create("update_product", product_id, {"brand": "Nestlé"}, "Corrige marca", contributor_id)
        """
        pending_change_id = str(uuid4())
        ok, error = self.insert("pending_changes", {
            "id": pending_change_id,
            "action": action,
            "target_id": target_id,
            "payload": json.dumps(payload, ensure_ascii=False, default=str),
            "reason": reason,
            "contributor_id": contributor_id,
        })
        if not ok:
            return False, error
        return True, pending_change_id

    def get(self, pending_change_id):
        """(True, alteração) no formato público, ou (True, None) se não existe."""
        sql = f"""
            SELECT {PENDING_CHANGE_PUBLIC_COLUMNS}
            FROM pending_changes
            JOIN contributors ON contributors.id = pending_changes.contributor_id
            WHERE pending_changes.id = ?
        """
        ok, row = self.run_sql(sql, (pending_change_id,), fetch="one")
        if not ok:
            return False, row
        return True, readable_pending_change(row)

    def get_internal(self, pending_change_id):
        """A linha completa, com o contributor_id do autor. Nunca sai pela API."""
        return self.select("pending_changes", where={"id": pending_change_id}, fetch="one")

    def list_by_status(self, status, limit, offset):
        """Fila em ordem de chegada: a mais antiga primeiro, para ninguém ficar esquecido no fim."""
        ok, total = self.count("pending_changes", where={"status": status})
        if not ok:
            return False, total

        oldest_first = "ASC" if status == "pending" else "DESC"
        sql = f"""
            SELECT {PENDING_CHANGE_PUBLIC_COLUMNS}
            FROM pending_changes
            JOIN contributors ON contributors.id = pending_changes.contributor_id
            WHERE pending_changes.status = ?
            ORDER BY pending_changes.created_at {oldest_first}, pending_changes.id
            LIMIT ? OFFSET ?
        """
        ok, rows = self.run_sql(sql, (status, limit, offset))
        if not ok:
            return False, rows

        return True, {"items": [readable_pending_change(row) for row in rows], "total": total}

    def save_vote(self, pending_change_id, voter_id, vote):
        """
        Grava, troca ou retira (vote = 0) o voto de uma pessoa e recalcula o saldo.
        Devolve (True, {"score": saldo novo, "difference": quanto o saldo mudou}).
        """
        ok, previous = self.select(
            "pending_change_votes", ["vote"],
            where={"pending_change_id": pending_change_id, "contributor_id": voter_id}, fetch="one",
        )
        if not ok:
            return False, previous
        previous_vote = previous["vote"] if previous else 0

        where_this_vote = "WHERE pending_change_id = ? AND contributor_id = ?"
        if vote == 0:
            command = (f"DELETE FROM pending_change_votes {where_this_vote}", (pending_change_id, voter_id))
        elif previous:
            command = (f"UPDATE pending_change_votes SET vote = ? {where_this_vote}", (vote, pending_change_id, voter_id))
        else:
            command = (
                "INSERT INTO pending_change_votes (pending_change_id, contributor_id, vote) VALUES (?, ?, ?)",
                (pending_change_id, voter_id, vote),
            )

        recalculate_score = (
            "UPDATE pending_changes SET score = "
            "(SELECT COALESCE(SUM(vote), 0) FROM pending_change_votes WHERE pending_change_id = ?) WHERE id = ?",
            (pending_change_id, pending_change_id),
        )
        ok, error = self.run_in_transaction([command, recalculate_score])
        if not ok:
            return False, error

        ok, row = self.select("pending_changes", ["score"], where={"id": pending_change_id}, fetch="one")
        if not ok:
            return False, row
        return True, {"score": row["score"], "difference": vote - previous_vote}

    def take_for_decision(self, pending_change_id):
        """
        Marca a alteração como "deciding" só se ela ainda estiver pendente.
        Dois votos chegando juntos não aplicam a mesma alteração duas vezes:
        só quem conseguiu marcar (True, True) segue em frente.
        """
        sql = "UPDATE pending_changes SET status = 'deciding' WHERE id = ? AND status = 'pending'"
        ok, changed_rows = self.run_sql(sql, (pending_change_id,), fetch="rowcount")
        if not ok:
            return False, changed_rows
        return True, changed_rows == 1

    def finish(self, pending_change_id, status, result_message=None):
        """status final: approved, rejected ou failed."""
        return self.update(
            "pending_changes",
            {"status": status, "result_message": result_message, "resolved_at": now_text()},
            where={"id": pending_change_id},
        )
