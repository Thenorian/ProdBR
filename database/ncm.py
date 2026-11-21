import re
from uuid import uuid4

from database.database import Database

FINAL_LEVEL = "subitem"
ONLY_DIGITS = re.compile(r"^[0-9]{2,8}$")

# Limite da subida pela árvore de categorias, para um ciclo (A pai de B, B pai de A)
# nunca virar um laço infinito.
MAX_CATEGORY_DEPTH = 20


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

        rows = []
        for ncm in table["codes"]:
            row = dict(ncm)
            row["in_force"] = True
            row["import_id"] = import_id
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

    def list_final_codes_under(self, code):
        """
        Lista os NCMs finais (8 dígitos, em vigor) que ficam dentro de um código.

            list_final_codes_under("2203")      ->  todos os NCMs de cerveja de malte
            list_final_codes_under("22030000")  ->  só ele mesmo
        """
        if not ONLY_DIGITS.match(str(code)):
            return False, f"Código de NCM inválido: {code!r}"

        return self.select(
            "ncm",
            ["code", "formatted_code", "description", "full_description"],
            where={"code": ("LIKE", code + "%"), "level": FINAL_LEVEL, "in_force": True},
            order_by="code",
        )

    def suggest_for_category(self, category_id):
        """
        Descobre o NCM de um produto a partir da categoria dele.

            ok, suggestion = NcmDB().suggest_for_category(category_id)
            suggestion  ->  {
                "ncm": "22030000",          # preenchido só quando há exatamente um NCM possível
                "candidates": [...],        # todos os NCMs finais possíveis para a categoria
                "linked_code": "2203",      # NCM ligado à categoria (pode ser um grupo)
                "linked_category_id": "...",# categoria onde a ligação foi achada (ela ou uma acima)
            }

        Se a categoria não tiver NCM ligado, sobe para a categoria pai até achar.
        Não altera nenhum produto: quem chama decide se aplica o "ncm".
        """
        no_suggestion = {"ncm": None, "candidates": [], "linked_code": None, "linked_category_id": None}

        ok, category = self._find_category_linked_to_ncm(category_id)
        if not ok:
            return False, category
        if category is None:
            return True, no_suggestion

        ok, candidates = self.list_final_codes_under(category["ncm_code"])
        if not ok:
            return False, candidates

        only_one_possible_ncm = len(candidates) == 1

        return True, {
            "ncm": candidates[0]["code"] if only_one_possible_ncm else None,
            "candidates": candidates,
            "linked_code": category["ncm_code"],
            "linked_category_id": category["id"],
        }

    def _find_category_linked_to_ncm(self, category_id):
        """Sobe da categoria para as categorias pai até achar uma com ncm_code."""
        visited_ids = set()
        current_id = category_id

        while current_id and current_id not in visited_ids and len(visited_ids) < MAX_CATEGORY_DEPTH:
            visited_ids.add(current_id)

            ok, category = self.select(
                "categories", ["id", "parent_id", "ncm_code"], where={"id": current_id}, fetch="one"
            )
            if not ok:
                return False, category
            if category is None:
                return True, None
            if category["ncm_code"]:
                return True, category

            current_id = category["parent_id"]

        return True, None
