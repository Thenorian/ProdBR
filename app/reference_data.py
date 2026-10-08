"""Dados de referencia que ja vem de fabrica: paises do Mercosul, suas
UFs/provincias/departamentos (codigos ISO 3166-2) e os tributos de cada
um, com nome traduzido em pt/es/en.

Roda sozinho ao subir o app (`ensure_reference_data`), entao uma
instalacao nova ja nasce pronta pra consulta - sem script nenhum. So
INSERE o que falta: o que o admin editou depois (nome, traducao,
aliquota geral) nunca e sobrescrito.
"""

from app.models_public import Country, State, TaxType

COUNTRIES = [
    # id, nome, idioma, como o pais chama a subdivisao
    ("BR", "Brasil", "pt-BR", "UF"),
    ("AR", "Argentina", "es-AR", "Provincia"),
    ("PY", "Paraguai", "es-PY", "Departamento"),
    ("UY", "Uruguai", "es-UY", "Departamento"),
]

STATES = {
    "BR": [
        ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
        ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"), ("ES", "Espírito Santo"),
        ("GO", "Goiás"), ("MA", "Maranhão"), ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"),
        ("MG", "Minas Gerais"), ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"),
        ("PE", "Pernambuco"), ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
        ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"), ("SC", "Santa Catarina"),
        ("SP", "São Paulo"), ("SE", "Sergipe"), ("TO", "Tocantins"),
    ],
    # ISO 3166-2:AR (sem o prefixo "AR-").
    "AR": [
        ("A", "Salta"), ("B", "Buenos Aires"), ("C", "Ciudad Autónoma de Buenos Aires"),
        ("D", "San Luis"), ("E", "Entre Ríos"), ("F", "La Rioja"), ("G", "Santiago del Estero"),
        ("H", "Chaco"), ("J", "San Juan"), ("K", "Catamarca"), ("L", "La Pampa"),
        ("M", "Mendoza"), ("N", "Misiones"), ("P", "Formosa"), ("Q", "Neuquén"),
        ("R", "Río Negro"), ("S", "Santa Fe"), ("T", "Tucumán"), ("U", "Chubut"),
        ("V", "Tierra del Fuego"), ("W", "Corrientes"), ("X", "Córdoba"), ("Y", "Jujuy"),
        ("Z", "Santa Cruz"),
    ],
    # ISO 3166-2:PY.
    "PY": [
        ("ASU", "Asunción"), ("1", "Concepción"), ("2", "San Pedro"), ("3", "Cordillera"),
        ("4", "Guairá"), ("5", "Caaguazú"), ("6", "Caazapá"), ("7", "Itapúa"),
        ("8", "Misiones"), ("9", "Paraguarí"), ("10", "Alto Paraná"), ("11", "Central"),
        ("12", "Ñeembucú"), ("13", "Amambay"), ("14", "Canindeyú"), ("15", "Presidente Hayes"),
        ("16", "Alto Paraguay"), ("19", "Boquerón"),
    ],
    # ISO 3166-2:UY.
    "UY": [
        ("AR", "Artigas"), ("CA", "Canelones"), ("CL", "Cerro Largo"), ("CO", "Colonia"),
        ("DU", "Durazno"), ("FS", "Flores"), ("FD", "Florida"), ("LA", "Lavalleja"),
        ("MA", "Maldonado"), ("MO", "Montevideo"), ("PA", "Paysandú"), ("RN", "Río Negro"),
        ("RV", "Rivera"), ("RO", "Rocha"), ("SA", "Salto"), ("SJ", "San José"),
        ("SO", "Soriano"), ("TA", "Tacuarembó"), ("TT", "Treinta y Tres"),
    ],
}

