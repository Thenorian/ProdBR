"""Carga dos dados de referencia (paises, UFs/provincias e tributos de
fabrica). O app ja faz isso sozinho ao subir - o script so existe pra
quem quiser rodar na mao. Idempotente: so insere o que falta.

Uso:
    python -m scripts.seed_geo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import PublicBase, PublicSession, public_engine  # noqa: E402
from app.reference_data import ensure_reference_data  # noqa: E402


def main() -> None:
    PublicBase.metadata.create_all(bind=public_engine)
    db = PublicSession()
    try:
        stats = ensure_reference_data(db)
    finally:
        db.close()
    print(f"Inseridos: {stats['countries']} paises, {stats['states']} subdivisoes, {stats['tax_types']} tributos.")


if __name__ == "__main__":
    main()
