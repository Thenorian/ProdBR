from uuid import uuid4

from database.category import now_text
from database.database import Database
from database.revision import revision_command
from util.validation import clean_cnpj

COMPANY_FIELDS = ("name", "description", "website", "source")

ESTABLISHMENT_FIELDS = (
    "cnpj", "legal_name", "state_registration", "is_headquarters",
    "zip_code", "street", "number", "complement", "district", "city", "city_ibge_code", "uf",
)
PHONE_FIELDS = ("phone", "description")

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

# CNPJ da matriz (ou do primeiro estabelecimento, se nenhum for matriz), usado no endereço da página.
HEADQUARTERS_CNPJ = """
    (SELECT cnpj FROM company_establishments
     WHERE company_id = companies.id AND cnpj IS NOT NULL
     ORDER BY is_headquarters DESC, position LIMIT 1)
"""


def brands_as_text(brands):
    """ ["Nescau", "Ninho"] -> "Nescau, Ninho" (como fica no histórico) """
    return ", ".join(brands) if brands else None


def establishments_as_text(establishments):
    """ Como fica no histórico: "60409075000152 Nestlé Brasil Ltda matriz São Paulo/SP; ..." """
    if not establishments:
        return None
    lines = []
    for establishment in establishments:
        place = "/".join(part for part in (establishment.get("city"), establishment.get("uf")) if part)
        headquarters = "matriz" if establishment.get("is_headquarters") else ""
        lines.append(" ".join(part for part in (
            establishment.get("cnpj"), establishment.get("legal_name"), headquarters, place,
        ) if part))
    return "; ".join(lines)


def phones_as_text(phones):
    """ [{"phone": "0800 123", "description": "SAC"}] -> "SAC: 0800 123" """
    if not phones:
        return None
    return "; ".join(f"{phone['description']}: {phone['phone']}" if phone.get("description") else phone["phone"]
                     for phone in phones)


def one_line_address(establishment):
    """ Endereço numa linha só, para o campo address antigo da API. Ex: "Av. Paulista, 1000 - Sala 2, Bela Vista" """
    street_and_number = ", ".join(part for part in (establishment["street"], establishment["number"]) if part)
    with_complement = " - ".join(part for part in (street_and_number, establishment["complement"]) if part)
    return ", ".join(part for part in (with_complement, establishment["district"]) if part) or None


