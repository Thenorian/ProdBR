from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import PublicBase
from app.ids import new_id


def utcnow() -> datetime:
    # Naive-UTC de proposito: DateTime nao faz round-trip
    # confiavel de tzinfo no SQLite. Convencao do projeto: todo datetime
    # salvo/comparado e naive e implicitamente UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Product(PublicBase):
    """Identificacao de um produto - sem preco, custo ou fornecedor, e sem
    aliquotas (isso mora em FiscalRule, chaveada por NCM e nao pelo
    produto, ja que a lei tributa a classificacao fiscal, nao o SKU).
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=lambda: new_id("prod"))

    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Nullable no banco (nao na API - ProductCreate/Update exigem NCM):
    # importacao em lote (ver importers/) pode gerar produtos com NCM
    # ainda nao mapeado, pendente de revisao manual antes de aplicar.
    ncm: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commercial_unit: Mapped[str] = mapped_column(String(10), default="UN")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Origem do cadastro em si (nao das aliquotas - essa fonte fica em
    # FiscalRule.source). Ex: "GS1 Brasil", "Contribuicao da comunidade".
    source: Mapped[str] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    identifiers: Mapped[list["ProductIdentifier"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


IDENTIFIER_TYPES = (
    "gtin8",
    "gtin12",
    "gtin13",
    "gtin14",
    "upc",
    "ean",
    "manufacturer_code",
    "other",
)


class ProductIdentifier(PublicBase):
    """Um produto pode ter varios identificadores (unidade, caixa, codigo
    proprio do fabricante etc). Nao limitado a GTIN."""

    __tablename__ = "product_identifiers"
    __table_args__ = (UniqueConstraint("type", "value", name="uq_identifier_type_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(String(64), index=True)

    product: Mapped[Product] = relationship(back_populates="identifiers")


class FiscalRule(PublicBase):
    """Aliquotas de referencia para um NCM (+ CEST opcional), por UF e
    vigencia. Compartilhada por todo produto com o mesmo NCM/CEST - a lei
    tributa a classificacao fiscal, nao o produto especifico.

    uf=None significa regra nacional/default, usada quando nao ha regra
    especifica para o estado consultado. Ver app/fiscal.py para a
    resolucao (mais especifica + vigente na data pedida).
    """

    __tablename__ = "fiscal_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    ncm: Mapped[str] = mapped_column(String(8), index=True)
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Codigo de origem da mercadoria (tabela ICMS - Origem, 0 a 8).
    origin: Mapped[int | None] = mapped_column(nullable=True)

    icms_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ipi_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pis_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    cofins_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Reforma tributaria (EC 132/2023).
    cbs_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ibs_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Revision(PublicBase):
    """Historico de alteracoes, tipo `git log` publico - uma linha por
    campo alterado. `contributor` e o username denormalizado (a base de
    comunidade e um banco separado, sem FK cruzando arquivos)."""

    __tablename__ = "revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # product | identifier | fiscal_rule
    entity_id: Mapped[str] = mapped_column(String(20), index=True)
    contributor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    action: Mapped[str] = mapped_column(String(10))  # create | update | delete
    field: Mapped[str | None] = mapped_column(String(60), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
