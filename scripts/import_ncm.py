"""Importa a tabela oficial de NCM (JSON do Portal Único Siscomex) para o banco.

Uso:
    python -m scripts.import_ncm caminho/Tabela_NCM_Vigente_AAAAMMDD.json

Pode rodar de novo sempre que sair uma tabela nova: atualiza o que mudou e
marca como fora de vigor (in_force = FALSE) o que saiu da tabela.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from util.data_util import DataUtil  # noqa: E402
from database.database import Database  # noqa: E402

DATABASE_SQL = Path(__file__).resolve().parent.parent / "docs" / "database.sql"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m scripts.import_ncm caminho/Tabela_NCM_Vigente.json")

    ok, changes = Database().migrate(str(DATABASE_SQL))
    if not ok:
        raise SystemExit(f"[DB] Migração falhou: {changes}")
    for change in changes:
        print(f"[DB] {change}")

    ok, summary = DataUtil().import_ncm_file(sys.argv[1])
    if not ok:
        raise SystemExit(f"[NCM] Importação falhou: {summary}")

    print(f"[NCM] {summary['legal_act']} ({summary['version_label']})")
    print(f"[NCM] {summary['saved']} códigos gravados, {summary['no_longer_in_force']} saíram de vigor.")


if __name__ == "__main__":
    main()
