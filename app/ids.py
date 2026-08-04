import uuid


def new_id(prefix: str) -> str:
    """ID publico legivel, ex: prod_a1b2c3d4e5f6.

    Nao usamos GTIN como chave primaria (nem todo produto tem um, e um
    produto pode ter varios) - ver models_public.ProductIdentifier.
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