class CompanyDB(Database):
    """
    Perfil de empresa, editado pela comunidade como um verbete da Wikipedia.
    Toda alteração entra no histórico (revisions, entity_type "company").

    A empresa tem listas: marcas, estabelecimentos (cada CNPJ com razão social e endereço)
    e telefones (cada um com a descrição: SAC, Suporte...). Na edição, cada lista enviada
    substitui a anterior inteira; lista não enviada (None) não muda.
    """

    def __init__(self):
        super().__init__()

    def find_id(self, cnpj_or_id):
        """
        Id da empresa a partir de qualquer CNPJ dela (com ou sem pontuação, numérico ou alfanumérico)
        ou do próprio id. (True, None) se não existe.

            find_id("60.409.075/0001-52")  ->  (True, "f2f6cbab-...")
            find_id("f2f6cbab-...")        ->  (True, "f2f6cbab-...")
        """
        cnpj = clean_cnpj(cnpj_or_id)
        if cnpj:
            ok, row = self.select("company_establishments", ["company_id"], where={"cnpj": cnpj}, fetch="one")
            if not ok:
                return False, row
            return True, row and row["company_id"]

        ok, row = self.select("companies", ["id"], where={"id": str(cnpj_or_id or "")}, fetch="one")
        if not ok:
            return False, row
        return True, row and row["id"]

    def get_full(self, company_id):
        """
        Empresa com marcas, estabelecimentos, telefones e quantos produtos ela tem. (True, None) se não existe.

        Os campos cnpj, legal_name, address, city, uf e phone são da primeira versão da API:
        vêm da matriz (ou do primeiro estabelecimento) e do primeiro telefone.
        """
        ok, company = self.select("companies", ["id", *COMPANY_FIELDS, "created_at", "updated_at"],
                                  where={"id": company_id}, fetch="one")
        if not ok or company is None:
            return ok, company

        ok, brands = self.list_brands(company_id)
        if not ok:
            return False, brands
        ok, establishments = self.list_establishments(company_id)
        if not ok:
            return False, establishments
        ok, phones = self.list_phones(company_id)
        if not ok:
            return False, phones
        ok, product_count = self.count_products(company)
        if not ok:
            return False, product_count

        headquarters = establishments[0] if establishments else None
        return True, {
            **company,
            "brands": brands,
            "establishments": establishments,
            "phones": phones,
            "product_count": product_count,
            "cnpj": headquarters["cnpj"] if headquarters else None,
            "legal_name": headquarters["legal_name"] if headquarters else None,
            "address": one_line_address(headquarters) if headquarters else None,
            "city": headquarters["city"] if headquarters else None,
            "uf": headquarters["uf"] if headquarters else None,
            "phone": phones[0]["phone"] if phones else None,
        }

    def list_brands(self, company_id):
        ok, rows = self.select("company_brands", ["brand"], where={"company_id": company_id}, order_by="brand")
        if not ok:
            return False, rows
        return True, [row["brand"] for row in rows]

    def list_establishments(self, company_id):
        """Estabelecimentos da empresa, a matriz primeiro."""
        ok, rows = self.select(
            "company_establishments", list(ESTABLISHMENT_FIELDS),
            where={"company_id": company_id}, order_by=["is_headquarters DESC", "position"],
        )
        if not ok:
            return False, rows
        return True, [{**row, "is_headquarters": bool(row["is_headquarters"])} for row in rows]

    def list_phones(self, company_id):
        ok, rows = self.select("company_phones", list(PHONE_FIELDS), where={"company_id": company_id}, order_by="position")
        if not ok:
            return False, rows
        return True, [dict(row) for row in rows]

    def search(self, text, uf, limit, offset):
        """
        Busca por nome, razão social, qualquer CNPJ ou marca. Todos os filtros são opcionais.
        uf: empresas com algum estabelecimento na UF. Devolve (True, {"items": [...], "total": n}).
        """
        conditions = []
        values = []

        if text:
            conditions.append("""(
                companies.name LIKE ?
                OR EXISTS (SELECT 1 FROM company_establishments
                           WHERE company_id = companies.id AND (legal_name LIKE ? OR cnpj = ?))
                OR EXISTS (SELECT 1 FROM company_brands WHERE company_id = companies.id AND brand LIKE ?)
            )""")
            values.extend([f"%{text}%", f"%{text}%", clean_cnpj(text) or text, f"%{text}%"])

        if uf:
            conditions.append("EXISTS (SELECT 1 FROM company_establishments WHERE company_id = companies.id AND uf = ?)")
            values.append(uf)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        ok, total = self.run_sql(f"SELECT COUNT(*) AS total FROM companies {where_sql}", values, fetch="one")
        if not ok:
            return False, total

        sql = f"""
            SELECT companies.id, companies.name,
                   headquarters.cnpj, headquarters.legal_name, headquarters.city, headquarters.uf
            FROM companies
            LEFT JOIN company_establishments AS headquarters ON headquarters.id = (
                SELECT id FROM company_establishments
                WHERE company_id = companies.id ORDER BY is_headquarters DESC, position LIMIT 1
            )
            {where_sql}
            ORDER BY companies.name COLLATE NOCASE, companies.id
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
        Devolve só {"id", "name", "cnpj" (da matriz), "linked_by"}, com linked_by = "company_id", "brand" ou "manufacturer".
        """
        columns = f"companies.id, companies.name, {HEADQUARTERS_CNPJ} AS cnpj"

        if company_id:
            ok, company = self.run_sql(f"SELECT {columns} FROM companies WHERE companies.id = ?", (company_id,), fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "company_id"}

        if brand:
            sql = f"""
                SELECT {columns} FROM company_brands
                JOIN companies ON companies.id = company_brands.company_id
                WHERE company_brands.brand = ? COLLATE NOCASE
                ORDER BY companies.created_at
            """
            ok, company = self.run_sql(sql, (brand,), fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "brand"}

        if manufacturer:
            sql = f"SELECT {columns} FROM companies WHERE companies.name = ? COLLATE NOCASE ORDER BY companies.created_at"
            ok, company = self.run_sql(sql, (manufacturer,), fetch="one")
            if not ok or company is not None:
                return ok, company and {**company, "linked_by": "manufacturer"}

        return True, None

    def create(self, data, brands, establishments, phones, contributor, reason):
        """Cria a empresa com as listas e grava o histórico, tudo numa transação. Devolve o id."""
        ok, error = self._check_cnpjs_are_free(establishments, company_id=None)
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
        commands.extend(brand_commands(company_id, brands))
        commands.extend(establishment_commands(company_id, establishments))
        commands.extend(phone_commands(company_id, phones))

        for field in filled_fields:
            commands.append(revision_command("company", company_id, contributor, "create", reason, field, None, data[field]))
        for field, text in (("brands", brands_as_text(brands)), ("establishments", establishments_as_text(establishments)),
                            ("phones", phones_as_text(phones))):
            if text:
                commands.append(revision_command("company", company_id, contributor, "create", reason, field, None, text))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error
        return True, company_id

    def update(self, company_id, changes, new_brands, new_establishments, new_phones, contributor, reason):
        """
        Altera a empresa e grava no histórico só o que mudou. Devolve os campos alterados.
        Listas None não mudam; uma lista substitui a anterior inteira.
        """
        ok, current = self.select("companies", where={"id": company_id}, fetch="one")
        if not ok:
            return False, current
        if current is None:
            return False, "Empresa não encontrada."

        if new_establishments is not None:
            ok, error = self._check_cnpjs_are_free(new_establishments, company_id)
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

        list_changes = (
            ("brands", new_brands, self.list_brands, brands_as_text, "company_brands", brand_commands),
            ("establishments", new_establishments, self._list_establishments_as_saved, establishments_as_text,
             "company_establishments", establishment_commands),
            ("phones", new_phones, self.list_phones, phones_as_text, "company_phones", phone_commands),
        )
        for field, new_list, read_current_list, as_text, table, insert_commands in list_changes:
            if new_list is None:
                continue
            ok, current_list = read_current_list(company_id)
            if not ok:
                return False, current_list
            if current_list == new_list:
                continue

            commands.append((f"DELETE FROM {table} WHERE company_id = ?", (company_id,)))
            commands.extend(insert_commands(company_id, new_list))
            commands.append(revision_command(
                "company", company_id, contributor, "update", reason, field, as_text(current_list), as_text(new_list),
            ))
            changed_fields.append(field)

        if not commands:
            return True, []
        if not any(field in COMPANY_FIELDS for field in changed_fields):
            commands.append(("UPDATE companies SET updated_at = ? WHERE id = ?", (now_text(), company_id)))

        ok, error = self.run_in_transaction(commands)
        if not ok:
            return False, error
        return True, changed_fields

    def _list_establishments_as_saved(self, company_id):
        """Estabelecimentos na ordem e no formato em que são gravados, para comparar com a lista nova."""
        ok, rows = self.select(
            "company_establishments", list(ESTABLISHMENT_FIELDS), where={"company_id": company_id}, order_by="position",
        )
        if not ok:
            return False, rows
        return True, [dict(row) for row in rows]

    def _check_cnpjs_are_free(self, establishments, company_id):
        """Um CNPJ pertence a um estabelecimento só, de uma empresa só."""
        cnpjs = [establishment["cnpj"] for establishment in establishments or [] if establishment.get("cnpj")]
        if len(cnpjs) != len(set(cnpjs)):
            return False, "O mesmo CNPJ apareceu duas vezes na lista."

        for cnpj in cnpjs:
            sql = """
                SELECT companies.id, companies.name FROM company_establishments
                JOIN companies ON companies.id = company_establishments.company_id
                WHERE company_establishments.cnpj = ?
            """
            ok, owner = self.run_sql(sql, (cnpj,), fetch="one")
            if not ok:
                return False, owner
            if owner is not None and owner["id"] != company_id:
                return False, f"O CNPJ {cnpj} já está cadastrado na empresa {owner['name']}."
        return True, None


