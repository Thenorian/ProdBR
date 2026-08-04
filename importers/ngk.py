"""Importador NGK - fonte: automotivo.ngkntk.com.br (site oficial da
Niterra do Brasil / NGK Automotivo). Coletado manualmente em 2026-08-04.

O site oficial da NGK e organizado por TIPO de vela (nao por codigo de
peca individual navegavel em listagem simples) - a busca por peca
especifica exige o formulario "Consulta Rapida" (por veiculo/motor/ano).
Por isso este primeiro lote traz as familias de produto, nao SKUs
individuais com codigo NGK (ex: BPR6ES) - isso fica para uma proxima
rodada, extraindo via consulta veiculo a veiculo ou catalogo tecnico
oficial em PDF/XML, se a NGK disponibilizar um.
"""

from importers.common import ImportedProduct, write_outputs

PRODUCTS = [
    (
        "NGK Vela de Ignição Múltiplos Eletrodos",
        "https://automotivo.ngkntk.com.br/produtos/linha-ngk/velas-de-ignicao_/?country=br&lang=pt",
    ),
    (
        "NGK Vela de Ignição Convencional",
        "https://automotivo.ngkntk.com.br/produtos/linha-ngk/categoria-ignicao/velas-convencionais/?country=br&lang=pt",
    ),
    (
        "NGK Vela de Ignição Green",
        "https://automotivo.ngkntk.com.br/produtos/linha-ngk/velas-de-ignicao_/?country=br&lang=pt",
    ),
]


def collect() -> list[ImportedProduct]:
    products = []
    for name, url in PRODUCTS:
        products.append(
            ImportedProduct(
                name=name,
                brand="NGK",
                manufacturer="NGK (Niterra do Brasil Ltda.)",
                category="Mecânica > Ignição > Velas",
                source_url=url,
                ncm_category_key="vela_ignicao",
                commercial_unit="UN",
                notes="Familia de produto, nao SKU individual - codigo de peca NGK (ex: BPR6ES) exige consulta por veiculo no site oficial.",
            )
        )
    return products


if __name__ == "__main__":
    items = collect()
    sql_path, csv_path = write_outputs(items, "ngk")
    print(f"{len(items)} produtos NGK -> {sql_path.name}, {csv_path.name}")
