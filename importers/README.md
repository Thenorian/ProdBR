# Importadores por fabricante

Pipeline reproduzível para popular o ProdBR com produtos reais, um
fabricante por vez — em vez de uma coleta manual única. Quando um
fabricante lançar produtos novos, basta rodar o importador dele de novo.

## Cobertura atual (honesta)

Esta primeira rodada trouxe **36 produtos reais**, coletados manualmente
navegando os sites oficiais dos fabricantes (PremieR Pet: 21, Tramontina:
12, NGK: 3 — famílias de produto, não códigos de peça individuais).

Isso está **bem abaixo** da meta de 2.000-20.000 produtos, de propósito:
não existe hoje uma forma confiável de extrair em massa GTIN/NCM
verificados de dezenas de fabricantes a partir de navegação manual de
site — isso violaria a regra "nunca inventar produto ou atributo". Ver
"Como escalar" abaixo para o caminho real até esse volume.

Nenhum GTIN foi gravado nesta rodada: nenhuma das páginas de fabricante
visitadas publica código de barras por SKU (comum em sites voltados ao
consumidor final — GTIN normalmente só aparece em catálogos B2B/EDI de
distribuidor). Isso é o comportamento correto, não uma falha: a regra é
"se a fonte não informou, deixar vazio", nunca inventar.

## Como rodar

```bash
# Um fabricante:
python -m importers.premier_pet
python -m importers.tramontina
python -m importers.ngk

# Todos de uma vez (gera tambem um lote combinado all_manufacturers.*):
python -m importers.run_all
```

Cada execução gera `importers/output/<nome>.sql` e `.csv`. O SQL cobre
`products` e `product_identifiers` (só quando há GTIN validado). **NCM
nunca é gravado como confirmado** — é sempre uma sugestão por categoria
(`app/importers/common.py::NCM_SUGGESTIONS`), e o CSV tem uma coluna
`ncm_confirmed` sempre `NAO` para deixar isso explícito a quem for revisar
antes de aplicar em produção.

## Como funciona / regras que todo importador segue

Ver `importers/common.py` para a implementação. Resumo das regras (vieram
do pedido original e devem valer para qualquer importador novo):

- **Fonte obrigatória**: todo `ImportedProduct` exige `source_url` - de
  onde exatamente veio o nome/dado. Sem isso, o produto não é aceito
  (`ImportedProduct.__post_init__` levanta erro).
- **GTIN nunca inventado**: só é gravado se a fonte mostrou o código, e
  passa por validação de dígito verificador (`validate_gtin`) antes de
  aceitar - GTIN inválido também é rejeitado.
- **NCM nunca definitivo**: `ncm_category_key` aponta para uma sugestão
  por categoria (não por produto individual) em `NCM_SUGGESTIONS`. Se a
  categoria não tem uma entrada mapeada (porque a classificação real
  exigiria mais confiança do que uma tabela genérica permite), o produto
  entra com NCM vazio e um aviso `-- ATENCAO` no SQL, para alguém
  preencher manualmente.
- **Sem marketplace**: as fontes usadas são sempre o site oficial do
  fabricante (ou a loja oficial dele, como a Tramontina Store) - nunca
  Mercado Livre, Shopee, OLX, revendedores terceiros ou blogs.
- **Sem preço/custo/fornecedor**: mesmo quando a página fonte mostra
  preço (ex: loja oficial Tramontina), esse dado é ignorado - não faz
  parte do schema do ProdBR.

## Como adicionar um novo fabricante

Cada importador é só um módulo Python com uma função `collect() -> list[ImportedProduct]`.
Copie `importers/tramontina.py` como ponto de partida:

```python
from importers.common import ImportedProduct, write_outputs

def collect() -> list[ImportedProduct]:
    return [
        ImportedProduct(
            name="...",              # nome exato da fonte, normalizado
            brand="...",
            manufacturer="...",
            category="Vertical > Categoria",
            source_url="https://...",# pagina exata de onde veio
            ncm_category_key="...",  # chave em NCM_SUGGESTIONS, ou None
            gtin="...",              # só se a fonte mostrou
        ),
    ]

if __name__ == "__main__":
    items = collect()
    write_outputs(items, "nome_do_fabricante")
```

Depois adicione o módulo em `importers/run_all.py` (lista `IMPORTERS`).

## Como escalar de 36 para milhares

Navegação manual de site não escala. Os caminhos reais, em ordem de
confiabilidade:

1. **Catálogo B2B do distribuidor/fabricante** (XML, EDI, planilha) - é
   assim que ERPs do setor normalmente conseguem GTIN/NCM em volume, via
   relacionamento comercial. Um importador que lê esse formato é o
   próximo passo natural (mesmo padrão `collect()`, só trocando a fonte).
2. **Catálogo técnico oficial em PDF/app** (ex: o app "NGK|NTK -
   Catálogo" achado na busca) - alguns fabricantes de autopeças
   disponibilizam isso, geralmente por código de peça x aplicação
   veicular, não por listagem simples.
3. **Mais rodadas de coleta manual**, uma categoria/linha por vez, como
   esta primeira - lento, mas 100% verificável.

## Achado desta rodada

A coluna `products.ncm` era `NOT NULL` no schema - um produto importado
sem NCM mapeado quebrava a carga do SQL. Corrigido em
`app/models_public.py` (coluna nullable no banco; a API continua
exigindo NCM em `POST /products`/`PUT /products/{id}` normalmente - só a
via de importação em lote pode deixar pendente).