def brand_commands(company_id, brands):
    return [("INSERT INTO company_brands (company_id, brand) VALUES (?, ?)", (company_id, brand)) for brand in brands or []]


def establishment_commands(company_id, establishments):
    columns = ", ".join(ESTABLISHMENT_FIELDS)
    placeholders = ", ".join(["?"] * len(ESTABLISHMENT_FIELDS))
    return [
        (
            f"INSERT INTO company_establishments (id, company_id, position, {columns}) VALUES (?, ?, ?, {placeholders})",
            (str(uuid4()), company_id, position, *[establishment[field] for field in ESTABLISHMENT_FIELDS]),
        )
        for position, establishment in enumerate(establishments or [])
    ]


def phone_commands(company_id, phones):
    return [
        (
            "INSERT INTO company_phones (id, company_id, position, phone, description) VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), company_id, position, phone["phone"], phone["description"]),
        )
        for position, phone in enumerate(phones or [])
    ]


def move_old_company_data_to_lists():
    """
    A primeira versão das empresas guardava CNPJ, razão social, endereço, cidade, UF e telefone
    direto na tabela companies. Agora isso fica em company_establishments e company_phones.
    Roda a cada início do app: copia o que ainda estiver nas colunas antigas e esvazia elas,
    então da segunda vez em diante não acha mais nada. Num banco novo as colunas nem existem.
    """
    companies = CompanyDB()
    ok, has_old_columns = companies.column_exists("companies", "cnpj")
    if not ok:
        return False, has_old_columns
    if not has_old_columns:
        return True, 0

    sql = """
        SELECT id, cnpj, legal_name, address, city, uf, phone FROM companies
        WHERE cnpj IS NOT NULL OR legal_name IS NOT NULL OR address IS NOT NULL
           OR city IS NOT NULL OR uf IS NOT NULL OR phone IS NOT NULL
    """
    ok, rows = companies.run_sql(sql)
    if not ok:
        return False, rows

    for row in rows:
        commands = []
        if any(row[field] for field in ("cnpj", "legal_name", "address", "city", "uf")):
            commands.append((
                "INSERT INTO company_establishments (id, company_id, cnpj, legal_name, is_headquarters, street, city, uf) "
                "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                (str(uuid4()), row["id"], row["cnpj"], row["legal_name"], row["address"], row["city"], row["uf"]),
            ))
        if row["phone"]:
            commands.append((
                "INSERT INTO company_phones (id, company_id, phone) VALUES (?, ?, ?)",
                (str(uuid4()), row["id"], row["phone"]),
            ))
        commands.append((
            "UPDATE companies SET cnpj = NULL, legal_name = NULL, address = NULL, city = NULL, uf = NULL, phone = NULL "
            "WHERE id = ?",
            (row["id"],),
        ))
        ok, error = companies.run_in_transaction(commands)
        if not ok:
            return False, error

    return True, len(rows)
