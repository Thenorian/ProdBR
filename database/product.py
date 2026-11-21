import statistics
from uuid import uuid4

from database.category import CategoryDB, now_text
from database.database import Database
from database.fiscal import FiscalDB, summarize_fiscal_rules
from database.revision import revision_command

PRODUCT_FIELDS = (
    "name", "brand", "manufacturer", "manufacturer_code", "description",
    "category_id", "ncm_code", "cest", "origin", "commercial_unit", "source",
)

BARCODE_FIELDS = ("barcode", "package_description", "net_quantity", "net_unit", "units_per_pack")

PRICE_PERIOD_IN_MONTHS = 12


class ProductDB(Database):
    """
    O produto é o centro do ProdBR. get_full junta tudo que um ERP precisa
    para preencher um cadastro numa resposta só: códigos de barras, NCM,
    categoria, preço médio e regras fiscais.
    """

    def __init__(self):
        super().__init__()
        self.categories = CategoryDB()
        self.fiscal = FiscalDB()

    def get_full(self, product_id, uf=None, tax_regime=None):
        """
        Produto completo, ou (True, None) se não existe.

        NCM, CEST e origem: vale o do produto; o que estiver vazio vem da categoria
        (ou da categoria acima). A lista "fiscal_data_from_category" diz o que veio de lá.
        As regras fiscais são as do NCM que estiver valendo, filtradas por uf e regime se informados.
        "fiscal_summary" junta as regras campo a campo (ICMS da UF + IPI/II oficiais): é o que o ERP usa.
        """
        ok, product = self.select("products", where={"id": product_id}, fetch="one")
        if not ok or product is None:
            return ok, product

        ok, barcodes = self.list_barcodes(product_id)
        if not ok:
            return False, barcodes

        ok, category = self._category_summary(product["category_id"])
        if not ok:
            return False, category

        fiscal_data_from_category = []
        for field in ("ncm_code", "cest", "origin"):
            if product[field] is None and category and category["inherited"][field] is not None:
                product[field] = category["inherited"][field]
                fiscal_data_from_category.append(field)

        ok, ncm = self._ncm_summary(product["ncm_code"])
        if not ok:
            return False, ncm

        ok, price = self._price_summary(product_id)
        if not ok:
            return False, price

        fiscal_rules = []
        if product["ncm_code"]:
            ok, fiscal_rules = self.fiscal.list_applicable(product["ncm_code"], uf, tax_regime, product["cest"])
            if not ok:
                return False, fiscal_rules

        return True, {
            "id": product["id"],
            "name": product["name"],
            "brand": product["brand"],
            "manufacturer": product["manufacturer"],
            "manufacturer_code": product["manufacturer_code"],
            "description": product["description"],
            "barcodes": barcodes,
            "category": category and {"id": category["id"], "path": category["path"]},
            "commercial_unit": product["commercial_unit"],
            "ncm": ncm,
            "cest": product["cest"],
            "origin": product["origin"],
            "fiscal_data_from_category": fiscal_data_from_category,
            "price": price,
            "fiscal_summary": summarize_fiscal_rules(fiscal_rules, uf, tax_regime),
            "fiscal_rules": fiscal_rules,
            "source": product["source"],
            "created_at": product["created_at"],
            "updated_at": product["updated_at"],
        }

    def list_barcodes(self, product_id):
        """Códigos de barras do produto, cada um com a embalagem dele."""
        return self.select("product_barcodes", list(BARCODE_FIELDS), where={"product_id": product_id}, order_by="barcode")

    def find_id_by_barcode(self, barcode):
        ok, row = self.select("product_barcodes", ["product_id"], where={"barcode": barcode}, fetch="one")
        if not ok:
            return False, row
        return True, row and row["product_id"]

    def search(self, filters, limit, offset, order="name"):
        """
        Busca produtos. Todos os filtros são opcionais e se somam (AND).

            filters = {
                "barcode": "7891000100103",      código de barras exato
                "ncm_code": "22030000",          NCM do produto ou herdado da categoria
                "manufacturer_code": "BPR6ES",   código interno do fabricante, exato
                "manufacturer": "Tramontina",    parte do nome do fabricante
                "category_id": "...",            a categoria e as que estão abaixo dela
                "text": "café",                  nome, marca, fabricante, descrição ou qualquer código
            }
            order: "name" (A a Z) ou "recent" (alterados por último primeiro)

        Devolve (True, {"ids": [...], "total": n}). Para o produto completo, use get_full em cada id.
        """
        conditions = []
        values = []

        if filters.get("barcode"):
            conditions.append("EXISTS (SELECT 1 FROM product_barcodes WHERE product_id = products.id AND barcode = ?)")
            values.append(filters["barcode"])

        if filters.get("ncm_code"):
            ok, category_ids = self._category_ids_with_inherited_ncm(filters["ncm_code"])
            if not ok:
                return False, category_ids
            placeholders = ", ".join(["?"] * len(category_ids)) or "NULL"
            conditions.append(f"(ncm_code = ? OR (ncm_code IS NULL AND category_id IN ({placeholders})))")
            values.extend([filters["ncm_code"], *category_ids])

        if filters.get("manufacturer_code"):
            conditions.append("manufacturer_code = ?")
            values.append(filters["manufacturer_code"])

        if filters.get("manufacturer"):
            conditions.append("manufacturer LIKE ?")
            values.append(f"%{filters['manufacturer']}%")

        if filters.get("category_id"):
            ok, category_ids = self._category_and_children_ids(filters["category_id"])
            if not ok:
                return False, category_ids
            conditions.append(f"category_id IN ({', '.join(['?'] * len(category_ids))})")
            values.extend(category_ids)

        if filters.get("text"):
            text = filters["text"]
            conditions.append("""(
                name LIKE ? OR brand LIKE ? OR manufacturer LIKE ? OR description LIKE ?
                OR manufacturer_code = ? OR ncm_code = ?
                OR EXISTS (SELECT 1 FROM product_barcodes WHERE product_id = products.id AND barcode = ?)
            )""")
            values.extend([f"%{text}%"] * 4 + [text] * 3)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        order_sql = "updated_at DESC, id" if order == "recent" else "name, id"

        ok, total = self.run_sql(f"SELECT COUNT(*) AS total FROM products {where_sql}", values, fetch="one")
        if not ok:
            return False, total

        sql = f"SELECT id FROM products {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?"
        ok, rows = self.run_sql(sql, values + [limit, offset])
        if not ok:
            return False, rows

        return True, {"ids": [row["id"] for row in rows], "total": total["total"]}

    def list_changed_since(self, since, limit, offset):
        """
        Produtos alterados a partir de uma data, do mais antigo para o mais novo.
        Serve para um ERP sincronizar só o que mudou, e para o sitemap do site.
        """
        sql = """
            SELECT id, updated_at FROM products
            WHERE updated_at >= ?
            ORDER BY updated_at, id
            LIMIT ? OFFSET ?
        """
        return self.run_sql(sql, (since, limit, offset))

    def create(self, data, barcodes, contributor, reason):
        """
        Cria o produto com os códigos de barras e grava o histórico, tudo numa transação.
        data tem as colunas de PRODUCT_FIELDS (já validadas pela API).
        barcodes é uma lista de dicionários com as colunas de BARCODE_FIELDS.
        """
        ok, error = self._check_barcodes_are_free(barcodes, product_id=None)
        if not ok:
            return False, error

        product_id = str(uuid4())
        filled_fields = [field for field in PRODUCT_FIELDS if data.get(field) is not None]

        columns = ", ".join(["id", *filled_fields])
        placeholders = ", ".join(["?"] * (len(filled_fields) + 1))
        commands = [(
            f"INSERT INTO products ({columns}) VALUES ({placeholders})",
            [product_id, *[data[field] for field in filled_fields]],
        )]

        commands.extend(insert_barcode_commands(product_id, barcodes))

        for field in filled_fields:
            commands.append(revision_command("product", product_id, contributor, "create", reason, field, None, data[field]))
        if barcodes:
            commands.append(
                revision_command("product", product_id, contributor, "create", reason, "barcodes", None, barcodes_as_text(barcodes))
            )

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, product_id

    def update(self, product_id, changes, new_barcodes, contributor, reason):
        """
        Altera o produto e grava no histórico só o que mudou.
        new_barcodes None não mexe nos códigos; uma lista substitui todos.
        Devolve a lista de campos alterados.
        """
        ok, current = self.select("products", where={"id": product_id}, fetch="one")
        if not ok:
            return False, current
        if current is None:
            return False, "Produto não encontrado."

        commands = []
        changed_fields = [field for field, value in changes.items() if current[field] != value]

        if changed_fields:
            set_sql = ", ".join(f"{self._quote(field)} = ?" for field in changed_fields)
            values = [changes[field] for field in changed_fields] + [now_text(), product_id]
            commands.append((f"UPDATE products SET {set_sql}, updated_at = ? WHERE id = ?", values))

            for field in changed_fields:
                commands.append(
                    revision_command("product", product_id, contributor, "update", reason, field, current[field], changes[field])
                )

        if new_barcodes is not None:
            ok, barcode_commands = self._barcode_change_commands(product_id, new_barcodes, contributor, reason)
            if not ok:
                return False, barcode_commands
            if barcode_commands:
                commands.extend(barcode_commands)
                changed_fields.append("barcodes")
                if len(changed_fields) == 1:
                    commands.append(("UPDATE products SET updated_at = ? WHERE id = ?", (now_text(), product_id)))

        if not commands:
            return True, []

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, changed_fields

    def add_price_report(self, product_id, price_cents, uf, contributor):
        return self.insert("price_reports", {
            "id": str(uuid4()),
            "product_id": product_id,
            "price_cents": price_cents,
            "uf": uf,
            "contributor": contributor,
        })

    def _barcode_change_commands(self, product_id, new_barcodes, contributor, reason):
        """Se a lista mudou (código ou embalagem), troca todos os códigos do produto pela lista nova."""
        ok, current_barcodes = self.list_barcodes(product_id)
        if not ok:
            return False, current_barcodes

        new_barcodes = sorted(new_barcodes, key=lambda item: item["barcode"])
        if [dict(row) for row in current_barcodes] == [complete_barcode(item) for item in new_barcodes]:
            return True, []

        ok, error = self._check_barcodes_are_free(new_barcodes, product_id)
        if not ok:
            return False, error

        commands = [("DELETE FROM product_barcodes WHERE product_id = ?", (product_id,))]
        commands.extend(insert_barcode_commands(product_id, new_barcodes))
        commands.append(revision_command(
            "product", product_id, contributor, "update", reason,
            "barcodes", barcodes_as_text(current_barcodes), barcodes_as_text(new_barcodes),
        ))
        return True, commands

    def _check_barcodes_are_free(self, barcodes, product_id):
        """Um código de barras pertence a um produto só."""
        if not barcodes:
            return True, None

        codes = [item["barcode"] for item in barcodes]
        ok, rows = self.select("product_barcodes", ["barcode", "product_id"], where={"barcode": codes})
        if not ok:
            return False, rows

        for row in rows:
            if row["product_id"] != product_id:
                return False, f"O código de barras {row['barcode']} já pertence a outro produto ({row['product_id']})."

        return True, None

    def _category_summary(self, category_id):
        if not category_id:
            return True, None

        ok, category = self.categories.get(category_id)
        if not ok:
            return False, category
        return True, category

    def _ncm_summary(self, ncm_code):
        """Dados do NCM na tabela oficial. Se o código não estiver lá, avisa com in_official_table = False."""
        if not ncm_code:
            return True, None

        ok, ncm = self.select(
            "ncm", ["code", "description", "full_description", "in_force"],
            where={"code": ncm_code}, fetch="one",
        )
        if not ok:
            return False, ncm

        if ncm is None:
            return True, {
                "code": ncm_code,
                "description": None,
                "full_description": None,
                "in_official_table": False,
            }

        return True, {
            "code": ncm["code"],
            "description": ncm["description"],
            "full_description": ncm["full_description"],
            "in_official_table": bool(ncm["in_force"]),
        }

    def _price_summary(self, product_id):
        """Média e mediana dos preços informados nos últimos 12 meses. A mediana não se deixa levar por um preço absurdo."""
        sql = f"""
            SELECT price_cents FROM price_reports
            WHERE product_id = ? AND reported_at >= datetime('now', '-{PRICE_PERIOD_IN_MONTHS} months')
        """
        ok, rows = self.run_sql(sql, (product_id,))
        if not ok:
            return False, rows
        if not rows:
            return True, None

        prices = [row["price_cents"] for row in rows]
        return True, {
            "average": round(statistics.mean(prices) / 100, 2),
            "median": round(statistics.median(prices) / 100, 2),
            "reports": len(prices),
            "period_in_months": PRICE_PERIOD_IN_MONTHS,
        }

    def _category_ids_with_inherited_ncm(self, ncm_code):
        """Categorias cujo NCM (próprio ou herdado de cima) é o pedido."""
        ok, categories = self.categories.list_all()
        if not ok:
            return False, categories

        category_by_id = {category["id"]: category for category in categories}
        matching_ids = []

        for category in categories:
            current = category
            for _ in range(20):
                if current is None or current["ncm_code"]:
                    break
                current = category_by_id.get(current["parent_id"])
            if current and current["ncm_code"] == ncm_code:
                matching_ids.append(category["id"])

        return True, matching_ids

    def _category_and_children_ids(self, category_id):
        """A categoria e todas as que estão abaixo dela, em qualquer nível."""
        ok, categories = self.categories.list_all()
        if not ok:
            return False, categories

        found_ids = [category_id]
        for found_id in found_ids:
            found_ids.extend(
                category["id"] for category in categories
                if category["parent_id"] == found_id and category["id"] not in found_ids
            )
            if len(found_ids) > len(categories) + 1:
                break

        return True, found_ids


def complete_barcode(item):
    """O código de barras com todas as colunas, as que não vieram como vazias."""
    return {field: item.get(field) for field in BARCODE_FIELDS}


def insert_barcode_commands(product_id, barcodes):
    commands = []
    for item in barcodes:
        barcode = complete_barcode(item)
        commands.append((
            """INSERT INTO product_barcodes
                   (barcode, product_id, package_description, net_quantity, net_unit, units_per_pack)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (barcode["barcode"], product_id, barcode["package_description"], barcode["net_quantity"],
             barcode["net_unit"], barcode["units_per_pack"]),
        ))
    return commands


def barcodes_as_text(barcodes):
    """Para o histórico: "7891000100103 (6x350ml), 7891000053508"."""
    parts = []
    for item in sorted(barcodes, key=lambda item: item["barcode"]):
        package = item.get("package_description")
        parts.append(f"{item['barcode']} ({package})" if package else item["barcode"])
    return ", ".join(parts)
