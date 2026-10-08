"""Tabelas da base pública - o arquivo que vai pra quem baixa o ProdBR.

Cada tabela e coluna tem `comment=`: é de lá que a página /estrutura é
gerada, então a documentação nunca fica diferente do banco de verdade.

    countries ─┬─< states
               ├─< tax_types ──────────────┐
               └─< fiscal_rules ─< fiscal_rule_rates
                        │ (ncm)
    ncm_classifications ┘
                        │ (ncm)
    categories ─< products ─< product_identifiers

    revisions: histórico de tudo (uma linha por campo alterado)

Regras que valem pra base toda:
- Nada de preço, custo, estoque ou fornecedor - só identificação e
  classificação fiscal.
- Nada de arquivo binário.
- Todo dado tem fonte (`source`) e toda alteração vira uma `revision`.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import PublicBase
from app.models.common import new_id, utcnow


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Referência: país, subdivisão e tributos. Vêm de fábrica          ║
# ║  (app/sources/reference_data.py) e o admin cadastra outros em     ║
# ║  /admin/tributos.                                                 ║
# ╚══════════════════════════════════════════════════════════════════╝
class Country(PublicBase):
    __tablename__ = "countries"
    __table_args__ = {"comment": "Países com tributação cadastrada. O NCM é do Mercosul, mas cada país tributa do seu jeito."}

    id: Mapped[str] = mapped_column(String(2), primary_key=True, comment="Código ISO 3166-1 alpha-2 (BR, AR, PY, UY...).")
    name: Mapped[str] = mapped_column(String(50), comment="Nome do país.")
    language: Mapped[str] = mapped_column(String(10), default="pt-BR", comment="Idioma padrão das respostas (BCP 47, ex: es-AR).")
    subdivision_label: Mapped[str] = mapped_column(String(30), default="UF", comment="Como o país chama a subdivisão: UF, Provincia, Departamento...")


class State(PublicBase):
    __tablename__ = "states"
    __table_args__ = {"comment": "Subdivisões de cada país (UF, província, departamento), código ISO 3166-2 sem o prefixo do país."}

    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), primary_key=True, comment="País (countries.id).")
    code: Mapped[str] = mapped_column(String(5), primary_key=True, comment="Sigla da subdivisão: SP, B (Buenos Aires), ASU (Assunção)...")
    name: Mapped[str] = mapped_column(String(80), comment="Nome da subdivisão.")


class TaxType(PublicBase):
    __tablename__ = "tax_types"
    __table_args__ = (
        UniqueConstraint("country_id", "code", name="uq_tax_type_country_code"),
        {"comment": "Tributos de cada país (ICMS, IPI, IVA...). A alíquota por NCM fica em fiscal_rule_rates."},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), index=True, comment="País do tributo (countries.id).")
    code: Mapped[str] = mapped_column(String(20), comment="Sigla, única dentro do país: ICMS, IPI, IVA, IIBB...")
    name: Mapped[str] = mapped_column(String(120), comment="Nome oficial, no idioma do país.")
    translations: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment='Nome em outros idiomas: {"pt": ..., "es": ..., "en": ...}.')
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Explicação curta do tributo.")
    level: Mapped[str] = mapped_column(String(10), default="national", comment="national (vale no país todo) ou state (muda por subdivisão).")
    unit: Mapped[str] = mapped_column(String(10), default="percent", comment="percent (alíquota em %) ou amount (valor fixo por unidade).")
    default_rate: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Alíquota geral do país, usada quando o NCM não tem regra própria (ex: IVA 21% na Argentina).")
    default_source: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="Lei/ato de onde vem a alíquota geral.")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="Ordem de exibição.")
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="Tributo desativado some da consulta (não é apagado: regras antigas podem usar).")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Catálogo: produto, códigos de barras e categoria.                ║
# ╚══════════════════════════════════════════════════════════════════╝
class Category(PublicBase):
    __tablename__ = "categories"
    __table_args__ = {"comment": 'Categorias de produto. A hierarquia vai no próprio nome: "Pet > Ração para Cães".'}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, comment="Nome completo da categoria.")


class Product(PublicBase):
    __tablename__ = "products"
    __table_args__ = {"comment": "Identificação do produto. Sem preço, custo, estoque, fornecedor e sem alíquota (alíquota é do NCM)."}

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=lambda: new_id("prod"), comment="ID gerado pelo ProdBR (prod_xxxxxxxxxxxx).")
    name: Mapped[str] = mapped_column(String(255), comment="Nome do produto como vai na nota.")
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="Marca.")
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="Fabricante (razão social ou nome conhecido).")
    ncm: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True, comment="NCM, 8 dígitos sem ponto (ncm_classifications.ncm). Vazio só em importação pendente de revisão.")
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True, comment="CEST, 7 dígitos - só produto sujeito a substituição tributária.")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True, comment="Categoria (categories.id).")
    commercial_unit: Mapped[str] = mapped_column(String(10), default="UN", comment="Unidade comercial da nota (UN, KG, CX...).")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="Descrição livre.")
    source: Mapped[str] = mapped_column(String(120), comment="De onde veio o cadastro (site do fabricante, GS1, comunidade...).")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="Cadastro (UTC).")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, comment="Última alteração (UTC).")

    identifiers: Mapped[list["ProductIdentifier"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    category_ref: Mapped[Category | None] = relationship()

    @property
    def category(self) -> str | None:
        """Nome da categoria - a API lê e escreve texto, o banco guarda o id."""
        return self.category_ref.name if self.category_ref else None


# gtin8/12/13/14 cobrem EAN e UPC (EAN-13 = GTIN-13, UPC-A = GTIN-12).
IDENTIFIER_TYPES = ("gtin8", "gtin12", "gtin13", "gtin14", "manufacturer_code", "other")


class ProductIdentifier(PublicBase):
    __tablename__ = "product_identifiers"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_identifier_type_value"),
        {"comment": "Códigos do produto - um por embalagem (1 kg, 15 kg, caixa com 12...). Mesmo produto = mesmos dados fiscais."},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True, comment="Produto (products.id).")
    type: Mapped[str] = mapped_column(String(20), comment="gtin8, gtin12, gtin13, gtin14, manufacturer_code ou other.")
    value: Mapped[str] = mapped_column(String(64), index=True, comment="O código em si (só dígitos, no caso do GTIN).")
    description: Mapped[str | None] = mapped_column(String(120), nullable=True, comment='Embalagem como o fabricante escreve: "Pacote 15 kg", "6x350ml".')
    net_quantity: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Quantidade líquida (lida da descrição só quando dá certeza).")
    net_unit: Mapped[str | None] = mapped_column(String(5), nullable=True, comment="Unidade da quantidade: g, kg, mg, ml, l ou un.")
    units_per_pack: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Itens dentro da embalagem (caixa com 12 = 12).")

    product: Mapped[Product] = relationship(back_populates="identifiers")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Fiscal: a classificação (NCM) e as alíquotas dela.               ║
# ║  A lei tributa a classificação, não o produto - dois produtos     ║
# ║  com o mesmo NCM compartilham as mesmas regras.                   ║
# ╚══════════════════════════════════════════════════════════════════╝
class NcmClassification(PublicBase):
    __tablename__ = "ncm_classifications"
    __table_args__ = {"comment": "Tabela NCM oficial (Siscomex), atualizada sozinha todo dia. Igual nos 4 países do Mercosul."}

    ncm: Mapped[str] = mapped_column(String(8), primary_key=True, comment="NCM, 8 dígitos sem ponto.")
    description: Mapped[str] = mapped_column(String(500), comment='Descrição com a hierarquia inteira: "Posição > Subposição > Item".')
    source: Mapped[str] = mapped_column(String(120), comment="Fonte e ato legal da tabela.")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="Entrada na base (UTC).")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, comment="Última alteração (UTC).")

    @property
    def chapter(self) -> str:
        """Capítulo = 2 primeiros dígitos (ex: 23 = resíduos e alimentos para animais)."""
        return self.ncm[:2]


class FiscalRule(PublicBase):
    __tablename__ = "fiscal_rules"
    __table_args__ = (
        ForeignKeyConstraint(["country_id", "state_code"], ["states.country_id", "states.code"]),
        Index("ix_fiscal_rules_lookup", "ncm", "country_id"),
        {"comment": "Uma regra = alíquotas de um NCM num escopo (país, subdivisão opcional, CEST opcional) e período."},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ncm: Mapped[str] = mapped_column(String(8), comment="NCM a que a regra se aplica (ncm_classifications.ncm).")
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True, comment="Só pra esse CEST. Vazio = qualquer CEST.")
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), default="BR", comment="País (countries.id).")
    state_code: Mapped[str | None] = mapped_column(String(5), nullable=True, comment="Subdivisão (states.code). Vazio = regra nacional.")
    valid_from: Mapped[date] = mapped_column(Date, comment="Vale a partir de.")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True, comment="Vale até (inclusive). Vazio = em vigor.")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Particularidades: isenção, monofásico, redução de base, exceções (Ex) da TIPI...")
    source: Mapped[str] = mapped_column(String(120), comment="De onde vêm as alíquotas (lei, TIPI, TEC, regulamento estadual...).")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="Cadastro (UTC).")

    rate_rows: Mapped[list["FiscalRuleRate"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def rates(self) -> dict[str, float]:
        """{código do tributo: alíquota}, ex: {"IPI": 6.5, "II": 12.6}."""
        return {row.tax_type.code: row.rate for row in self.rate_rows}


class FiscalRuleRate(PublicBase):
    __tablename__ = "fiscal_rule_rates"
    __table_args__ = {"comment": "Alíquota de um tributo dentro de uma regra. Sem linha = sem dado (diferente de alíquota zero)."}

    rule_id: Mapped[int] = mapped_column(ForeignKey("fiscal_rules.id", ondelete="CASCADE"), primary_key=True, comment="Regra (fiscal_rules.id).")
    tax_type_id: Mapped[int] = mapped_column(ForeignKey("tax_types.id"), primary_key=True, index=True, comment="Tributo (tax_types.id).")
    rate: Mapped[float] = mapped_column(Float, comment="Alíquota: % quando tax_types.unit = percent, valor quando = amount.")

    rule: Mapped[FiscalRule] = relationship(back_populates="rate_rows")
    tax_type: Mapped[TaxType] = relationship(lazy="joined")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Histórico: tipo `git log` público.                               ║
# ╚══════════════════════════════════════════════════════════════════╝
class Revision(PublicBase):
    __tablename__ = "revisions"
    __table_args__ = {"comment": "Histórico público: uma linha por campo alterado, com autor e motivo."}

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True, comment="product, identifier, fiscal_rule ou ncm_classification.")
    entity_id: Mapped[str] = mapped_column(String(20), index=True, comment="ID do registro alterado (texto, pra caber qualquer tipo de chave).")
    contributor: Mapped[str | None] = mapped_column(String(60), nullable=True, comment="Usuário que fez a alteração (o nome, já que usuários ficam em outro banco).")
    action: Mapped[str] = mapped_column(String(10), comment="create, update ou delete.")
    field: Mapped[str | None] = mapped_column(String(60), nullable=True, comment='Campo alterado. Alíquota aparece como "rates.ICMS".')
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Valor anterior, em JSON.")
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="Valor novo, em JSON.")
    reason: Mapped[str] = mapped_column(String(300), comment="Motivo informado por quem alterou (obrigatório).")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, comment="Quando (UTC).")
