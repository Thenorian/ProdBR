from datetime import date, timedelta
from uuid import uuid4

from database.category import now_text
from database.database import Database
from database.revision import revision_command

# Mesmo prefixo de util/official_data.py: identifica as regras que vêm do governo, não da comunidade.
OFFICIAL_SOURCE_PREFIX = "Oficial: "

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

    def apply_official_rates(self, federal_rates, today=None):
        """
        Grava o IPI (TIPI) e o II (TEC) oficiais: uma regra nacional por NCM, com fonte "Oficial: ...".
        federal_rates vem de util/official_data.py::download_federal_rates.

        Só mexe nas regras oficiais em vigor; as cadastradas pela comunidade ficam intactas.
        Alíquota igual: nada muda. Alíquota diferente: a regra antiga é encerrada ontem e nasce
        uma nova a partir de hoje, então o histórico das alíquotas continua consultável.

            ok, totals = FiscalDB().apply_official_rates(federal_rates)
            totals  ->  {"created": 3, "changed": 1, "unchanged": 10512}
        """
        today = today or date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        source = federal_rates["source"]

        ok, current_rules = self.run_sql(
            """SELECT * FROM fiscal_rules
               WHERE source LIKE ? AND uf IS NULL AND cest IS NULL AND tax_regime IS NULL AND valid_until IS NULL""",
            (OFFICIAL_SOURCE_PREFIX + "%",),
        )
        if not ok:
            return False, current_rules
        current_rule_by_ncm = {rule["ncm_code"]: rule for rule in current_rules}

        ipi_by_ncm = federal_rates["ipi_by_ncm"]
        ii_by_ncm = federal_rates["ii_by_ncm"]
        commands = []
        totals = {"created": 0, "changed": 0, "unchanged": 0}

        for ncm_code in sorted(set(ipi_by_ncm) | set(ii_by_ncm)):
            new_values = {
                "ipi_rate": ipi_by_ncm.get(ncm_code),
                "ii_rate": ii_by_ncm.get(ncm_code),
                "notes": official_notes(ncm_code, ipi_by_ncm, federal_rates["ipi_exceptions_by_ncm"]),
            }
            current_rule = current_rule_by_ncm.get(ncm_code)

            if current_rule and all(current_rule[field] == value for field, value in new_values.items()):
                totals["unchanged"] += 1
                if current_rule["source"] != source:
                    commands.append(("UPDATE fiscal_rules SET source = ? WHERE id = ?", (source, current_rule["id"])))
                continue

            same_rates = current_rule and all(
                current_rule[field] == new_values[field] for field in ("ipi_rate", "ii_rate")
            )
            created_today = current_rule and current_rule["valid_from"] >= today.isoformat()

            if same_rates or created_today:
                # Só o texto mudou, ou a regra é de hoje mesmo: corrige no lugar, sem nova versão.
                commands.append((
                    "UPDATE fiscal_rules SET ipi_rate = ?, ii_rate = ?, notes = ?, source = ?, updated_at = ? WHERE id = ?",
                    (*new_values.values(), source, now_text(), current_rule["id"]),
                ))
                totals["changed"] += 1
                continue

            if current_rule:
                commands.append((
                    "UPDATE fiscal_rules SET valid_until = ?, updated_at = ? WHERE id = ?",
                    (yesterday, now_text(), current_rule["id"]),
                ))
                totals["changed"] += 1
            else:
                totals["created"] += 1

            commands.append((
                """INSERT INTO fiscal_rules (id, ncm_code, ipi_rate, ii_rate, notes, valid_from, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid4()), ncm_code, *new_values.values(), today.isoformat(), source),
            ))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, totals


def official_notes(ncm_code, ipi_by_ncm, ipi_exceptions_by_ncm):
    """Observações da regra oficial: IPI não tributado (NT) e as exceções (Ex) da TIPI."""
    parts = []
    if ncm_code in ipi_by_ncm and ipi_by_ncm[ncm_code] is None:
        parts.append("IPI: NT (não tributado, fora do campo de incidência do IPI).")
    if ipi_exceptions_by_ncm.get(ncm_code):
        parts.append("IPI diferente para: " + "; ".join(ipi_exceptions_by_ncm[ncm_code]) + ".")

    text = " ".join(parts)
    if len(text) > 500:
        return text[:497] + "..."
    return text or None


TAX_SUMMARY_FIELDS = (
    "icms_cst", "csosn", "icms_rate", "fcp_rate", "icms_st_mva_rate",
    "ipi_cst", "ipi_rate", "pis_cofins_cst", "pis_rate", "cofins_rate",
    "cbs_rate", "ibs_rate", "ii_rate",
)


def summarize_fiscal_rules(rules, uf=None, tax_regime=None):
    """
    Junta as regras num quadro só, campo a campo: cada tributo vem da regra mais específica
    que tem ele preenchido. Ex: ICMS da regra de SP + IPI e II da regra oficial nacional.

    Regras de uma UF (ou regime) só entram se essa UF (ou regime) foi pedida;
    sem uf, o quadro mostra só o que vale para o país todo.

        summarize_fiscal_rules(rules, uf="SP")
        ->  {"icms_rate": 18.0, "ipi_rate": 6.5, ..., "sources": {"icms_rate": "RICMS-SP", "ipi_rate": "Oficial: TIPI ..."}}
    """
    summary = {field: None for field in TAX_SUMMARY_FIELDS}
    summary["sources"] = {}

    for rule in rules:
        if rule["uf"] and rule["uf"] != uf:
            continue
        if rule["tax_regime"] and rule["tax_regime"] != tax_regime:
            continue

        for field in TAX_SUMMARY_FIELDS:
            if summary[field] is None and rule[field] is not None:
                summary[field] = rule[field]
                summary["sources"][field] = rule["source"]

    return summary
