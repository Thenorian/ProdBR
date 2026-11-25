from uuid import uuid4

from database.category import now_text
from database.database import Database
from database.revision import revision_command
from util.validation import clean_cnpj

COMPANY_FIELDS = (
    "name", "legal_name", "cnpj", "description", "website", "phone", "address", "city", "uf", "source",
)

# Produtos de uma empresa: os ligados direto a ela e os sem empresa cuja marca é dela
# ou cujo fabricante tem o nome dela. Os "?" são, na ordem: id, id e nome da empresa.
PRODUCTS_OF_COMPANY_CONDITION = """
    products.company_id = ?
    OR (
        products.company_id IS NULL
        AND (
            products.brand COLLATE NOCASE IN (SELECT brand FROM company_brands WHERE company_id = ?)
            OR products.manufacturer = ? COLLATE NOCASE
        )
    )
"""


def brands_as_text(brands):
    """ ["Nescau", "Ninho"] -> "Nescau, Ninho" (como fica no histórico) """
    return ", ".join(brands) if brands else None


class CompanyDB(Database):
    """
    Perfil de empresa, editado pela comunidade como um verbete da Wikipedia.
    Toda alteração entra no histórico (revisions, entity_type "company").
    """

    def __init__(self):
        super().__init__()

    def find_id(self, cnpj_or_id):
        """
        Id da empresa a partir do CNPJ (com ou sem pontuação, numérico ou alfanumérico) ou do próprio id.
        (True, None) se não existe.

            find_id("60.409.075/0001-52")  ->  (True, "f2f6cbab-...")
            find_id("f2f6cbab-...")        ->  (True, "f2f6cbab-...")
        """
        cnpj = clean_cnpj(cnpj_or_id)
        where = {"cnpj": cnpj} if cnpj else {"id": str(cnpj_or_id or "")}
        ok, row = self.select("companies", ["id"], where=where, fetch="one")
        if not ok:
            return False, row
        return True, row and row["id"]

    def get_full(self, company_id):
        """Empresa com as marcas e quantos produtos ela tem. (True, None) se não existe."""
        ok, company = self.select("companies", where={"id": company_id}, fetch="one")
        if not ok or company is None:
            return ok, company

        ok, brands = self.list_brands(company_id)
        if not ok:
            return False, brands

        ok, product_count = self.count_products(company)
        if not ok:
            return False, product_count

        return True, {**company, "brands": brands, "product_count": product_count}

    def list_brands(self, company_id):
        ok, rows = self.select("company_brands", ["brand"], where={"company_id": company_id}, order_by="brand")
        if not ok:
            return False, rows
        return True, [row["brand"] for row in rows]

    def search(self, text, uf, limit, offset):
        """
        Busca por nome, razão social, CNPJ ou marca. Todos os filtros são opcionais.
        Devolve (True, {"items": [...], "total": n}).
        """
        conditions = []
        values = []

        if text:
            conditions.append("""(
                name LIKE ? OR legal_name LIKE ? OR cnpj = ?
                OR EXISTS (SELECT 1 FROM company_brands WHERE company_id = companies.id AND brand LIKE ?)
            )""")
            values.extend([f"%{text}%", f"%{text}%", clean_cnpj(text) or text, f"%{text}%"])

        if uf:
            conditions.append("uf = ?")
            values.append(uf)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        ok, total = self.run_sql(f"SELECT COUNT(*) AS total FROM companies {where_sql}", values, fetch="one")
        if not ok:
            return False, total

        sql = f"""
            SELECT id, name, legal_name, cnpj, city, uf
            FROM companies {where_sql}
            ORDER BY name COLLATE NOCASE, id
            LIMIT ? OFFSET ?
        """
        ok, items = self.run_sql(sql, values + [limit, offset])
        if not ok:
            return False, items

        return True, {"items": items, "total": total["total"]}

    def count_products(self, company):
        sql = f"SELECT COUNT(*) AS total FROM products WHERE {PRODUCTS_OF_COMPANY_CONDITION}"
        ok, row = self.run_sql(sql, (company["id"], company["id"], company["name"]), fetch="one")
        if not ok:
            return False, row
        return True, row["total"]

    def list_product_ids(self, company_id, limit, offset):
        """Ids dos produtos da empresa, por nome. (True, None) se a empresa não existe."""
        ok, company = self.select("companies", ["id", "name"], where={"id": company_id}, fetch="one")
        if not ok or company is None:
            return ok, company

        ok, total = self.count_products(company)
        if not ok:
            return False, total

        sql = f"""
            SELECT id FROM products
            WHERE {PRODUCTS_OF_COMPANY_CONDITION}
            ORDER BY name, id
            LIMIT ? OFFSET ?
        """
        ok, rows = self.run_sql(sql, (company["id"], company["id"], company["name"], limit, offset))
        if not ok:
            return False, rows

        return True, {"ids": [row["id"] for row in rows], "total": total}

    def find_for_product(self, company_id, brand, manufacturer):
        """
        A empresa de um produto: a ligada direto a ele; se não tem, a dona da marca;
        se ninguém tem a marca, a que tem o nome do fabricante. (True, None) se nenhuma.
        Devolve só {"id", "name", "cnpj", "linked_by"}, com linked_by = "company_id", "brand" ou "manufacturer".
        """
        if company_id:
            ok, company = self.select("companies", ["id", "name", "cnpj"], where={"id": company_id}, fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "company_id"}

        if brand:
            sql = """
                SELECT companies.id, companies.name, companies.cnpj FROM company_brands
                JOIN companies ON companies.id = company_brands.company_id
                WHERE company_brands.brand = ? COLLATE NOCASE
                ORDER BY companies.created_at
            """
            ok, company = self.run_sql(sql, (brand,), fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "brand"}

        if manufacturer:
            sql = "SELECT id, name, cnpj FROM companies WHERE name = ? COLLATE NOCASE ORDER BY created_at"
            ok, company = self.run_sql(sql, (manufacturer,), fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "manufacturer"}

        return True, None

    def create(self, data, brands, contributor, reason):
        """Cria a empresa com as marcas e grava o histórico, tudo numa transação. Devolve o id."""
        ok, error = self._check_cnpj_is_free(data.get("cnpj"), company_id=None)
        if not ok:
            return False, error

        company_id = str(uuid4())
        filled_fields = [field for field in COMPANY_FIELDS if data.get(field) is not None]

        columns = ", ".join(["id", *filled_fields])
        placeholders = ", ".join(["?"] * (len(filled_fields) + 1))
        commands = [(
            f"INSERT INTO companies ({columns}) VALUES ({placeholders})",
            [company_id, *[data[field] for field in filled_fields]],
        )]
        for brand in brands:
            commands.append(("INSERT INTO company_brands (company_id, brand) VALUES (?, ?)", (company_id, brand)))

        for field in filled_fields:
            commands.append(revision_command("company", company_id, contributor, "create", reason, field, None, data[field]))
        if brands:
            commands.append(revision_command("company", company_id, contributor, "create", reason, "brands", None, brands_as_text(brands)))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error
        return True, company_id

    def update(self, company_id, changes, new_brands, contributor, reason):
        """
        Altera a empresa e grava no histórico só o que mudou.
        new_brands None não mexe nas marcas; uma lista substitui todas. Devolve os campos alterados.
        """
        ok, current = self.select("companies", where={"id": company_id}, fetch="one")
        if not ok:
            return False, current
        if current is None:
            return False, "Empresa não encontrada."

        if "cnpj" in changes:
            ok, error = self._check_cnpj_is_free(changes["cnpj"], company_id)
            if not ok:
                return False, error

        commands = []
        changed_fields = [field for field, value in changes.items() if current[field] != value]

        if changed_fields:
            set_sql = ", ".join(f"{self._quote(field)} = ?" for field in changed_fields)
            values = [changes[field] for field in changed_fields] + [now_text(), company_id]
            commands.append((f"UPDATE companies SET {set_sql}, updated_at = ? WHERE id = ?", values))
            for field in changed_fields:
                commands.append(
                    revision_command("company", company_id, contributor, "update", reason, field, current[field], changes[field])
                )

        if new_brands is not None:
            ok, current_brands = self.list_brands(company_id)
            if not ok:
                return False, current_brands

            if sorted(current_brands) != sorted(new_brands):
                commands.append(("DELETE FROM company_brands WHERE company_id = ?", (company_id,)))
                for brand in new_brands:
                    commands.append(("INSERT INTO company_brands (company_id, brand) VALUES (?, ?)", (company_id, brand)))
                commands.append(revision_command(
                    "company", company_id, contributor, "update", reason,
                    "brands", brands_as_text(current_brands), brands_as_text(new_brands),
                ))
                changed_fields.append("brands")
                if len(changed_fields) == 1:
                    commands.append(("UPDATE companies SET updated_at = ? WHERE id = ?", (now_text(), company_id)))

        if not commands:
            return True, []

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error
        return True, changed_fields

    def _check_cnpj_is_free(self, cnpj, company_id):
        """Um CNPJ pertence a uma empresa só."""
        if not cnpj:
            return True, None

        ok, owner = self.select("companies", ["id", "name"], where={"cnpj": cnpj}, fetch="one")
        if not ok:
            return False, owner
        if owner is not None and owner["id"] != company_id:
            return False, f"O CNPJ já está cadastrado na empresa {owner['name']}."
        return True, None
