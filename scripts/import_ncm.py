"""Importa/atualiza a tabela NCM oficial (Siscomex) em ncm_classifications.
Idempotente - roda quantas vezes precisar (so cria e atualiza, nunca apaga).

Uso:
    python -m scripts.import_ncm
    python -m scripts.import_ncm --arquivo tabela.json   # JSON ja baixado

O app tambem faz isso sozinho uma vez por dia (NCM_AUTO_UPDATE=true, padrao).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import PublicBase, PublicSession, public_engine  # noqa: E402
from app.ncm_official import apply, fetch, parse, source_label  # noqa: E402


def main():
    PublicBase.metadata.create_all(bind=public_engine)
    if "--arquivo" in sys.argv:
        data = json.loads(Path(sys.argv[sys.argv.index("--arquivo") + 1]).read_text(encoding="utf-8"))
    else:
        print("Baixando a tabela NCM do Siscomex...")
        data = fetch()
    print(f"Vigencia: {data.get('Data_Ultima_Atualizacao_NCM')} | {source_label(data)}")
    db = PublicSession()
    try:
        stats = apply(db, parse(data), source_label(data))
    finally:
        db.close()
    print(f"NCMs criados: {stats['criados']} | atualizados: {stats['atualizados']} | iguais: {stats['iguais']}")


if __name__ == "__main__":
    main()
