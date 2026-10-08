import uuid
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Data/hora em UTC, sem fuso (naive). Convenção do projeto: todo
    datetime gravado é UTC implícito - o SQLite não guarda fuso de forma
    confiável, então misturar com/sem fuso daria comparação errada."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix: str) -> str:
    """ID público legível, ex: prod_a1b2c3d4e5f6.

    O GTIN não é a chave do produto: nem todo produto tem um, e um produto
    pode ter vários (um por embalagem) - ver ProductIdentifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
