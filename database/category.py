from datetime import datetime, timezone
from uuid import uuid4

from database.database import Database
from database.revision import revision_command

PATH_SEPARATOR = " > "

# Dados fiscais que a categoria passa para os produtos dela (igual ao Simple ERP).
FISCAL_FIELDS = ("ncm_code", "cest", "origin")

# Limite de níveis da árvore, para um erro de cadastro (categoria pai dela mesma) nunca travar a subida.
MAX_DEPTH = 20


class CategoryDB(Database):
    """
    Categorias em árvore. Na API e no site a categoria aparece como texto,
    com ">" entre os níveis ("Bebidas > Cervejas"); no banco cada nível é uma linha.
    """

    def __init__(self):
        super().__init__()

    def get(self, category_id):
        """
        Categoria com o caminho completo e os dados fiscais que ela passa para os produtos.

            ok, category = CategoryDB().get(category_id)
            category  ->  {"id", "name", "path", "parent_id", "ncm_code", "cest", "origin",
                           "inherited": {"ncm_code": ..., "cest": ..., "origin": ...}}
        """
        ok, category = self.select("categories", where={"id": category_id}, fetch="one")
        if not ok or category is None:
            return ok, category

        ok, path = self.path_of(category_id)
        if not ok:
            return False, path

        ok, inherited = self.inherited_fiscal_data(category_id)
        if not ok:
            return False, inherited

        category["path"] = path
        category["inherited"] = inherited
        return True, category

    def list_all(self):
        """Todas as categorias com o caminho completo, em ordem alfabética do caminho."""
        ok, categories = self.select("categories", ["id", "name", "parent_id", "ncm_code", "cest", "origin"])
        if not ok:
            return False, categories

        category_by_id = {category["id"]: category for category in categories}
        for category in categories:
            category["path"] = self._build_path(category["id"], category_by_id)

        categories.sort(key=lambda category: category["path"].lower())
        return True, categories

    def find_or_create_path(self, names, contributor=None, reason=None):
        """
        Devolve o id do último nível, criando os níveis que ainda não existem.

            find_or_create_path(["Bebidas", "Cervejas"])  ->  (True, "id da categoria Cervejas")
        """
        parent_id = None

        for name in names:
            ok, category = self.select(
                "categories", ["id"], where={"name": name, "parent_id": parent_id}, fetch="one"
            )
            if not ok:
                return False, category

            if category:
                parent_id = category["id"]
                continue

            new_id = str(uuid4())
            ok, error = self.run_in_transaction([
                ("INSERT INTO categories (id, name, parent_id) VALUES (?, ?, ?)", (new_id, name, parent_id)),
                revision_command("category", new_id, contributor, "create", reason or "Categoria criada", "name", None, name),
            ])
            if not ok:
                return False, error
            parent_id = new_id

        return True, parent_id

    def update(self, category_id, changes, contributor, reason):
        """
        Altera nome e dados fiscais da categoria e grava no histórico só o que mudou.

            CategoryDB().update(category_id, {"ncm_code": "22030000"}, "kainan", "NCM das cervejas")
            ->  (True, ["ncm_code"])
        """
        ok, current = self.select("categories", where={"id": category_id}, fetch="one")
        if not ok:
            return False, current
        if current is None:
            return False, "Categoria não encontrada."

        changed_fields = [field for field, value in changes.items() if current[field] != value]
        if not changed_fields:
            return True, []

        set_sql = ", ".join(f"{self._quote(field)} = ?" for field in changed_fields)
        values = [changes[field] for field in changed_fields] + [now_text(), category_id]
        commands = [(f"UPDATE categories SET {set_sql}, updated_at = ? WHERE id = ?", values)]

        for field in changed_fields:
            commands.append(
                revision_command("category", category_id, contributor, "update", reason, field, current[field], changes[field])
            )

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, changed_fields

    def inherited_fiscal_data(self, category_id):
        """
        NCM, CEST e origem que valem para os produtos da categoria.
        Cada campo vazio é procurado na categoria acima, até a raiz.

            Bebidas (ncm 22030000)  >  Cervejas (sem nada)
            inherited_fiscal_data(id de Cervejas)
            ->  (True, {"ncm_code": "22030000", "cest": None, "origin": None,
                        "ncm_from_category": "Bebidas"})
        """
        inherited = {field: None for field in FISCAL_FIELDS}
        inherited["ncm_from_category"] = None

        current_id = category_id
        visited_ids = set()

        while current_id and current_id not in visited_ids and len(visited_ids) < MAX_DEPTH:
            visited_ids.add(current_id)

            ok, category = self.select(
                "categories", ["name", "parent_id", *FISCAL_FIELDS], where={"id": current_id}, fetch="one"
            )
            if not ok:
                return False, category
            if category is None:
                break

            for field in FISCAL_FIELDS:
                if inherited[field] is None and category[field] is not None:
                    inherited[field] = category[field]
                    if field == "ncm_code":
                        inherited["ncm_from_category"] = category["name"]

            current_id = category["parent_id"]

        return True, inherited

    def path_of(self, category_id):
        """
        Texto completo da categoria, do nível mais alto até ela.

            path_of("id da categoria Cervejas")  ->  (True, "Bebidas > Cervejas")
        """
        names = []
        current_id = category_id

        while current_id and len(names) < MAX_DEPTH:
            ok, category = self.select("categories", ["name", "parent_id"], where={"id": current_id}, fetch="one")
            if not ok:
                return False, category
            if category is None:
                break
            names.insert(0, category["name"])
            current_id = category["parent_id"]

        return True, PATH_SEPARATOR.join(names) or None

    def _build_path(self, category_id, category_by_id):
        """Mesmo que path_of, mas com as categorias já carregadas na memória (para listar todas de uma vez)."""
        names = []
        current = category_by_id.get(category_id)

        while current and len(names) < MAX_DEPTH:
            names.insert(0, current["name"])
            current = category_by_id.get(current["parent_id"])

        return PATH_SEPARATOR.join(names)


def now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
