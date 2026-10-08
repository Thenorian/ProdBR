"""Importa/atualiza IPI (TIPI - Receita Federal) e II (TEC - MDIC/Gecex)
oficiais de cada NCM em fiscal_rules (regra nacional, BR). Idempotente -
roda quantas vezes precisar; aliquota que mudou encerra a regra antiga e
cria outra (historico preservado), nada e apagado.

Uso:
    python -m scripts.import_tributos
    python -m scripts.import_tributos --tipi tipi.xlsx --tec tec.xlsx   # planilhas ja baixadas

O app tambem faz isso sozinho uma vez por dia (NCM_AUTO_UPDATE=true, padrao).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import PublicBase, PublicSession, public_engine  # noqa: E402
from app import tax_official as tax  # noqa: E402


def _arg(name):
    return Path(sys.argv[sys.argv.index(name) + 1]).read_bytes() if name in sys.argv else None


def main():
    PublicBase.metadata.create_all(bind=public_engine)
    print("Lendo a TIPI (IPI)...")
    tipi, exes, tipi_act = tax.parse_tipi(tax.read_xlsx(_arg("--tipi") or tax._get(tax.TIPI_URL)))
    print("Lendo a TEC (II)...")
    tec_bytes = _arg("--tec")
    if tec_bytes is None:
        url = tax.tec_url(tax._get(tax.TEC_PAGE_URL, timeout=60).decode("utf-8", "replace"))
        if not url:
            sys.exit("Planilha da TEC nao encontrada na pagina do MDIC - baixe e use --tec arquivo.xlsx")
        tec_bytes = tax._get(url)
    tec, tec_act = tax.parse_tec(tax.read_xlsx(tec_bytes))
    source = tax.source_label(tipi_act, tec_act)
    print(f"{source} | IPI: {len(tipi)} NCMs | II: {len(tec)} NCMs")
    db = PublicSession()
    try:
        stats = tax.apply(db, tipi, exes, tec, source)
    finally:
        db.close()
    print(f"Regras criadas: {stats['criadas']} | alteradas: {stats['alteradas']} | iguais: {stats['iguais']}")


if __name__ == "__main__":
    main()
