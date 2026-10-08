from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import PublicBase
from app.ids import new_id


def utcnow() -> datetime:
    # Naive-UTC de proposito: DateTime nao faz round-trip
    # confiavel de tzinfo no SQLite. Convencao do projeto: todo datetime
    # salvo/comparado e naive e implicitamente UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Country(PublicBase):
    """Pais do Mercosul (bloco a que o NCM pertence). `id` e' o codigo ISO
    3166-1 alpha-2 (ex: "BR") - mesmo valor ja usado em FiscalRule.country,
    entao vira FK sem precisar migrar dado nenhum."""

    __tablename__ = "countries"

    id: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class State(PublicBase):
    """Estado/provincia de um pais - dado de referencia (bibliografia),
    nao uma FK obrigatoria em FiscalRule.uf (que continua uma sigla livre
    por simplicidade do formulario) - serve pra alimentar um seletor de
    UF real em vez de um campo de texto solto."""

    __tablename__ = "states"
    __table_args__ = (UniqueConstraint("country_id", "code", name="uq_state_country_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(5))
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Category(PublicBase):
    """Categoria normalizada, compartilhada por produtos e NCMs - em vez
    de repetir o mesmo texto de categoria em cada linha. Nome pode ser
    hierarquico como texto livre (ex: "Pet > Ração Cães > Filhotes"); a
    tabela em si e' flat, so o nome carrega a hierarquia."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


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
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
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
    category_ref: Mapped[Category | None] = relationship()

    @property
    def category(self) -> str | None:
        """Nome da categoria (via FK) - le/escreve como texto simples pra
        API/UI, mas armazenado normalizado. Ver app/changes.py::_resolve_category_id
        pra escrita (resolve/cria a Category por nome)."""
        return self.category_ref.name if self.category_ref else None


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
    # Embalagem deste codigo (um produto = mesmos dados fiscais; cada tamanho
    # tem seu GTIN). `description` e o texto como o fabricante escreve
    # ("Pacote 15 kg", "10,1kg") e nunca e alterado; os campos padronizados
    # sao lidos dele por app/packaging.py so quando da pra ter certeza.
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)
    net_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_unit: Mapped[str | None] = mapped_column(String(5), nullable=True)
    units_per_pack: Mapped[int | None] = mapped_column(Integer, nullable=True)

    product: Mapped[Product] = relationship(back_populates="identifiers")


class FiscalRule(PublicBase):
    """Aliquotas de referencia para um NCM (+ CEST opcional), por UF e
    vigencia. Compartilhada por todo produto com o mesmo NCM/CEST - a lei
    tributa a classificacao fiscal, nao o produto especifico.

    uf=None significa regra nacional/default, usada quando nao ha regra
    especifica para o estado consultado. Ver app/fiscal.py para a
    resolucao (mais especifica + vigente na data pedida).

    `country` existe porque o NCM e uma nomenclatura do Mercosul (Brasil,
    Argentina, Paraguai, Uruguai compartilham o mesmo codigo de 8 digitos
    e sua descricao - ver NcmClassification), mas cada pais tributa essa
    classificacao com tributos proprios. Hoje so ha dados fiscais do
    Brasil (`country="BR"`), mas o schema ja fica pronto para os demais
    membros do bloco sem precisar de migracao futura.
    """

    __tablename__ = "fiscal_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    ncm: Mapped[str] = mapped_column(String(8), index=True)
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True)
    country: Mapped[str] = mapped_column(ForeignKey("countries.id"), default="BR", index=True)
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
    # Imposto de Importacao - federal, aliquota-base definida pela TEC
    # (Tarifa Externa Comum do Mercosul), com listas de excecao por pais.
    ii_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Fundo de Combate a Pobreza - adicional estadual sobre o ICMS.
    fcp_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Margem de Valor Agregado usada no calculo do ICMS-ST, quando houver.
    icms_st_mva_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Espaco livre para particularidades do regime (monofasico, isencao,
    # reducao de base de calculo etc.) que nao valem um campo dedicado.
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NcmClassification(PublicBase):
    """A classificacao fiscal em si (o NCM), independente de qualquer
    produto - descricao oficial, hierarquia e afins. E a nomenclatura
    compartilhada por todo o Mercosul (mesmo codigo/descricao em Brasil,
    Argentina, Paraguai e Uruguai, salvo raras notas nacionais), por isso
    nao tem `country`: quem varia por pais e a tributacao (FiscalRule),
    nao a classificacao.

    Existe para permitir consultar "o que e e quanto pesa" um NCM sem
    precisar de um produto cadastrado - produtos continuam sendo a
    entidade principal, isso e so um catalogo de apoio.
    """

    __tablename__ = "ncm_classifications"

    ncm: Mapped[str] = mapped_column(String(8), primary_key=True)
    description: Mapped[str] = mapped_column(String(500))
    # Dois primeiros digitos do NCM, para navegacao/agrupamento (ex: "22"
    # = bebidas). Redundante com `ncm` de proposito - evita recalcular na
    # leitura toda hora.
    chapter: Mapped[str | None] = mapped_column(String(2), nullable=True)
    # Categoria normalizada (mesma tabela usada por Product) - opcional,
    # ajuda a navegar/agrupar NCMs por area (ex: "Bebidas", "Alimentos").
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    # Unidade estatistica de comercio exterior (Siscomex), ex: "UN", "KG".
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    category_ref: Mapped[Category | None] = relationship()

    @property
    def category(self) -> str | None:
        return self.category_ref.name if self.category_ref else None


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
