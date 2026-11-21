from pathlib import Path

from database.database import CommunityDatabase, Database
from database.legacy_import import LegacyImport

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SCHEMA = PROJECT_ROOT / "docs" / "database.sql"
COMMUNITY_SCHEMA = PROJECT_ROOT / "docs" / "community.sql"


def prepare_databases():
    """
    Roda toda vez que o app inicia, antes de atender qualquer requisição:
    deixa os dois bancos iguais aos arquivos .sql e, na primeira vez,
    copia os dados da versão antiga do ProdBR. Nenhum passo manual no servidor.
    """
    for database, schema in ((Database(), PUBLIC_SCHEMA), (CommunityDatabase(), COMMUNITY_SCHEMA)):
        ok, changes = database.migrate(str(schema))
        if not ok:
            raise SystemExit(f"[DB] Migração de {schema.name} falhou: {changes}")
        for change in changes:
            print(f"[DB] {schema.name}: {change}")

    ok, messages = LegacyImport().run_if_needed()
    if not ok:
        raise SystemExit(f"[DB] Importação dos dados antigos falhou: {messages}")
    for message in messages:
        print(f"[DB] {message}")
