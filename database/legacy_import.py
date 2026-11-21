"""
Copia os dados da versão antiga do ProdBR (SQLAlchemy) para o banco novo.

Roda sozinha toda vez que o app inicia, mas só faz alguma coisa uma vez:
quando o banco novo ainda não tem produto (ou contribuidor) e o arquivo antigo existe.
Os arquivos antigos não são alterados nem apagados.

O que vem da versão antiga:
    produtos (com o mesmo id, para os links antigos continuarem valendo)
    códigos de barras e código do fabricante (antes ficavam em product_identifiers)
    categorias, regras fiscais do Brasil e todo o histórico de alterações
    usuários (só nome, reputação e chaves de API, que continuam funcionando)

O que não vem: e-mail e senha (o acesso agora é por token, como no Git),
sessões de login, fila de moderação e a tabela de NCM cadastrada à mão
(substituída pela tabela oficial do Siscomex).
"""
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from database.category import CategoryDB
from database.database import CommunityDatabase, Database
from database.product import insert_barcode_commands
from database.revision import revision_command
from util.validation import clean_barcode, clean_category_path, clean_cest, clean_ncm, clean_uf

DEFAULT_LEGACY_PUBLIC_PATH = "data/public.sqlite3"
DEFAULT_LEGACY_COMMUNITY_PATH = "data/community.sqlite3"

SKIPPED_IDENTIFIER_REASON = (
    "Retirado na migração para a versão nova: código de barras com dígito verificador inválido ou repetido"
)

BARCODE_IDENTIFIER_TYPES = ("gtin8", "gtin12", "gtin13", "gtin14", "upc", "ean", "other")

FISCAL_RATE_COLUMNS = (
    "icms_rate", "ipi_rate", "pis_rate", "cofins_rate", "cbs_rate",
    "ibs_rate", "ii_rate", "fcp_rate", "icms_st_mva_rate",
)


