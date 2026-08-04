from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    """Cadastro generico de um produto: identificacao fiscal e tributaria.

    Nao guarda preco, custo ou fornecedor de proposito - ver Objetivo no
    card do Kanban: a base e publica e serve so para identificacao/aliquotas.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    ncm: Mapped[str] = mapped_column(String(8), index=True)
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(10), default="UN")

    gross_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Origem da mercadoria (tabela ICMS - Origem, 0 a 8).
    origin: Mapped[int | None] = mapped_column(nullable=True)

    icms_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ipi_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pis_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    cofins_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Reforma tributaria (EC 132/2023).
    cbs_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ibs_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    barcodes: Mapped[list["ProductBarcode"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    changelog: Mapped[list["ChangeLog"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductBarcode(Base):
    """Um produto pode ter mais de um codigo de barras (unidade, caixa, etc.)."""

    __tablename__ = "product_barcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    barcode: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    product: Mapped[Product] = relationship(back_populates="barcodes")


class ApiKey(Base):
    """Chave de acesso para edicao. So o hash e guardado - a chave em texto
    puro e mostrada uma unica vez, na criacao (scripts/create_api_key.py).
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChangeLog(Base):
    """Historico de alteracoes de um produto, tipo um `git log` publico."""

    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(10))  # create | update | delete
    diff: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="changelog")
    api_key: Mapped[ApiKey | None] = relationship()
