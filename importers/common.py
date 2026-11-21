"""Utilitarios compartilhados por todo importador de fabricante.

Um importador especifico (ver importers/tramontina.py, premier_pet.py,
etc.) so precisa produzir uma lista de ImportedProduct a partir de uma
fonte real (pagina do fabricante, catalogo oficial em PDF, etc.) e chamar
`write_outputs()`. Toda validacao de GTIN, sugestao de NCM (sempre nao
confirmada) e geracao de SQL/CSV fica centralizada aqui.

Regras que todo importador deve seguir (vieram do pedido original):
- Nunca inventar produto, atributo, GTIN ou NCM.
- `source_url` e obrigatorio - de onde exatamente veio a informacao.
- GTIN so e gravado se a fonte informou (e validado por digito
  verificador antes de aceitar).
- NCM nunca e gravado como definitivo - so uma sugestao por categoria,
  sempre com `ncm_confirmed=False` na saida, para revisao humana.
"""

import csv
import uuid
from dataclasses import dataclass, field
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def new_product_id() -> str:
    return f"prod_{uuid.uuid4().hex[:12]}"


def validate_gtin(code: str) -> bool:
    """Valida o digito verificador de um GTIN-8/12/13/14 (algoritmo
    publico GS1: soma alternada 3/1 a partir do digito mais a direita do
    corpo, digito verificador = (10 - soma mod 10) mod 10)."""
    code = (code or "").strip()
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(d) for d in code]
    check = digits[-1]
    body = digits[:-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


# Sugestao de NCM por categoria - referencia da classificacao fiscal
# publica (NCM/TIPI), usada so como PONTO DE PARTIDA para revisao
# humana. NUNCA gravar como definitivo (ver ImportedProduct.ncm_suggested
# e a coluna ncm_confirmed nos arquivos gerados, sempre "NAO").
NCM_SUGGESTIONS: dict[str, tuple[str, str]] = {
    "racao_pet": ("23091000", "Alimentos para caes e gatos, acondicionados para venda a retalho"),
    "petisco_pet": ("23099090", "Outras preparacoes dos tipos utilizados na alimentacao de animais"),
    "acessorio_pet": ("42010000", "Artigos de correeiro ou de seleiro (coleiras, guias etc.)"),
    "ferramenta_manual": ("82055000", "Ferramentas manuais diversas (chaves, alicates, martelos)"),
    "ferramenta_eletrica": ("84679100", "Ferramentas com motor eletrico incorporado"),
    "parafuso_fixacao": ("73181500", "Parafusos e pinos ou pernos, de ferro fundido/ferro/aco"),
    "vela_ignicao": ("85111000", "Velas de ignicao"),
    "filtro_automotivo": ("84212300", "Aparelhos para filtrar oleos minerais em motores"),
    "amortecedor": ("87088000", "Amortecedores de suspensao para veiculos automoveis"),
    "pastilha_freio": ("87083090", "Freios e servo-freios; suas partes"),
    "oleo_lubrificante": ("27101932", "Oleos lubrificantes"),
    "rolamento": ("84821000", "Rolamentos de esferas"),
    "defensivo_agricola": ("38089199", "Inseticidas/defensivos agricolas, apresentados para venda a retalho"),
    "medicamento_veterinario": ("30049099", "Medicamentos para uso veterinario"),
    "pulverizador_agricola": ("84242000", "Aparelhos pulverizadores/aspersores agricolas"),
    "isca_pesca": ("95079000", "Outros artigos para pesca a linha (iscas, chumbadas etc.)"),
    "anzol": ("95071000", "Anzois, mesmo montados em linha"),
    "carretilha_molinete": ("95072000", "Carretilhas e molinetes de pesca"),
    "linha_pesca": ("95079000", "Outros artigos para pesca a linha"),
    "material_eletrico": ("85369090", "Aparelhos para interrupcao/protecao de circuitos eletricos"),
    "fio_cabo_eletrico": ("85444900", "Fios e cabos eletricos isolados diversos"),
    "conexao_hidraulica": ("39174090", "Acessorios para tubos, de plastico (conexoes hidraulicas)"),
    "registro_valvula": ("84819000", "Torneiras, valvulas e dispositivos semelhantes"),
    "broca": ("82075000", "Ferramentas intercambiaveis para furar (brocas)"),
    "serrote": ("82021000", "Serras manuais"),
    "disco_abrasivo": ("68042290", "Discos e rodas abrasivas para corte/desbaste"),
    "carrinho_mao": ("87168000", "Outros veiculos nao autopropulsionados (carrinhos de mao)"),
}


@dataclass
class ImportedProduct:
    name: str
    brand: str
    manufacturer: str
    category: str  # chave livre, ex: "Pet > Racao"
    source_url: str
    ncm_category_key: str | None = None  # chave em NCM_SUGGESTIONS, se aplicavel
    subcategory: str | None = None
    commercial_unit: str = "UN"
    description: str | None = None
    gtin: str | None = None
    cest: str | None = None
    notes: str | None = None

    def __post_init__(self):
        if not self.source_url:
            raise ValueError(f"Produto '{self.name}' sem source_url - nao pode ser importado.")
        if self.gtin and not validate_gtin(self.gtin):
            raise ValueError(f"GTIN '{self.gtin}' de '{self.name}' falhou na validacao de digito verificador.")

    @property
    def ncm_suggested(self) -> str | None:
        if self.ncm_category_key and self.ncm_category_key in NCM_SUGGESTIONS:
            return NCM_SUGGESTIONS[self.ncm_category_key][0]
        return None


def write_outputs(products: list[ImportedProduct], batch_name: str) -> Path:
    """
    Gera importers/output/<batch_name>.csv. Para gravar no banco, use:

        python -m scripts.import_manufacturer_products importers/output/<batch_name>.csv

    O NCM do CSV é só sugestão por categoria (coluna ncm_confirmed = NAO).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / f"{batch_name}.csv"

    csv_rows = []
    for p in products:
        csv_rows.append(
            {
                "id": new_product_id(),
                "name": p.name,
                "brand": p.brand,
                "manufacturer": p.manufacturer,
                "category": p.category,
                "subcategory": p.subcategory or "",
                "commercial_unit": p.commercial_unit,
                "description": p.description or "",
                "gtin": p.gtin or "",
                "ncm_suggested": p.ncm_suggested or "",
                "ncm_confirmed": "NAO",
                "cest": p.cest or "",
                "source_url": p.source_url,
                "notes": p.notes or "",
            }
        )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()) if csv_rows else [])
        writer.writeheader()
        writer.writerows(csv_rows)

    return csv_path