class LegacyImport:

    def __init__(self):
        self.legacy_public_path = Path(os.getenv("LEGACY_PUBLIC_DB_PATH") or DEFAULT_LEGACY_PUBLIC_PATH)
        self.legacy_community_path = Path(os.getenv("LEGACY_COMMUNITY_DB_PATH") or DEFAULT_LEGACY_COMMUNITY_PATH)
        self.public_db = Database()
        self.community_db = CommunityDatabase()
        self.categories = CategoryDB()

    def run_if_needed(self):
        """Devolve (True, lista do que foi copiado) ou (False, erro)."""
        messages = []

        ok, result = self._import_public_data_if_needed()
        if not ok:
            return False, f"Dados públicos: {result}"
        messages.extend(result)

        ok, result = self._import_contributors_if_needed()
        if not ok:
            return False, f"Contribuidores: {result}"
        messages.extend(result)

        return True, messages

    def _import_public_data_if_needed(self):
        ok, product_count = self.public_db.count("products")
        if not ok:
            return False, product_count
        if product_count > 0 or not self._legacy_table_has_rows(self.legacy_public_path, "products"):
            return True, []

        legacy = self._open_read_only(self.legacy_public_path)
        try:
            ok, category_id_by_old_id = self._import_categories(legacy)
            if not ok:
                return False, category_id_by_old_id

            commands = []
            product_messages = self._product_commands(legacy, category_id_by_old_id, commands)
            fiscal_messages = self._fiscal_rule_commands(legacy, commands)
            revision_messages = self._revision_commands(legacy, commands)
        finally:
            legacy.close()

        ok, error = self.public_db.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, [*product_messages, *fiscal_messages, *revision_messages]

    def _import_categories(self, legacy):
        """Na versão antiga a categoria era um texto só ("Pet > Ração Cães"). Aqui vira a árvore."""
        category_id_by_old_id = {}

        if not self._table_exists(legacy, "categories"):
            return True, category_id_by_old_id

        for old_category in legacy.execute("SELECT id, name FROM categories"):
            names = clean_category_path(old_category["name"])
            if not names:
                continue

            ok, new_id = self.categories.find_or_create_path(names, "importacao", "Importado da versão antiga do ProdBR")
            if not ok:
                return False, new_id
            category_id_by_old_id[old_category["id"]] = new_id

        return True, category_id_by_old_id

    def _product_commands(self, legacy, category_id_by_old_id, commands):
        identifiers_by_product = {}
        if self._table_exists(legacy, "product_identifiers"):
            for identifier in legacy.execute("SELECT * FROM product_identifiers ORDER BY id"):
                identifiers_by_product.setdefault(identifier["product_id"], []).append(identifier)

        used_barcodes = set()
        skipped_identifiers = []
        product_count = 0

        for product in legacy.execute("SELECT * FROM products"):
            manufacturer_code = None
            barcodes = []

            for identifier in identifiers_by_product.get(product["id"], []):
                if identifier["type"] == "manufacturer_code" and manufacturer_code is None:
                    manufacturer_code = identifier["value"][:60]
                    continue

                barcode = clean_barcode(identifier["value"])
                if identifier["type"] in BARCODE_IDENTIFIER_TYPES and barcode and barcode not in used_barcodes:
                    barcodes.append(legacy_barcode_with_package(barcode, identifier))
                    used_barcodes.add(barcode)
                else:
                    skipped_identifiers.append(f"{product['id']}: {identifier['type']} {identifier['value']}")
                    # Não entra como código de barras (nota com GTIN inválido é rejeitada pela SEFAZ),
                    # mas fica registrado no histórico do produto para ninguém perder a informação.
                    commands.append(revision_command(
                        "product", product["id"], "importacao", "delete", SKIPPED_IDENTIFIER_REASON,
                        "barcodes", identifier["value"], None,
                    ))

            commands.append((
                """INSERT INTO products (id, name, brand, manufacturer, manufacturer_code, description,
                       category_id, ncm_code, cest, commercial_unit, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    product["id"], product["name"], product["brand"], product["manufacturer"], manufacturer_code,
                    product["description"], category_id_by_old_id.get(product["category_id"]),
                    clean_ncm(product["ncm"]), clean_cest(product["cest"]), product["commercial_unit"] or "UN",
                    product["source"], product["created_at"], product["updated_at"],
                ),
            ))
            commands.extend(insert_barcode_commands(product["id"], barcodes))
            product_count += 1

        messages = [f"importação antiga: {product_count} produtos, {len(used_barcodes)} códigos de barras"]
        for skipped in skipped_identifiers:
            messages.append(f"importação antiga: identificador não aproveitado (código inválido ou repetido) {skipped}")
        return messages

    def _fiscal_rule_commands(self, legacy, commands):
        if not self._table_exists(legacy, "fiscal_rules"):
            return []

        rule_count = 0
        for rule in legacy.execute("SELECT * FROM fiscal_rules WHERE country = 'BR' OR country IS NULL"):
            ncm_code = clean_ncm(rule["ncm"])
            if not ncm_code:
                continue

            rates = [rule[column] for column in FISCAL_RATE_COLUMNS]
            commands.append((
                f"""INSERT INTO fiscal_rules (id, ncm_code, cest, uf, {", ".join(FISCAL_RATE_COLUMNS)},
                        notes, valid_from, valid_until, source, created_at)
                    VALUES (?, ?, ?, ?, {", ".join(["?"] * len(FISCAL_RATE_COLUMNS))}, ?, ?, ?, ?, ?)""",
                (
                    str(rule["id"]), ncm_code, clean_cest(rule["cest"]), clean_uf(rule["uf"]), *rates,
                    rule["notes"], rule["valid_from"], rule["valid_until"], rule["source"], rule["created_at"],
                ),
            ))
            rule_count += 1

        return [f"importação antiga: {rule_count} regras fiscais"]

    def _revision_commands(self, legacy, commands):
        if not self._table_exists(legacy, "revisions"):
            return []

        revision_count = 0
        for revision in legacy.execute("SELECT * FROM revisions ORDER BY id"):
            commands.append((
                """INSERT INTO revisions (entity_type, entity_id, contributor, action, field,
                       old_value, new_value, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision["entity_type"], str(revision["entity_id"]), revision["contributor"], revision["action"],
                    revision["field"], revision["old_value"], revision["new_value"], revision["reason"],
                    revision["created_at"],
                ),
            ))
            revision_count += 1

        return [f"importação antiga: {revision_count} registros de histórico"]

    def _import_contributors_if_needed(self):
        ok, contributor_count = self.community_db.count("contributors")
        if not ok:
            return False, contributor_count
        if contributor_count > 0 or not self._legacy_table_has_rows(self.legacy_community_path, "users"):
            return True, []

        legacy = self._open_read_only(self.legacy_community_path)
        try:
            commands = []
            contributor_id_by_old_id = {}

            for user in legacy.execute("SELECT id, username, reputation, edit_count, created_at FROM users"):
                contributor_id = str(uuid4())
                contributor_id_by_old_id[user["id"]] = contributor_id
                commands.append((
                    "INSERT INTO contributors (id, username, reputation, edit_count, created_at) VALUES (?, ?, ?, ?, ?)",
                    (contributor_id, user["username"], user["reputation"] or 0, user["edit_count"] or 0, user["created_at"]),
                ))

            token_count = 0
            if self._table_exists(legacy, "api_keys"):
                for api_key in legacy.execute("SELECT user_id, key_hash, created_at FROM api_keys WHERE is_active = 1"):
                    contributor_id = contributor_id_by_old_id.get(api_key["user_id"])
                    if contributor_id:
                        # A versão antiga já guardava o SHA-256 da chave, igual ao token novo.
                        commands.append((
                            "INSERT INTO contributor_tokens (token_hash, contributor_id, created_at) VALUES (?, ?, ?)",
                            (api_key["key_hash"], contributor_id, api_key["created_at"]),
                        ))
                        token_count += 1
        finally:
            legacy.close()

        ok, error = self.community_db.run_in_transaction(commands)
        if not ok:
            return False, error

        return True, [f"importação antiga: {len(contributor_id_by_old_id)} contribuidores, {token_count} chaves de API"]

    def _legacy_table_has_rows(self, path, table):
        if not path.is_file():
            return False

        legacy = self._open_read_only(path)
        try:
            if not self._table_exists(legacy, table):
                return False
            return legacy.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None
        finally:
            legacy.close()

    @staticmethod
    def _open_read_only(path):
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _table_exists(connection, table):
        found = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
        return found is not None


def legacy_barcode_with_package(barcode, identifier):
    """A embalagem por código de barras só existe nas versões antigas mais novas; nas outras fica vazia."""
    columns = identifier.keys()

    def column_or_none(column):
        return identifier[column] if column in columns else None

    return {
        "barcode": barcode,
        "package_description": column_or_none("description"),
        "net_quantity": column_or_none("net_quantity"),
        "net_unit": column_or_none("net_unit"),
        "units_per_pack": column_or_none("units_per_pack"),
    }
