import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from database.database import CommunityDatabase


def hash_token(token):
    """O token é aleatório e longo, então SHA-256 basta (não é senha escolhida por pessoa)."""
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


class ContributorDB(CommunityDatabase):
    """
    Quem contribui com a base. Funciona como o Git: um nome de usuário público
    e um token secreto que assina as alterações. Sem e-mail e sem senha.

    A reputação fica só aqui e só aparece no site, nunca na API.
    """

    def __init__(self):
        super().__init__()

    def create(self, username):
        """
        Cria o contribuidor e devolve o token. O token só aparece aqui, uma única vez.

            ok, result = ContributorDB().create("kainan")
            result  ->  {"username": "kainan", "token": "..."}
        """
        ok, already_exists = self.exists("contributors", where={"username": username})
        if not ok:
            return False, already_exists
        if already_exists:
            return False, f"O usuário {username} já existe. Escolha outro nome."

        contributor_id = str(uuid4())
        ok, error = self.insert("contributors", {"id": contributor_id, "username": username})
        if not ok:
            return False, error

        return self._create_token(contributor_id, username)

    def create_new_token(self, contributor):
        """Gera mais um token para quem já tem um (ex: um token por ERP). Os antigos continuam valendo."""
        return self._create_token(contributor["id"], contributor["username"])

    def find_by_token(self, token):
        """(True, contribuidor) ou (True, None) se o token não existe."""
        sql = """
            SELECT contributors.*
            FROM contributor_tokens
            JOIN contributors ON contributors.id = contributor_tokens.contributor_id
            WHERE contributor_tokens.token_hash = ?
        """
        return self.run_sql(sql, (hash_token(token),), fetch="one")

    def register_contribution(self, contributor_id, edits):
        """Cada campo alterado vale um ponto de reputação."""
        sql = """
            UPDATE contributors
            SET reputation = reputation + ?, edit_count = edit_count + ?, last_contribution_at = ?
            WHERE id = ?
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return self.run_sql(sql, (edits, edits, now, contributor_id), fetch="rowcount")

    def get_by_username(self, username):
        return self.select(
            "contributors",
            ["username", "reputation", "edit_count", "created_at", "last_contribution_at"],
            where={"username": username},
            fetch="one",
        )

    def list_ranking(self, limit):
        return self.select(
            "contributors",
            ["username", "reputation", "edit_count", "created_at", "last_contribution_at"],
            where={"edit_count": (">", 0)},
            order_by=["reputation DESC", "username"],
            limit=limit,
        )

    def _create_token(self, contributor_id, username):
        token = secrets.token_urlsafe(32)
        ok, error = self.insert(
            "contributor_tokens", {"token_hash": hash_token(token), "contributor_id": contributor_id}
        )
        if not ok:
            return False, error

        return True, {"username": username, "token": token}
