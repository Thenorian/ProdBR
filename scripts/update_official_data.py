"""Baixa agora a tabela NCM (Siscomex), o IPI (TIPI) e o II (TEC), sem esperar a rotina diária.

Uso (no servidor: docker exec prodbr python -m scripts.update_official_data):
    python -m scripts.update_official_data
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.setup import prepare_databases  # noqa: E402
from util.daily_update import update_official_data_now  # noqa: E402

if __name__ == "__main__":
    prepare_databases()
    update_official_data_now()
