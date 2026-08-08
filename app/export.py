"""Geracao dos formatos de download da base publica. Sempre le direto do
arquivo de app.database.public_db_path() - nunca toca a base de comunidade,
que nao e distribuida (ver app/database.py e a filosofia no README).
"""

import csv
import io
import sqlite3
import zipfile

from app.database import public_db_path

PUBLIC_TABLES = ["categories", "products", "product_identifiers", "fiscal_rules", "ncm_classifications", "revisions"]


def _connect_readonly() -> sqlite3.Connection:
    path = public_db_path()
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def generate_sql_dump() -> str:
    conn = _connect_readonly()
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


def generate_csv_zip() -> bytes:
    conn = _connect_readonly()
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for table in PUBLIC_TABLES:
                cursor = conn.execute(f"SELECT * FROM {table}")
                columns = [d[0] for d in cursor.description]
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(columns)
                writer.writerows(cursor.fetchall())
                archive.writestr(f"{table}.csv", csv_buffer.getvalue())
    finally:
        conn.close()
    return buffer.getvalue()