# Tributos de fabrica. Os do Brasil apontam pras colunas que FiscalRule ja
# tinha (`column`); os demais guardam a aliquota em FiscalRule.rates.
TAX_TYPES = {
    "BR": [
        dict(code="ICMS", level="state", column="icms_rate",
             name="Imposto sobre Circulação de Mercadorias e Serviços",
             translations={"es": "Impuesto sobre la Circulación de Mercaderías y Servicios",
                           "en": "Tax on the Circulation of Goods and Services (state VAT)"}),
        dict(code="FCP", level="state", column="fcp_rate",
             name="Fundo de Combate à Pobreza",
             translations={"es": "Fondo de Combate a la Pobreza", "en": "Poverty Combat Fund (ICMS surcharge)"}),
        dict(code="ICMS_ST_MVA", level="state", column="icms_st_mva_rate",
             name="Margem de Valor Agregado do ICMS-ST",
             translations={"es": "Margen de Valor Agregado del ICMS-ST", "en": "Added value margin for ICMS tax substitution"}),
        dict(code="IPI", level="national", column="ipi_rate",
             name="Imposto sobre Produtos Industrializados",
             translations={"es": "Impuesto sobre Productos Industrializados", "en": "Tax on Industrialized Products (federal excise)"}),
        dict(code="II", level="national", column="ii_rate",
             name="Imposto de Importação",
             translations={"es": "Impuesto de Importación", "en": "Import duty"}),
        dict(code="PIS", level="national", column="pis_rate",
             name="Contribuição para o PIS/Pasep",
             translations={"es": "Contribución al PIS/Pasep", "en": "PIS/Pasep social contribution"}),
        dict(code="COFINS", level="national", column="cofins_rate",
             name="Contribuição para o Financiamento da Seguridade Social",
             translations={"es": "Contribución para el Financiamiento de la Seguridad Social",
                           "en": "Social Security Financing Contribution"}),
        dict(code="CBS", level="national", column="cbs_rate",
             name="Contribuição sobre Bens e Serviços",
             translations={"es": "Contribución sobre Bienes y Servicios", "en": "Goods and Services Contribution (federal VAT)"}),
        dict(code="IBS", level="state", column="ibs_rate",
             name="Imposto sobre Bens e Serviços",
             translations={"es": "Impuesto sobre Bienes y Servicios", "en": "Goods and Services Tax (subnational VAT)"}),
    ],
    "AR": [
        dict(code="IVA", level="national", default_rate=21.0,
             default_source="Ley de IVA nº 23.349 (alícuota general)",
             name="Impuesto al Valor Agregado",
             description="Alícuota general 21%; algunos bienes tienen alícuota reducida (10,5%) o incrementada (27%).",
             translations={"pt": "Imposto sobre o Valor Agregado", "en": "Value Added Tax"}),
        dict(code="IIBB", level="state",
             name="Impuesto sobre los Ingresos Brutos",
             description="Provincial: la alícuota depende de la provincia y de la actividad.",
             translations={"pt": "Imposto sobre Receitas Brutas (provincial)", "en": "Gross Income Tax (provincial)"}),
        dict(code="DI", level="national",
             name="Derecho de Importación",
             translations={"pt": "Imposto de Importação", "en": "Import duty"}),
    ],
    "PY": [
        dict(code="IVA", level="national", default_rate=10.0,
             default_source="Ley nº 6380/2019 (tasa general)",
             name="Impuesto al Valor Agregado",
             description="Tasa general 10%; algunos bienes (canasta básica, entre otros) tienen tasa reducida de 5%.",
             translations={"pt": "Imposto sobre o Valor Agregado", "en": "Value Added Tax"}),
        dict(code="ISC", level="national",
             name="Impuesto Selectivo al Consumo",
             translations={"pt": "Imposto Seletivo ao Consumo", "en": "Selective Consumption Tax (excise)"}),
        dict(code="DI", level="national",
             name="Arancel de Importación",
             translations={"pt": "Imposto de Importação", "en": "Import duty"}),
    ],
    "UY": [
        dict(code="IVA", level="national", default_rate=22.0,
             default_source="Título 10, Texto Ordenado 1996 (tasa básica)",
             name="Impuesto al Valor Agregado",
             description="Tasa básica 22%; algunos bienes tienen tasa mínima de 10% o están exentos.",
             translations={"pt": "Imposto sobre o Valor Agregado", "en": "Value Added Tax"}),
        dict(code="IMESI", level="national",
             name="Impuesto Específico Interno",
             translations={"pt": "Imposto Específico Interno", "en": "Specific Internal Tax (excise)"}),
        dict(code="TGA", level="national",
             name="Tasa Global Arancelaria",
             translations={"pt": "Imposto de Importação", "en": "Import duty"}),
    ],
}


def ensure_reference_data(db) -> dict:
    """Insere o que falta (paises, UFs, tributos). Idempotente; nunca
    altera o que ja existe - exceto preencher idioma/rotulo de pais
    criado antes dessas colunas existirem."""
    stats = {"countries": 0, "states": 0, "tax_types": 0}
    for country_id, name, language, label in COUNTRIES:
        country = db.get(Country, country_id)
        if country is None:
            db.add(Country(id=country_id, name=name, language=language, subdivision_label=label))
            stats["countries"] += 1
        else:
            if not country.language:
                country.language = language
            if not country.subdivision_label:
                country.subdivision_label = label
    db.flush()

    for country_id, states in STATES.items():
        existing = {s.code for s in db.query(State).filter(State.country_id == country_id)}
        for code, name in states:
            if code not in existing:
                db.add(State(country_id=country_id, code=code, name=name))
                stats["states"] += 1

    for country_id, types in TAX_TYPES.items():
        existing = {t.code for t in db.query(TaxType).filter(TaxType.country_id == country_id)}
        for order, spec in enumerate(types):
            if spec["code"] not in existing:
                db.add(TaxType(country_id=country_id, sort_order=order * 10, **spec))
                stats["tax_types"] += 1
    db.commit()
    return stats
