"""Importador PremieR Pet - fonte: premierpet.com.br (site oficial do
fabricante). Coletado manualmente em 2026-08-04 navegando o catalogo do
site; nenhum GTIN e informado nessas paginas (comum em sites de
fabricante voltados ao consumidor final, que normalmente nao publicam
codigo de barras por SKU) - por isso todo produto fica sem GTIN, como
manda a regra "nunca inventar".

Cada nome de produto abaixo e o nome EXATO listado em:
https://premierpet.com.br/linha/premier-racas-especificas-caes/
(21 resultados, categoria "PremieR Racas Especificas" de racao para caes)
"""

from importers.common import ImportedProduct, write_outputs

LISTING_URL = "https://premierpet.com.br/linha/premier-racas-especificas-caes/"

# Confirmado individualmente (pagina propria do produto):
# 1kg / 2,5kg / 7,5kg - varia por SKU, por isso commercial_unit fica "KG"
# generico em vez de fixar um peso que nao se aplica a linha toda.
CONFIRMED_PRODUCT_URL = {
    "PremieR Raças Específicas Bulldog Francês Adultos Porte Pequeno Frango": (
        "https://premierpet.com.br/produto/premier-racas-especificas-bulldog-frances-adultos-sabor-frango/"
    ),
}

PRODUCT_NAMES = [
    "PremieR Raças Específicas Pug Filhotes Porte Pequeno Frango",
    "PremieR Raças Específicas Pug Adultos Porte Pequeno Frango",
    "PremieR Raças Específicas Spitz Alemão Adulto Porte Pequeno Frango",
    "PremieR Raças Específicas Spitz Alemão Filhotes Porte Pequeno Frango",
    "PremieR Raças Específicas Bulldog Inglês Adultos Porte Médio Frango",
    "PremieR Raças Específicas Bulldog Francês Adultos Porte Pequeno Frango",
    "PremieR Raças Específicas Filhotes Frango Bulldog Francês",
    "PremieR Raças Específicas Golden Retriever Adultos Porte Grande Frango",
    "PremieR Raças Específicas Cães Adultos Frango Labrador",
    "PremieR Raças Específicas Labrador Filhotes Porte Grande Frango",
    "PremieR Raças Específicas Lhasa Apso Adultos Porte Pequeno Frango",
    "PremieR Raças Específicas Lhasa Apso Filhotes Porte Pequeno Frango",
    "PremieR Raças Específicas Maltês Adultos Porte Pequeno Peru e Arroz",
    "PremieR Raças Específicas Maltês Filhotes Porte Pequeno Peru & Arroz",
    "PremieR Raças Específicas Adultos Frango Pit Bull",
    "PremieR Raças Específicas Shih Tzu Adultos Porte Pequeno Frango",
    "PremieR Raças Específicas Shih Tzu Adultos Porte Pequeno Salmão",
    "PremieR Raças Específicas Shih Tzu Filhotes Porte Pequeno Frango",
    "PremieR Raças Específicas Yorkshire Adultos Porte Pequeno Frango",
    "PremieR Raças Específicas Yorkshire Filhotes Porte Pequeno Frango",
    "PremieR Raças Específicas Golden Retriever Filhotes Porte Grande Sabor Frango",
]


def collect() -> list[ImportedProduct]:
    products = []
    for name in PRODUCT_NAMES:
        products.append(
            ImportedProduct(
                name=name,
                brand="PremieR",
                manufacturer="PremieR Pet",
                category="Pet > Ração Cães > Raças Específicas",
                source_url=CONFIRMED_PRODUCT_URL.get(name, LISTING_URL),
                ncm_category_key="racao_pet",
                commercial_unit="KG",
                notes="Linha disponivel em multiplos tamanhos de embalagem (1kg/2,5kg/7,5kg conforme SKU) - peso especifico nao confirmado por produto.",
            )
        )
    return products


if __name__ == "__main__":
    items = collect()
    sql_path, csv_path = write_outputs(items, "premier_pet")
    print(f"{len(items)} produtos PremieR Pet -> {sql_path.name}, {csv_path.name}")
