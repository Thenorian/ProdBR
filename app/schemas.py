from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models_public import IDENTIFIER_TYPES

REASON = Field(..., min_length=3, max_length=300, description="Motivo da alteracao (obrigatorio).")


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    ncm: str = Field(..., min_length=8, max_length=8, description="NCM com 8 digitos, sem pontuacao.")
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=150)
    commercial_unit: str = Field("UN", max_length=10)
    description: str | None = Field(None, max_length=1000)
    manufacturer: str | None = Field(None, max_length=120)
    source: str = Field(..., min_length=1, max_length=120, description="De onde veio esse cadastro.")


class ProductCreate(ProductBase):
    reason: str = REASON


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=120)
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    category: str | None = Field(None, max_length=150)
    commercial_unit: str | None = Field(None, max_length=10)
    description: str | None = Field(None, max_length=1000)
    manufacturer: str | None = Field(None, max_length=120)
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class IdentifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    value: str
    description: str | None = None
    net_quantity: float | None = None
    net_unit: str | None = None
    units_per_pack: int | None = None


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    # Nullable so de leitura: importacao em lote pode gerar produtos com
    # NCM pendente de revisao (ver importers/). Escrita via API continua
    # exigindo NCM normalmente (ProductCreate/ProductUpdate acima).
    ncm: str | None = Field(None, min_length=8, max_length=8)
    identifiers: list[IdentifierOut] = []
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
    note: str = "Limite maximo de itens por requisicao. Use offset para paginar."


class IdentifierCreate(BaseModel):
    product_id: str
    type: str = Field(..., description=f"Um de: {', '.join(IDENTIFIER_TYPES)}")
    value: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(None, max_length=120, description="Embalagem como o fabricante escreve, ex: 'Pacote 15 kg'. Se os campos abaixo vierem vazios, sao lidos daqui quando da pra ter certeza.")
    net_quantity: float | None = Field(None, gt=0)
    net_unit: str | None = Field(None, description="g, kg, mg, ml, l ou un")
    units_per_pack: int | None = Field(None, ge=1)
    reason: str = REASON


class IdentifierUpdate(BaseModel):
    type: str | None = Field(None, description=f"Um de: {', '.join(IDENTIFIER_TYPES)}")
    value: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=120, description="Embalagem como o fabricante escreve, ex: 'Pacote 15 kg'. Se os campos abaixo vierem vazios, sao lidos daqui quando da pra ter certeza.")
    net_quantity: float | None = Field(None, gt=0)
    net_unit: str | None = Field(None, description="g, kg, mg, ml, l ou un")
    units_per_pack: int | None = Field(None, ge=1)
    reason: str = REASON


class IdentifierDelete(BaseModel):
    reason: str = REASON


class FiscalRuleBase(BaseModel):
    ncm: str = Field(..., min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    country: str = Field("BR", min_length=2, max_length=2, description="Pais do Mercosul a que essa regra se refere (ISO 3166-1 alpha-2). Hoje so ha dados para BR.")
    uf: str | None = Field(None, min_length=2, max_length=2, description="Sigla do estado/provincia, ou nulo para regra nacional/default.")
    origin: int | None = Field(None, ge=0, le=8)
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=1000)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100, description="Contribuicao sobre Bens e Servicos - reforma tributaria (EC 132/2023).")
    ibs_rate: float | None = Field(None, ge=0, le=100, description="Imposto sobre Bens e Servicos - reforma tributaria (EC 132/2023).")
    ii_rate: float | None = Field(None, ge=0, le=100, description="Imposto de Importacao (aliquota-base = TEC do Mercosul).")
    fcp_rate: float | None = Field(None, ge=0, le=100, description="Fundo de Combate a Pobreza - adicional estadual sobre o ICMS.")
    icms_st_mva_rate: float | None = Field(None, ge=0, description="Margem de Valor Agregado para calculo do ICMS-ST.")
    notes: str | None = Field(None, max_length=500, description="Particularidades do regime (isencao, monofasico, reducao de base de calculo etc).")
    valid_from: date
    valid_until: date | None = None
    source: str = Field(..., min_length=1, max_length=120)


class FiscalRuleCreate(FiscalRuleBase):
    reason: str = REASON


class FiscalRuleUpdate(BaseModel):
    ncm: str | None = Field(None, min_length=8, max_length=8)
    cest: str | None = Field(None, max_length=7)
    country: str | None = Field(None, min_length=2, max_length=2)
    uf: str | None = Field(None, min_length=2, max_length=2)
    origin: int | None = Field(None, ge=0, le=8)
    icms_rate: float | None = Field(None, ge=0, le=100)
    ipi_rate: float | None = Field(None, ge=0, le=1000)
    pis_rate: float | None = Field(None, ge=0, le=100)
    cofins_rate: float | None = Field(None, ge=0, le=100)
    cbs_rate: float | None = Field(None, ge=0, le=100)
    ibs_rate: float | None = Field(None, ge=0, le=100)
    ii_rate: float | None = Field(None, ge=0, le=100)
    fcp_rate: float | None = Field(None, ge=0, le=100)
    icms_st_mva_rate: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=500)
    valid_from: date | None = None
    valid_until: date | None = None
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class FiscalRuleOut(FiscalRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CountryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class StateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    country_id: str


class NcmBase(BaseModel):
    ncm: str = Field(..., min_length=8, max_length=8, description="NCM com 8 digitos, sem pontuacao.")
    description: str = Field(..., min_length=1, max_length=500, description="Texto oficial da classificacao (TIPI/Mercosul).")
    chapter: str | None = Field(None, min_length=2, max_length=2, description="Dois primeiros digitos do NCM (capitulo).")
    category: str | None = Field(None, max_length=150, description="Categoria normalizada (ex: Bebidas, Ferragens).")
    unit: str | None = Field(None, max_length=20, description="Unidade estatistica de comercio exterior (ex: UN, KG).")
    source: str = Field(..., min_length=1, max_length=120)


class NcmCreate(NcmBase):
    reason: str = REASON


class NcmUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=500)
    chapter: str | None = Field(None, min_length=2, max_length=2)
    category: str | None = Field(None, max_length=150)
    unit: str | None = Field(None, max_length=20)
    source: str | None = Field(None, min_length=1, max_length=120)
    reason: str = REASON


class NcmOut(NcmBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime


class NcmDetail(NcmOut):
    """Ficha completa de um NCM: classificacao + todas as regras fiscais
    ja cadastradas para ele (qualquer pais/UF) + quantos produtos usam
    essa classificacao - tudo sem precisar de um produto especifico."""

    product_count: int = 0
    fiscal_rules: list[FiscalRuleOut] = []


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    contributor: str | None
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str
    created_at: datetime
