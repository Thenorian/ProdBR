from database.database import Database


def revision_command(entity_type, entity_id, contributor, action, reason, field=None, old_value=None, new_value=None):
    """
    Monta o INSERT de uma linha do histórico, para entrar na mesma transação da alteração.

        revision_command("product", product_id, "kainan", "update", "Corrige marca", "brand", "Nestle", "Nestlé")
    """
    sql = (
        "INSERT INTO revisions (entity_type, entity_id, contributor, action, field, old_value, new_value, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    values = (
        entity_type,
        entity_id,
        contributor,
        action,
        field,
        None if old_value is None else str(old_value),
        None if new_value is None else str(new_value),
        reason,
    )
    return sql, values


class RevisionDB(Database):
    """Leitura do histórico público de alterações (o "git log" do ProdBR)."""

    def __init__(self):
        super().__init__()

    def list_for(self, entity_type, entity_id, limit, offset):
        """Histórico de um produto ou de uma regra fiscal, do mais novo para o mais antigo."""
        ok, total = self.count("revisions", where={"entity_type": entity_type, "entity_id": entity_id})
        if not ok:
            return False, total

        ok, items = self.select(
            "revisions",
            where={"entity_type": entity_type, "entity_id": entity_id},
            order_by="id DESC",
            limit=limit,
            offset=offset,
        )
        if not ok:
            return False, items

        return True, {"items": items, "total": total}

    def list_recent(self, limit, offset, contributor=None):
        """Últimas alterações de toda a base, com o nome do produto quando a alteração é num produto."""
        where_contributor = ""
        values = []
        if contributor:
            where_contributor = "WHERE revisions.contributor = ?"
            values.append(contributor)

        ok, total = self.run_sql(f"SELECT COUNT(*) AS total FROM revisions {where_contributor}", values, fetch="one")
        if not ok:
            return False, total

        sql = f"""
            SELECT revisions.*, products.name AS product_name
            FROM revisions
            LEFT JOIN products
                ON revisions.entity_type = 'product' AND products.id = revisions.entity_id
            {where_contributor}
            ORDER BY revisions.id DESC
            LIMIT ? OFFSET ?
        """
        ok, items = self.run_sql(sql, values + [limit, offset])
        if not ok:
            return False, items

        return True, {"items": items, "total": total["total"]}
