"""Cria uma nova chave de API para edicao (uso administrativo/CLI).

A chave em texto puro so e mostrada uma vez aqui no terminal - o banco
guarda apenas o hash (sha256). Guarde a chave em local seguro.

Uso:
    python -m scripts.create_api_key "nome/descricao do titular da chave"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import ApiKey  # noqa: E402
from app.security import generate_key, hash_key  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print('Uso: python -m scripts.create_api_key "nome/descricao do titular"')
        raise SystemExit(1)

    name = sys.argv[1]

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        raw_key = generate_key()
        db.add(ApiKey(name=name, key_hash=hash_key(raw_key)))
        db.commit()
    finally:
        db.close()

    print(f"Chave criada para '{name}'.")
    print(f"Chave (guarde agora, nao sera mostrada de novo):\n{raw_key}")


if __name__ == "__main__":
    main()
