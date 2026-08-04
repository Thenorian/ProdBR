"""Popula o banco com alguns produtos de exemplo, para testar localmente.

Uso:
    python -m scripts.seed_example
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Product, ProductBarcode  # noqa: E402

EXAMPLES = [
    {
        "ncm": "22030000",
        "description": "Cerveja em garrafa de vidro, 600ml",
        "unit": "UN",
        "origin": 0,
        "icms_rate": 18.0,
        "ipi_rate": 6.0,
        "barcodes": ["7891149100104"],
    },
    {
        "ncm": "19059090",
        "description": "Biscoito recheado sabor chocolate, pacote 130g",
        "unit": "UN",
        "origin": 0,
        "icms_rate": 18.0,
        "ipi_rate": 0.0,
        "barcodes": ["7891000100103"],
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for item in EXAMPLES:
            barcodes = item.pop("barcodes")
            product = Product(**item)
            db.add(product)
            db.flush()
            for code in barcodes:
                db.add(ProductBarcode(product_id=product.id, barcode=code))
        db.commit()
    finally:
        db.close()

    print(f"{len(EXAMPLES)} produtos de exemplo inseridos.")


if __name__ == "__main__":
    main()
