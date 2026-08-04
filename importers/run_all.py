"""Roda todos os importadores disponiveis e gera tanto os arquivos
individuais por fabricante quanto um lote combinado `all_manufacturers`.

Uso:
    python -m importers.run_all
"""

from importers import ngk, premier_pet, tramontina
from importers.common import write_outputs

IMPORTERS = [premier_pet, tramontina, ngk]


def main() -> None:
    all_products = []
    for module in IMPORTERS:
        items = module.collect()
        sql_path, csv_path = write_outputs(items, module.__name__.rsplit(".", 1)[-1])
        print(f"{module.__name__}: {len(items)} produtos -> {sql_path.name}, {csv_path.name}")
        all_products.extend(items)

    sql_path, csv_path = write_outputs(all_products, "all_manufacturers")
    print(f"\nTotal: {len(all_products)} produtos -> {sql_path.name}, {csv_path.name}")


if __name__ == "__main__":
    main()
