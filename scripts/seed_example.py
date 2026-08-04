"""Popula a base publica com produtos de exemplo, para testar localmente.
Usa o mesmo motor de contribuicoes das rotas (app.changes), entao gera
Revision normalmente - contributor="seed" identifica que veio daqui.

Uso:
    python -m scripts.seed_example
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.changes import apply_identifier_create, dispatch_apply  # noqa: E402
from app.database import PublicBase, PublicSession, public_engine  # noqa: E402

PRODUCTS = [
    {
        "product": {
            "name": "Cerveja Pilsen, garrafa 600ml",
            "brand": "Exemplo",
            "ncm": "22030000",
            "category": "Bebidas",
            "commercial_unit": "UN",
            "manufacturer": "Cervejaria Exemplo LTDA",
            "source": "Contribuicao da comunidade",
        },
        "identifiers": [{"type": "gtin13", "value": "7891149100104"}],
        "fiscal": {
            "ncm": "22030000",
            "uf": None,
            "origin": 0,
            "icms_rate": 18.0,
            "ipi_rate": 6.0,
            "valid_from": date(2024, 1, 1).isoformat(),
            "source": "Receita Federal",
        },
    },
    {
        "product": {
            "name": "Biscoito recheado sabor chocolate, pacote 130g",
            "brand": "Exemplo",
            "ncm": "19059090",
            "category": "Alimentos",
            "commercial_unit": "UN",
            "manufacturer": "Alimentos Exemplo LTDA",
            "source": "Contribuicao da comunidade",
        },
        "identifiers": [{"type": "gtin13", "value": "7891000100103"}],
        "fiscal": {
            "ncm": "19059090",
            "uf": "SP",
            "origin": 0,
            "icms_rate": 18.0,
            "ipi_rate": 0.0,
            "valid_from": date(2024, 1, 1).isoformat(),
            "source": "SEFAZ-SP",
        },
    },
]


def main() -> None:
    PublicBase.metadata.create_all(bind=public_engine)
    db = PublicSession()
    try:
        for entry in PRODUCTS:
            product = dispatch_apply(db, "product", None, entry["product"], "seed", "Carga inicial de exemplo")
            for identifier in entry["identifiers"]:
                identifier["product_id"] = product.id
                apply_identifier_create(db, identifier, "seed", "Carga inicial de exemplo")
            dispatch_apply(db, "fiscal_rule", None, entry["fiscal"], "seed", "Carga inicial de exemplo")
    finally:
        db.close()

    print(f"{len(PRODUCTS)} produtos de exemplo inseridos (com identificador e regra fiscal).")


if __name__ == "__main__":
    main()
