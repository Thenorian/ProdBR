"""Gera um token novo para um contribuidor que perdeu o dele (o acesso não tem senha para recuperar).

Uso (no servidor):
    docker exec prodbr python -m scripts.new_contributor_token claude_bot
    docker exec prodbr python -m scripts.new_contributor_token claude_bot --revogar-antigos

O token aparece uma única vez. Com --revogar-antigos, os tokens anteriores param de funcionar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.contributor import ContributorDB  # noqa: E402
from database.setup import prepare_databases  # noqa: E402


def main() -> None:
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    revoke_old_tokens = "--revogar-antigos" in sys.argv
    if len(arguments) != 1:
        raise SystemExit("Uso: python -m scripts.new_contributor_token <usuario> [--revogar-antigos]")

    prepare_databases()
    contributors = ContributorDB()

    ok, contributor = contributors.select("contributors", ["id", "username"], where={"username": arguments[0]}, fetch="one")
    if not ok or contributor is None:
        raise SystemExit(f"Contribuidor {arguments[0]} não encontrado.")

    if revoke_old_tokens:
        ok, revoked = contributors.delete("contributor_tokens", where={"contributor_id": contributor["id"]})
        print(f"{revoked} token(s) antigo(s) revogado(s).")

    ok, result = contributors.create_new_token(contributor)
    if not ok:
        raise SystemExit(f"Erro ao gerar o token: {result}")

    print(f"Token novo de {result['username']} (guarde, ele não aparece de novo):")
    print(result["token"])


if __name__ == "__main__":
    main()
