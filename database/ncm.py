import re
from datetime import datetime, timezone
from uuid import uuid4

from database.database import Database

FINAL_LEVEL = "subitem"
ONLY_DIGITS = re.compile(r"^[0-9]{2,8}$")



class NcmDB(Database):

    def __init__(self):
        super().__init__()

    def save_table(self, table, file_name):
        """
        Grava a tabela de NCM já lida pelo DataUtil.read_ncm_file.

            ok, summary = NcmDB().save_table(table, "Tabela_NCM_Vigente_20261121.json")
            summary  ->  {"import_id": "...", "saved": 15157, "no_longer_in_force": 3, ...}

        Código novo é inserido, código que já existe é atualizado.
        Código que estava no banco e não veio no arquivo novo não é apagado
        (pode ter produto usando), só fica com in_force = FALSE.
        """
        import_id = str(uuid4())

        ok, error = self.insert("ncm_imports", {
            "id": import_id,
            "legal_act": table["legal_act"],
            "version_label": table["version_label"],
            "file_name": file_name,
            "total_codes": len(table["codes"]),
        })
        if not ok:
            return False, f"Erro ao registrar a importação: {error}"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        rows = []
        for ncm in table["codes"]:
            row = dict(ncm)
            row["in_force"] = True
            row["import_id"] = import_id
            row["updated_at"] = now
            rows.append(row)

        ok, saved = self.insert_or_update_many("ncm", rows, key_columns=["code"])
        if not ok:
            self.delete("ncm_imports", where={"id": import_id})
            return False, f"Erro ao gravar os NCMs: {saved}"

        ok, no_longer_in_force = self.update(
            "ncm",
            {"in_force": False},
            where={"import_id": ("!=", import_id), "in_force": True},
        )
        if not ok:
            return False, f"NCMs gravados, mas erro ao marcar os que saíram da tabela: {no_longer_in_force}"

        return True, {
            "import_id": import_id,
            "legal_act": table["legal_act"],
            "version_label": table["version_label"],
            "saved": saved,
            "no_longer_in_force": no_longer_in_force,
        }

    def get(self, code):
        """(True, linha do NCM) ou (True, None) se o código não existe."""
        if not ONLY_DIGITS.match(str(code)):
            return False, f"Código de NCM inválido: {code!r}"
        return self.select("ncm", where={"code": code}, fetch="one")

    def search(self, text, limit, offset):
        """
        Busca NCMs finais (8 dígitos) pelo começo do código ou por palavra da descrição.

            search("2203", 10, 0)     ->  NCMs que começam com 2203
            search("cerveja", 10, 0)  ->  NCMs com "cerveja" na descrição completa
        """
        code_prefix = str(text).replace(".", "").strip()
        sql = """
            SELECT code, formatted_code, description, full_description, in_force
            FROM ncm
            WHERE level = ? AND (code LIKE ? OR full_description LIKE ?)
            ORDER BY code
            LIMIT ? OFFSET ?
        """
        values = (FINAL_LEVEL, code_prefix + "%", "%" + str(text).strip() + "%", limit, offset)
        return self.run_sql(sql, values)
