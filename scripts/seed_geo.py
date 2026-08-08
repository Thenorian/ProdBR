"""Carga inicial dos dados de referencia de pais/estado (bibliografia,
nao editavel via API). Idempotente - roda quantas vezes precisar.

Uso:
    python -m scripts.seed_geo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import PublicBase, PublicSession, public_engine  # noqa: E402
from app.models_public import Country, State  # noqa: E402

# So os membros plenos do Mercosul - ver README/about.html.
COUNTRIES = [
    ("BR", "Brasil"),
    ("AR", "Argentina"),
    ("PY", "Paraguai"),
    ("UY", "Uruguai"),
]

# Estados/DF do Brasil - unico pais com dados fiscais reais hoje (ver
# app/models_public.py::FiscalRule).
BRAZIL_STATES = [
    ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
    ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"), ("ES", "Espírito Santo"),
    ("GO", "Goiás"), ("MA", "Maranhão"), ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"),
    ("MG", "Minas Gerais"), ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"),
    ("PE", "Pernambuco"), ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
    ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"), ("SC", "Santa Catarina"),
    ("SP", "São Paulo"), ("SE", "Sergipe"), ("TO", "Tocantins"),
]


def main() -> None:
    PublicBase.metadata.create_all(bind=public_engine)
    db = PublicSession()
    try:
        for country_id, name in COUNTRIES:
            if db.get(Country, country_id) is None:
                db.add(Country(id=country_id, name=name))
        db.commit()

        existing = {(s.country_id, s.code) for s in db.query(State).filter(State.country_id == "BR").all()}
        for code, name in BRAZIL_STATES:
            if ("BR", code) not in existing:
                db.add(State(country_id="BR", code=code, name=name))
        db.commit()
    finally:
        db.close()

    print(f"{len(COUNTRIES)} paises e {len(BRAZIL_STATES)} estados (BR) verificados/inseridos.")


if __name__ == "__main__":
    main()
