"""Grava no banco os produtos coletados pelos importadores (importers/output/*.csv).

Uso (no servidor: docker exec prodbr python -m scripts.import_manufacturer_products ...):
    python -m scripts.import_manufacturer_products importers/output/all_manufacturers.csv

Pode rodar mais de uma vez: produto com o mesmo nome e fabricante é pulado.
O NCM do CSV é só sugestão por categoria, então só entra se estiver em vigor
na tabela oficial; senão o produto entra sem NCM (e usa o da categoria, se houver).
Rode antes o scripts.import_ncm, para a tabela oficial estar no banco.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.category import CategoryDB  # noqa: E402
from database.ncm import NcmDB  # noqa: E402
from database.product import ProductDB  # noqa: E402
from database.setup import prepare_databases  # noqa: E402
from util.validation import clean_barcode, clean_category_path, clean_cest, clean_ncm  # noqa: E402

CONTRIBUTOR = "importador"
REASON = "Importado do site do fabricante (NCM sugerido pela categoria, não confirmado)"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m scripts.import_manufacturer_products importers/output/arquivo.csv")

    prepare_databases()

    products = ProductDB()
    categories = CategoryDB()
    ncm_table = NcmDB()
    counts = {"gravados": 0, "já existiam": 0, "sem NCM válido": 0}

    with open(sys.argv[1], encoding="utf-8") as file:
        for row in csv.DictReader(file):
            ok, already_exists = products.exists("products", {"name": row["name"], "manufacturer": row["manufacturer"] or None})
            if not ok:
                raise SystemExit(f"Erro ao consultar o banco: {already_exists}")
            if already_exists:
                counts["já existiam"] += 1
                continue

            ncm_code = official_ncm_or_none(ncm_table, row["ncm_suggested"])
            if row["ncm_suggested"] and ncm_code is None:
                counts["sem NCM válido"] += 1
                print(f"[aviso] NCM {row['ncm_suggested']} não está em vigor, produto entra sem NCM: {row['name']}")

            category_id = None
            category_names = clean_category_path(" > ".join(part for part in (row["category"], row["subcategory"]) if part))
            if category_names:
                ok, category_id = categories.find_or_create_path(category_names, CONTRIBUTOR, REASON)
                if not ok:
                    raise SystemExit(f"Erro ao criar a categoria: {category_id}")

            data = {
                "name": row["name"],
                "brand": row["brand"] or None,
                "manufacturer": row["manufacturer"] or None,
                "description": row["description"] or None,
                "category_id": category_id,
                "ncm_code": ncm_code,
                "cest": clean_cest(row["cest"]),
                "commercial_unit": row["commercial_unit"] or "UN",
                "source": row["source_url"][:255] or None,
            }
            barcode = clean_barcode(row["gtin"])

            ok, result = products.create(data, [barcode] if barcode else [], CONTRIBUTOR, REASON)
            if not ok:
                print(f"[erro] {row['name']}: {result}")
                continue
            counts["gravados"] += 1

    print(", ".join(f"{total} {label}" for label, total in counts.items()))


def official_ncm_or_none(ncm_table, suggested_ncm):
    ncm_code = clean_ncm(suggested_ncm)
    if not ncm_code:
        return None

    ok, ncm = ncm_table.get(ncm_code)
    if ok and ncm and ncm["in_force"]:
        return ncm_code
    return None


if __name__ == "__main__":
    main()
