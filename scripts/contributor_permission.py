"""Liga ou desliga as permissões especiais de um contribuidor.

    confiavel  grava direto, sem passar pela fila de votação (ERPs e bots da Thenorian)
    moderador  decide sozinho uma alteração da fila com um único voto

Uso (no servidor):
    docker exec prodbr python -m scripts.contributor_permission kainan moderador sim
    docker exec prodbr python -m scripts.contributor_permission erp_cliente confiavel nao
    docker exec prodbr python -m scripts.contributor_permission kainan            (só mostra como está)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.contributor import ContributorDB, contributor_level  # noqa: E402
from database.setup import prepare_databases  # noqa: E402

COLUMN_BY_PERMISSION = {"confiavel": "trusted", "moderador": "moderator"}
VALUE_BY_ANSWER = {"sim": 1, "nao": 0}
USAGE = "Uso: python -m scripts.contributor_permission <usuario> [confiavel|moderador sim|nao]"


def main() -> None:
    arguments = sys.argv[1:]
    if len(arguments) not in (1, 3):
        raise SystemExit(USAGE)

    prepare_databases()
    contributors = ContributorDB()
    username = arguments[0]

    if len(arguments) == 3:
        permission, answer = arguments[1], arguments[2]
        if permission not in COLUMN_BY_PERMISSION or answer not in VALUE_BY_ANSWER:
            raise SystemExit(USAGE)

        ok, changed_rows = contributors.update(
            "contributors", {COLUMN_BY_PERMISSION[permission]: VALUE_BY_ANSWER[answer]}, where={"username": username}
        )
        if not ok:
            raise SystemExit(f"Erro ao gravar: {changed_rows}")

    ok, contributor = contributors.select("contributors", where={"username": username}, fetch="one")
    if not ok or contributor is None:
        raise SystemExit(f"Contribuidor {username} não encontrado.")

    print(f"{contributor['username']}: {contributor_level(contributor['reputation'])} ({contributor['reputation']} pontos)")
    print(f"  confiável: {'sim' if contributor['trusted'] else 'não'}")
    print(f"  moderador: {'sim' if contributor['moderator'] else 'não'}")


if __name__ == "__main__":
    main()
