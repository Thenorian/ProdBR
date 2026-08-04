"""Promove um usuario ja registrado a moderador ou admin (uso
administrativo/CLI - bootstrap do primeiro moderador de uma instancia).

Uso:
    python -m scripts.promote_user <username> <moderator|admin>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import CommunityBase, CommunitySession, community_engine  # noqa: E402
from app.models_community import ROLES, User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[2] not in ROLES:
        print(f"Uso: python -m scripts.promote_user <username> <{'|'.join(ROLES)}>")
        raise SystemExit(1)

    username, role = sys.argv[1], sys.argv[2]

    CommunityBase.metadata.create_all(bind=community_engine)
    db = CommunitySession()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(f"Usuario '{username}' nao encontrado - registre-se primeiro via POST /auth/register.")
            raise SystemExit(1)
        user.role = role
        db.commit()
    finally:
        db.close()

    print(f"'{username}' agora e '{role}'.")


if __name__ == "__main__":
    main()
