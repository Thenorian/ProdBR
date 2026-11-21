import os
from pathlib import Path

from database.database import CommunityDatabase, Database
from database.legacy_import import LegacyImport

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SCHEMA = PROJECT_ROOT / "docs" / "database.sql"
DEFAULT_NCM_TABLES_FOLDER = PROJECT_ROOT / "reference_data" / "ncm"
COMMUNITY_SCHEMA = PROJECT_ROOT / "docs" / "community.sql"


def prepare_databases():
    """
    Roda toda vez que o app inicia, antes de atender qualquer requisição:
    deixa os dois bancos iguais aos arquivos .sql e, na primeira vez,
    copia os dados da versão antiga do ProdBR. Também importa a tabela oficial
    de NCM mais nova da pasta reference_data/ncm, se ainda não foi importada.
    Nenhum passo manual no servidor.
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

    import_newest_ncm_table_if_needed()


def import_newest_ncm_table_if_needed():
    """
    Reserva para a primeira subida: se a tabela da pasta reference_data/ncm ainda não foi
    importada, importa. A atualização de verdade é o download diário (util/official_data.py);
    esta pasta só garante que o banco nunca fica sem NCM se o site do governo estiver fora do ar.
    """
    from util.data_util import DataUtil

    ncm_tables_folder = Path(os.getenv("NCM_TABLES_FOLDER") or DEFAULT_NCM_TABLES_FOLDER)
    ncm_files = sorted(ncm_tables_folder.glob("Tabela_NCM_Vigente_*.json"))
    if not ncm_files:
        return

    newest_file = ncm_files[-1]
    ok, already_imported = Database().exists("ncm_imports", where={"file_name": newest_file.name})
    if not ok:
        raise SystemExit(f"[NCM] Erro ao consultar as importações: {already_imported}")
    if already_imported:
        return

    ok, any_import = Database().exists("ncm_imports", where={"id": ("!=", "")})
    if ok and any_import:
        return  # o banco já tem uma tabela (do download diário); a da pasta pode ser mais velha

    ok, summary = DataUtil().import_ncm_file(newest_file)
    if not ok:
        raise SystemExit(f"[NCM] Importação de {newest_file.name} falhou: {summary}")
    print(f"[NCM] {newest_file.name}: {summary['saved']} códigos, {summary['no_longer_in_force']} saíram de vigor")
