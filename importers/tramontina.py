"""Importador Tramontina - fonte: tramontina.com.br (loja oficial do
fabricante). Coletado manualmente em 2026-08-04 na listagem de
Ferramentas Manuais. Preco/frete/parcelamento (visiveis na pagina) foram
ignorados de proposito - ProdBR nao guarda esse tipo de dado.

Categoria de NCM so foi atribuida quando havia confianca razoavel na
classificacao; os demais ficam sem `ncm_category_key` (None) e caem na
revisao manual, em vez de arriscar uma classificacao errada.
"""

from importers.common import ImportedProduct, write_outputs

LISTING_URL = "https://www.tramontina.com.br/departamentos/ferramentas/ferramentas-manuais/"

# (nome, subcategoria, chave de NCM sugerido ou None)
PRODUCTS = [
    ("Espaçador Cruzeta Plástico Tramontina 1 mm (Saco com 100 un.)", "Fixação", None),
    (
        "Carrinho de Mão Extraforte Tramontina com Caçamba Reforçada Metálica Cinza 65 L, Braço Metálico e Pneu Maciço",
        "Carrinhos de Mão",
        "carrinho_mao",
    ),
    ("Organizador Plástico 16\" Tramontina MASTER", "Caixas, Bolsas e Organizadores", None),
    ("Maleta Plástica Organizadora 17\" Tramontina MASTER com Divisórias Móveis", "Caixas, Bolsas e Organizadores", None),
    (
        "Broca para Aço 9/16\" Tramontina MASTER em Aço Rápido HSS com Corpo Polido e Envernizado",
        "Brocas",
        "broca",
    ),
    (
        "Serrote para Poda Tramontina MASTER Supercut 14\" com 6 Dentes por Polegada em Aço Carbono e Cabo Injetado",
        "Serrotes e Arcos de Serra",
        "serrote",
    ),
    (
        "Conjunto de Lâminas para Arco de Serra Tramontina MASTER 12\" com 24 Dentes por Polegada em Aço 2 Peças",
        "Serrotes e Arcos de Serra",
        None,
    ),
    (
        "Jogo de Chaves Combinadas Tramontina Basic com Corpo em Aço Especial Cromado 5 Peças",
        "Chaves de Aperto",
        "ferramenta_manual",
    ),
    (
        "Jogo de Chaves Combinadas Tramontina Basic com Corpo em Aço Especial Cromado 17 Peças",
        "Chaves de Aperto",
        "ferramenta_manual",
    ),
    ("Broca para Aço 1.5x40 mm Tramontina MASTER em Aço Rápido HSS DIN 338", "Brocas", "broca"),
    (
        "Disco de Corte Fino 7\" Tramontina MASTER para Aço Inox e Materiais Endurecidos",
        "Discos",
        "disco_abrasivo",
    ),
    (
        "Cortador de Pisos e Azulejos 500 mm Tramontina MASTER com Disco de Corte em Carboneto Tungstênio e Peças em Aço e Alumínio",
        "Cortadores de Piso",
        None,
    ),
]


def collect() -> list[ImportedProduct]:
    products = []
    for name, subcategory, ncm_key in PRODUCTS:
        products.append(
            ImportedProduct(
                name=name,
                brand="Tramontina",
                manufacturer="Tramontina",
                category="Ferragens > Ferramentas Manuais",
                subcategory=subcategory,
                source_url=LISTING_URL,
                ncm_category_key=ncm_key,
                commercial_unit="UN",
            )
        )
    return products


if __name__ == "__main__":
    items = collect()
    sql_path, csv_path = write_outputs(items, "tramontina")
    print(f"{len(items)} produtos Tramontina -> {sql_path.name}, {csv_path.name}")
