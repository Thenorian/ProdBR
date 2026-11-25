# ProdBR

Base aberta e colaborativa de produtos brasileiros, feita para preencher o
cadastro de produtos em ERPs. Pelo código de barras vem tudo de uma vez:
nome, marca, fabricante, código do fabricante, NCM, CEST, categoria, preço
médio e regras fiscais (ICMS, IPI, PIS, COFINS, CBS, IBS) por UF e regime
tributário.

Código sob AGPLv3 (`LICENSE`). Dados sob ODbL v1.0 (`DATA_LICENSE`).

## Como está organizado

São duas partes separadas, que no servidor rodam juntas (`server.py`):

| Pasta       | O que é                                                                 |
|-------------|-------------------------------------------------------------------------|
| `api/`      | A API pública, só JSON, para ERPs. Funciona sozinha, sem o site.        |
| `website/`  | O site, para pessoas. Busca os dados na própria API pública, por HTTP. |
| `database/` | Acesso ao banco (SQLite), no mesmo padrão do MyMenu: SQL direto.        |
| `docs/`     | `database.sql` e `community.sql`: o schema completo e atual.           |
| `util/`     | Leitura da tabela de NCM e validações (código de barras, NCM, UF).      |
| `reference_data/ncm/` | Tabela oficial de NCM (JSON do Portal Único Siscomex).        |
| `scripts/`  | Importações feitas à mão (NCM e produtos dos fabricantes).              |
| `importers/`| Coleta de produtos nos sites dos fabricantes, gera CSV.                 |

Endereços no servidor:

- `/` site
- `/api/v1` API (documentação interativa em `/api/v1/docs`)
- `/sitemap.xml`, `/robots.txt` e `/llms.txt` para buscadores e IAs

## Versões da API

A versão faz parte do endereço (`/api/v1`). Uma versão publicada nunca muda
de um jeito que quebre quem já usa:

- Pode entrar na v1: campo novo na resposta, rota nova, filtro novo opcional.
- Não pode entrar na v1: tirar ou renomear campo, mudar formato ou tipo,
  tornar obrigatório algo que era opcional. Isso vira uma `/api/v2`, montada
  ao lado em `server.py`, e a v1 continua no ar até ninguém mais usar.

As rotas da API antiga, sem versão (`/products`, `/identifiers`, `/ncm/{código}`),
continuam respondendo no formato antigo só para sistemas já instalados
(OS-Mechanical nos clientes e versões antigas do Simple ERP). Ficam em
`api/legacy_v0.py`, não recebem nada novo e podem ser apagadas quando ninguém
mais usar.

## Rodar localmente

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server:app --reload
```

Só a API, sem o site: `uvicorn api.main:app`.

Testes: `.venv/bin/python -m pytest`

## Banco de dados

Dois arquivos SQLite em `data/`:

- `prodbr.sqlite3`: produtos, códigos de barras, categorias, NCM, regras
  fiscais, preços e histórico. É público e pode ser baixado inteiro em
  `/api/v1/download/prodbr.sqlite3`.
- `prodbr_community.sqlite3`: contribuidores, tokens e a fila de votação. Nunca sai do servidor.

Toda vez que o app inicia (`database/setup.py`), sem nenhum passo manual:

1. Cria as tabelas e colunas que faltam, comparando com `docs/database.sql`
   e `docs/community.sql`. Para mudar o banco, edite esses arquivos.
2. Na primeira vez, copia os dados da versão antiga (`public.sqlite3` e
   `community.sqlite3`), mantendo os ids dos produtos e as chaves de API.
3. Importa a tabela de NCM mais nova de `reference_data/ncm/`, se ainda
   não foi importada.

## Dados oficiais, atualizados sozinhos todo dia

O app baixa uma vez por dia, sem cron e sem passo manual (`util/daily_update.py`):

- a tabela NCM vigente do Portal Único Siscomex (JSON público);
- o IPI da TIPI (Receita Federal) e o II da TEC (MDIC/Gecex);
- a tabela do IBPT de cada UF (Lei 12.741/2012), baixada em JSON de um espelho
  público (`IBPT_SOURCE_URL` no `.env` para trocar). Só a versão vigente fica no
  banco, e ela só é regravada quando a versão muda.

O IPI e o II viram uma regra fiscal nacional "Oficial: ..." por NCM. Quando a
alíquota muda, a regra antiga é encerrada e nasce outra, então o histórico das
alíquotas fica guardado. Regras da comunidade nunca são alteradas. NCM que sai
da tabela fica com `in_force = 0`, nunca é apagado.

A carga aproximada do IBPT sai em `GET /api/v1/ibpt/{NCM}?uf=SP` e no campo
`ibpt` do produto e do NCM quando a consulta tem `?uf=`. Ela fica fora do
arquivo de download da base, porque é quase 10 vezes maior que o resto e o
próprio IBPT publica.

Para rodar na hora: `python -m scripts.update_official_data`.
Para desligar: `NCM_AUTO_UPDATE=false`.

A tabela em `reference_data/ncm/` é só reserva: entra na primeira subida se o
site do governo estiver fora do ar.

## Como o NCM do produto é decidido

1. Se o produto tem NCM próprio, vale o dele.
2. Se não tem, vale o da categoria. Se a categoria também não tem, o da
   categoria acima, até a raiz. O mesmo vale para CEST e origem.
3. As regras fiscais são as do NCM que valer, filtradas por UF e regime.
4. `fiscal_summary` junta as regras campo a campo (ICMS da UF + IPI e II
   oficiais) num quadro só. É o campo que o ERP deve usar.

O produto pode ficar sem NCM, ou com um NCM fora da tabela oficial: é uma
Wiki. A API avisa com `"in_official_table": false`.

## Contribuir

O acesso é como no Git: um nome de usuário e um token, sem e-mail e senha.

```bash
curl -X POST https://SEU-DOMINIO/api/v1/contributors -H 'Content-Type: application/json' \
     -d '{"username": "meu_nome"}'
