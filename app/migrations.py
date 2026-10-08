"""Migrações do esquema - roda sozinho ao subir o app.

Cada banco SQLite guarda a própria versão em `PRAGMA user_version`. Ao
subir:

- banco novo (sem tabela nenhuma): cria tudo pelos modelos e já marca a
  última versão - não tem o que migrar;
- banco existente com versão antiga: faz uma cópia do arquivo
  (`*.sqlite3.v<versão>.bak`, ao lado do original) e roda, em ordem, só as
  migrações que faltam - cada uma numa transação.

Migração nova = uma função no fim de PUBLIC_MIGRATIONS ou
COMMUNITY_MIGRATIONS. Nunca altere uma que já foi publicada: quem baixou a
base numa versão antiga depende dela pra chegar na atual.
"""

import json
import logging
import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.schema import CreateIndex, CreateTable

from app.config import settings
from app.database import CommunityBase, PublicBase, community_engine, public_engine, sqlite_path

log = logging.getLogger("prodbr.migrations")

Migration = Callable[[sqlite3.Connection], None]


# +--------------------------------------------------------------------+
# |  Utilitários                                                       |
# +--------------------------------------------------------------------+
def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {name for (name,) in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if table in _tables(conn) and column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _create_missing_tables(conn: sqlite3.Connection, base, engine) -> None:
    """CREATE TABLE/INDEX das tabelas do modelo que ainda não existem no
    arquivo, com o DDL gerado pelo próprio SQLAlchemy."""
    existing = _tables(conn)
    for table in base.metadata.sorted_tables:
        if table.name in existing:
            continue
        conn.execute(str(CreateTable(table).compile(engine)))
        for index in table.indexes:
            conn.execute(str(CreateIndex(index).compile(engine)))


# +--------------------------------------------------------------------+
# |  Base pública                                                      |
# +--------------------------------------------------------------------+
def _public_v1_columns_added_over_time(conn: sqlite3.Connection) -> None:
    """Colunas que foram aparecendo antes de existir controle de versão
    (antes eram criadas por `ensure_column` a cada boot)."""
    for column, ddl in (
        ("description", "VARCHAR(120)"),
        ("net_quantity", "FLOAT"),
        ("net_unit", "VARCHAR(5)"),
        ("units_per_pack", "INTEGER"),
    ):
        _add_column(conn, "product_identifiers", column, ddl)
    _add_column(conn, "countries", "language", "VARCHAR(10)")
    _add_column(conn, "countries", "subdivision_label", "VARCHAR(30)")
    _add_column(conn, "fiscal_rules", "rates", "JSON")


# Colunas de alíquota que fiscal_rules tinha até a v1 -> código do tributo.
_LEGACY_RATE_COLUMNS = {
    "icms_rate": "ICMS",
    "fcp_rate": "FCP",
    "icms_st_mva_rate": "ICMS_ST_MVA",
    "ipi_rate": "IPI",
    "ii_rate": "II",
    "pis_rate": "PIS",
    "cofins_rate": "COFINS",
    "cbs_rate": "CBS",
    "ibs_rate": "IBS",
}

# Tabelas recriadas na v2 e as colunas que passam da versão antiga pra nova
# (nova <- expressão sobre a antiga).
_V2_REBUILT = {
    "countries": {
        "id": "id",
        "name": "name",
        "language": "COALESCE(language, 'pt-BR')",
        "subdivision_label": "COALESCE(subdivision_label, 'UF')",
    },
    "states": {"country_id": "country_id", "code": "code", "name": "name"},
    "tax_types": {
        column: column
        for column in (
            "id", "country_id", "code", "name", "translations", "description", "level",
            "unit", "default_rate", "default_source", "sort_order", "active",
        )
    },
    "categories": {"id": "id", "name": "name"},
    "ncm_classifications": {
        "ncm": "ncm", "description": "description", "source": "source",
        "created_at": "created_at", "updated_at": "updated_at",
    },
    "fiscal_rules": {
        "id": "id", "ncm": "ncm", "cest": "cest", "country_id": "country", "state_code": "uf",
        "valid_from": "valid_from", "valid_until": "valid_until", "source": "source",
        "created_at": "created_at",
        # `origin` (origem da mercadoria) é do produto, não do NCM - se
        # alguém tinha preenchido, não se perde: vai pra observação.
        "notes": "TRIM(COALESCE(notes, '') || CASE WHEN origin IS NOT NULL "
                 "THEN ' Origem da mercadoria: ' || origin || '.' ELSE '' END)",
    },
}


def _public_v2_one_row_per_rate(conn: sqlite3.Connection) -> None:
    """fiscal_rules tinha uma coluna por tributo do Brasil (icms_rate,
    ipi_rate...) mais um JSON `rates` pros outros países, e tax_types.column
    dizia qual era qual. Vira uma tabela só, fiscal_rule_rates: uma linha
    por tributo, igual pra qualquer país.

    Também sai o que não tinha uso: ncm_classifications.chapter (são os 2
    primeiros dígitos do NCM), .unit e .category_id (nunca preenchidos),
    fiscal_rules.origin (é do produto, não do NCM), timestamps das tabelas
    de referência e os tipos de código "ean"/"upc" (= gtin13/gtin12)."""
    from app.sources.reference_data import COUNTRIES, TAX_TYPES

    existing = _tables(conn)
    for table in _V2_REBUILT:
        if table not in existing:
            continue
        # Índices têm nome único no banco: os da tabela velha saem antes da
        # nova ser criada com os mesmos nomes.
        for (index,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL", (table,)
        ).fetchall():
            conn.execute(f"DROP INDEX {index}")
        conn.execute(f"ALTER TABLE {table} RENAME TO _old_{table}")

    _create_missing_tables(conn, PublicBase, public_engine)

    for table, mapping in _V2_REBUILT.items():
        if table not in existing:
            continue
        columns = ", ".join(mapping)
        conn.execute(f"INSERT OR IGNORE INTO {table} ({columns}) SELECT {', '.join(mapping.values())} FROM _old_{table}")

    # Tributos do Brasil precisam existir pra converter as colunas antigas
    # (banco de antes da tabela tax_types não tem nenhum).
    for country_id, name, language, label in COUNTRIES:
        conn.execute(
            "INSERT OR IGNORE INTO countries (id, name, language, subdivision_label) VALUES (?, ?, ?, ?)",
            (country_id, name, language, label),
        )
    for order, spec in enumerate(TAX_TYPES["BR"]):
        conn.execute(
            "INSERT OR IGNORE INTO tax_types (country_id, code, name, translations, level, unit, sort_order, active)"
            " VALUES ('BR', ?, ?, ?, ?, 'percent', ?, 1)",
            (spec["code"], spec["name"], json.dumps(spec.get("translations"), ensure_ascii=False), spec["level"], order * 10),
        )

    if "fiscal_rules" in existing:
        _move_legacy_rates(conn)

    if "product_identifiers" in existing:
        conn.execute("UPDATE product_identifiers SET type = LOWER(REPLACE(type, '-', ''))")
        conn.execute("UPDATE product_identifiers SET type = 'gtin13' WHERE type IN ('ean', 'ean13')")
        conn.execute("UPDATE product_identifiers SET type = 'gtin12' WHERE type IN ('upc', 'upca')")

    for table in _V2_REBUILT:
        if table in existing:
            conn.execute(f"DROP TABLE _old_{table}")


def _move_legacy_rates(conn: sqlite3.Connection) -> None:
    """Colunas de alíquota e o JSON `rates` -> fiscal_rule_rates. Valor de
    um tributo que o país da regra não tem cadastrado não some: vai pra
    observação da regra."""
    tax_ids = {(country, code): tax_id for tax_id, country, code in conn.execute("SELECT id, country_id, code FROM tax_types")}
    old_columns = _columns(conn, "_old_fiscal_rules")
    legacy = [column for column in _LEGACY_RATE_COLUMNS if column in old_columns]
    select = ", ".join(["id", "country", *legacy, "rates" if "rates" in old_columns else "NULL"])

    for row in conn.execute(f"SELECT {select} FROM _old_fiscal_rules").fetchall():
        rule_id, country, *values = row
        raw_json = values.pop()
        rates = {_LEGACY_RATE_COLUMNS[column]: value for column, value in zip(legacy, values) if value is not None}
        if raw_json:
            loaded = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            rates.update({code.upper(): value for code, value in (loaded or {}).items() if value is not None})

        orphans = []
        for code, value in rates.items():
            tax_id = tax_ids.get((country, code))
            if tax_id is None:
                orphans.append(f"{code}: {value:g}")
                continue
            conn.execute(
                "INSERT OR REPLACE INTO fiscal_rule_rates (rule_id, tax_type_id, rate) VALUES (?, ?, ?)",
                (rule_id, tax_id, value),
            )
        if orphans:
            note = f"Alíquotas sem tributo cadastrado em {country}: {', '.join(orphans)}."
            conn.execute(
                "UPDATE fiscal_rules SET notes = SUBSTR(TRIM(COALESCE(notes, '') || ' ' || ?), 1, 500) WHERE id = ?",
                (note, rule_id),
            )


PUBLIC_MIGRATIONS: list[Migration] = [
    _public_v1_columns_added_over_time,
    _public_v2_one_row_per_rate,
]


# +--------------------------------------------------------------------+
# |  Base de comunidade                                                |
# +--------------------------------------------------------------------+
def _community_v1_user_flags(conn: sqlite3.Connection) -> None:
    _add_column(conn, "users", "tier_override", "VARCHAR(20)")
    _add_column(conn, "users", "auto_approve", "BOOLEAN NOT NULL DEFAULT 0")


COMMUNITY_MIGRATIONS: list[Migration] = [
    _community_v1_user_flags,
]


# +--------------------------------------------------------------------+
# |  Execução                                                          |
# +--------------------------------------------------------------------+
def upgrade(url: str, base, engine, migrations: list[Migration]) -> None:
    """Deixa o banco de `url` na última versão (ver docstring do módulo)."""
    if not url.startswith("sqlite"):
        base.metadata.create_all(bind=engine)
        return

    path = sqlite_path(url)
    latest = len(migrations)
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        if not _tables(conn):
            base.metadata.create_all(bind=engine)
            conn.execute(f"PRAGMA user_version = {latest}")
            return

        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current < latest:
            backup = Path(f"{path}.v{current}.bak")
            shutil.copy2(path, backup)
            log.warning("Banco %s na versão %s - cópia de segurança em %s.", path, current, backup)
            # FK desligada durante a migração: tabelas são recriadas e
            # copiadas fora de ordem. legacy_alter_table impede o RENAME de
            # reescrever as FKs das outras tabelas pro nome temporário.
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("PRAGMA legacy_alter_table = ON")
            for version in range(current, latest):
                conn.execute("BEGIN")
                try:
                    migrations[version](conn)
                    conn.execute(f"PRAGMA user_version = {version + 1}")
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
                log.warning("Banco %s migrado para a versão %s.", path, version + 1)
    finally:
        conn.close()

    base.metadata.create_all(bind=engine)


def upgrade_all() -> None:
    upgrade(settings.public_database_url, PublicBase, public_engine, PUBLIC_MIGRATIONS)
    upgrade(settings.community_database_url, CommunityBase, community_engine, COMMUNITY_MIGRATIONS)
