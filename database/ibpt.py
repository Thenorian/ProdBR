from database.database import Database

IBPT_PUBLIC_COLUMNS = [
    "code", "ex", "item_type", "uf", "description",
    "federal_national_rate", "federal_imported_rate", "state_rate", "municipal_rate",
    "valid_from", "valid_until", "version", "source",
]
PRODUCT_ITEM_TYPE = 0


class IbptDB(Database):
    """
    Tabela do IBPT: carga tributária aproximada por código e UF (Lei 12.741/2012).
    Fica só a versão vigente de cada UF.
    """

    def __init__(self):
        super().__init__()

    def current_version(self, uf):
        """Versão gravada da UF (ex: "26.2.C"), ou None se a UF ainda não foi importada."""
        ok, row = self.select("ibpt_rates", ["version"], where={"uf": uf}, fetch="one")
        if not ok:
            return False, row
        return True, row and row["version"]

    def replace_state_table(self, uf, version, rows):
        """
        Troca todas as linhas da UF pelas da versão nova, numa transação só:
        se algo der errado, a versão anterior continua inteira.

            IbptDB().replace_state_table("SP", "26.2.C", [{"code": "22030000", ...}, ...])
        """
        insert_sql = (
            "INSERT INTO ibpt_rates (uf, code, ex, item_type, description, federal_national_rate, "
            "federal_imported_rate, state_rate, municipal_rate, valid_from, valid_until, version, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        commands = [("DELETE FROM ibpt_rates WHERE uf = ?", (uf,))]
        for row in rows:
            commands.append((insert_sql, (
                uf, row["code"], row["ex"], row["item_type"], row["description"],
                row["federal_national_rate"], row["federal_imported_rate"], row["state_rate"], row["municipal_rate"],
                row["valid_from"], row["valid_until"], version, row["source"],
            )))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error
        return True, len(rows)

    def get_for_product(self, ncm_code, uf):
        """
        Linha do IBPT para um NCM de produto numa UF, ou (True, None).
        O produto não tem exceção da TIPI, então vale a linha sem "ex".
        """
        if not ncm_code or not uf:
            return True, None
        return self.select(
            "ibpt_rates", IBPT_PUBLIC_COLUMNS,
            where={"uf": uf, "item_type": PRODUCT_ITEM_TYPE, "code": ncm_code, "ex": ""}, fetch="one",
        )

    def list_by_code(self, code, uf):
        """Todas as linhas de um código numa UF (com e sem exceção da TIPI, produto e serviço)."""
        return self.select(
            "ibpt_rates", IBPT_PUBLIC_COLUMNS, where={"uf": uf, "code": code}, order_by=["item_type", "ex"]
        )

    def list_versions(self):
        """Versão vigente de cada UF importada: [{"uf": "SP", "version": "26.2.C", "total": 12162}, ...]"""
        return self.run_sql(
            "SELECT uf, version, COUNT(*) AS total, MAX(valid_until) AS valid_until "
            "FROM ibpt_rates GROUP BY uf, version ORDER BY uf"
        )