```

O token volta uma única vez. Use no cabeçalho `X-API-Key` para cadastrar
ou alterar. Toda alteração fica no histórico público com o seu nome.
A reputação aparece só no site (página Sobre), nunca na API.

### Empresas

Perfil de empresa no estilo Wikipedia: qualquer pessoa cadastra e completa
(`POST`/`PUT /api/v1/companies`, ou as páginas `/empresas` e `/empresa/{CNPJ}`
do site). Só o nome é obrigatório. A empresa tem três listas, e cada lista
enviada substitui a anterior inteira:

- `establishments`: cada CNPJ (matriz e filiais) com razão social, inscrição
  estadual e endereço separado como na NF-e (CEP, logradouro, número,
  complemento, bairro, cidade, código IBGE do município e UF). O CNPJ é
  conferido (numérico ou alfanumérico) e não se repete. No site, o CEP
  preenche o endereço pelo ViaCEP.
- `phones`: telefones com a descrição de cada um (SAC, Suporte...).
- `brands`: marcas da empresa.

As rotas da empresa usam qualquer CNPJ dela: `GET /api/v1/companies/60409075000152`
(sem a barra; pontos e hífen são aceitos). Empresa sem CNPJ usa o id. Os campos
da primeira versão (`cnpj`, `legal_name`, `address`, `city`, `uf`, `phone`)
continuam na resposta, vindos da matriz e do primeiro telefone.

Os produtos aparecem no perfil (`GET /api/v1/companies/{CNPJ}/products`) quando:

1. o produto aponta para a empresa (`company_id`, que aceita o CNPJ), ou, se não aponta,
2. a marca do produto é uma das marcas da empresa, ou
3. o fabricante do produto tem o nome da empresa.

O produto traz o campo `company` com `linked_by` dizendo qual dos três foi.
Cadastrar e alterar empresa também passa pela fila de votação.

### Fila de votação

Quem acabou de se cadastrar é Iniciante. As alterações dele não gravam
direto: a API responde `202` com `"status": "pending"` e a alteração vai para
a fila (`GET /api/v1/pending-changes`, ou a página `/fila` do site).

- Vota qualquer contribuidor com conta de mais de 24 horas, menos o autor:
  `POST /api/v1/pending-changes/{id}/votes` com `{"vote": 1}` (a favor),
  `-1` (contra) ou `0` (retira o voto).
- Saldo +3 aplica a alteração em nome do autor. Saldo -3 descarta.
- Cada voto a favor dá 1 ponto de reputação ao autor, cada voto contra tira 1.
  Cada campo aplicado na base também vale 1 ponto.
- Com 50 pontos a pessoa vira Editor e passa a gravar direto.
- Confiável (ERPs e bots) grava direto. Moderador decide uma alteração da
  fila sozinho, com um voto. Quem já existia antes da votação ficou confiável.

```bash
docker exec prodbr python -m scripts.contributor_permission kainan moderador sim
docker exec prodbr python -m scripts.contributor_permission erp_x confiavel sim
```

As rotas antigas, sem `/api/v1`, não conhecem a fila: recusam Iniciante com `403`.

## Produtos dos fabricantes

```bash
python -m importers.run_all                                                   # coleta e gera o CSV
python -m scripts.import_manufacturer_products importers/output/all_manufacturers.csv  # grava no banco
```

No servidor: `docker exec prodbr python -m scripts.import_manufacturer_products importers/output/all_manufacturers.csv`.
Pode rodar mais de uma vez: o que já existe é pulado.

## Deploy

Ver `deploy/README.md`.
