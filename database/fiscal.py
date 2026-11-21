from datetime import date
from uuid import uuid4

from database.category import now_text
from database.database import Database
from database.revision import revision_command

FISCAL_RULE_FIELDS = (
    "ncm_code", "cest", "uf", "tax_regime",
    "icms_cst", "csosn", "icms_rate", "fcp_rate", "icms_st_mva_rate",
    "ipi_cst", "ipi_rate",
    "pis_cofins_cst", "pis_rate", "cofins_rate",
    "cbs_rate", "ibs_rate", "ii_rate",
    "notes", "valid_from", "valid_until", "source",
)


class FiscalDB(Database):
    """
    Regras fiscais de referência, por NCM. O produto não tem regra própria:
    ele usa as regras do NCM dele (ou do NCM herdado da categoria).
    """

    def __init__(self):
        super().__init__()

    def list_applicable(self, ncm_code, uf=None, tax_regime=None, cest=None, on_date=None):
        """
        Regras em vigor para um NCM, da mais específica para a mais genérica.
        O ERP normalmente usa a primeira da lista.

            list_applicable("22030000", uf="SP", tax_regime="lucro_presumido")

        Sem uf (ou regime), traz as regras de todas as UFs (ou regimes).
        Com uf, traz as regras daquela UF e as que valem para todas (uf vazia).
        """
        on_date = (on_date or date.today()).isoformat()

        conditions = ["ncm_code = ?", "valid_from <= ?", "(valid_until IS NULL OR valid_until >= ?)"]
        values = [ncm_code, on_date, on_date]

        optional_filters = {"uf": uf, "tax_regime": tax_regime, "cest": cest}
        for column, value in optional_filters.items():
            if value:
                conditions.append(f"({column} IS NULL OR {column} = ?)")
                values.append(value)

        sql = f"""
            SELECT *
            FROM fiscal_rules
            WHERE {" AND ".join(conditions)}
            ORDER BY
                (cest IS NOT NULL) DESC,
                (uf IS NOT NULL) DESC,
                (tax_regime IS NOT NULL) DESC,
                valid_from DESC
        """
        return self.run_sql(sql, values)

    def get(self, rule_id):
        return self.select("fiscal_rules", where={"id": rule_id}, fetch="one")

    def create(self, data, contributor, reason):
        """Cria a regra e grava um registro no histórico para cada campo preenchido."""
        rule_id = str(uuid4())
        filled_fields = [field for field in FISCAL_RULE_FIELDS if data.get(field) is not None]

        columns = ", ".join(["id", *filled_fields])
        placeholders = ", ".join(["?"] * (len(filled_fields) + 1))
        commands = [(
            f"INSERT INTO fiscal_rules ({columns}) VALUES ({placeholders})",
            [rule_id, *[data[field] for field in filled_fields]],
        )]

        for field in filled_fields:
            commands.append(revision_command("fiscal_rule", rule_id, contributor, "create", reason, field, None, data[field]))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, rule_id

    def update(self, rule_id, changes, contributor, reason):
        """Altera a regra e grava no histórico só os campos que mudaram. Devolve a lista de campos alterados."""
        ok, current = self.get(rule_id)
        if not ok:
            return False, current
        if current is None:
            return False, "Regra fiscal não encontrada."

        changed_fields = [field for field, value in changes.items() if current[field] != value]
        if not changed_fields:
            return True, []

        set_sql = ", ".join(f"{self._quote(field)} = ?" for field in changed_fields)
        values = [changes[field] for field in changed_fields] + [now_text(), rule_id]
        commands = [(f"UPDATE fiscal_rules SET {set_sql}, updated_at = ? WHERE id = ?", values)]

        for field in changed_fields:
            commands.append(
                revision_command("fiscal_rule", rule_id, contributor, "update", reason, field, current[field], changes[field])
            )

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, changed_fields
