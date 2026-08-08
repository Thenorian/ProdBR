# ProdBR

Base pública e colaborativa de produtos brasileiros — pensada nos moldes da
Wikipédia ou do ViaCEP: a Thenorian é a mantenedora inicial, mas qualquer
pessoa pode consultar, contribuir e até hospedar sua própria instância
(self-hosted). O objetivo não é só oferecer uma API, e sim construir a
maior base aberta de identificação de produtos do Brasil — a API é apenas
uma das formas de acessá-la.

Dado um código de barras, GTIN ou outro identificador, a base devolve a
identificação do produto (nome, marca, NCM/CEST, categoria...) e, à parte,
as regras fiscais de referência (ICMS + FCP + MVA-ST, IPI, PIS, COFINS,
II, CBS/IBS) por país, UF e vigência. **Não é salvo preço, custo ou
fornecedor.**

## Arquitetura

### Produto, NCM e regras fiscais são três entidades separadas

A legislação tributária muda com frequência e varia por estado (e por
país, no caso do Mercosul) — o cadastro do produto não pode ficar refém
disso. Por isso:

- **Product**: identificação (`prod_xxxxxxxxxxxx`, nome, marca, NCM/CEST
  "atuais", categoria, fabricante, fonte). Não guarda alíquota nenhuma.
- **NcmClassification**: o NCM em si — descrição oficial (TIPI/Mercosul),
  capítulo, unidade estatística — consultável (`/ncm/{codigo}`) mesmo sem
  nenhum produto usando essa classificação. É o catálogo de apoio; o
  produto continua sendo a entidade principal do projeto.
- **FiscalRule**: alíquotas chaveadas por **NCM + CEST + país + UF +
  vigência**, não pelo produto. Dois produtos com o mesmo NCM
  compartilham a mesma regra automaticamente — é a lei que tributa a
  classificação fiscal, não o SKU específico. `uf=null` é a regra
  nacional/default, usada quando não há regra específica para o estado
  consultado.

### Escopo Mercosul

O NCM (Nomenclatura Comum do Mercosul) é compartilhado por Brasil,
Argentina, Paraguai e Uruguai — por isso `NcmClassification` não tem
campo de país: o código e a descrição são os mesmos no bloco todo. Já a
tributação sobre essa classificação é decidida por cada país-membro, e
por isso toda `FiscalRule` tem um campo `country` (ISO 3166-1 alpha-2,
padrão `"BR"`). Hoje só há dados fiscais do Brasil — o schema já está
pronto para os demais membros sem precisar de migração.

### Tributos cobertos (Brasil)

Além de ICMS/IPI/PIS/COFINS, `FiscalRule` também registra: **FCP** (Fundo
de Combate à Pobreza, adicional estadual do ICMS), **MVA** do ICMS-ST,
**II** (Imposto de Importação — alíquota-base é a TEC do Mercosul), e
**CBS/IBS** (Reforma Tributária, EC 132/2023). Um campo livre `notes`
cobre particularidades do regime (isenção, monofásico, redução de base de
cálculo etc.) sem precisar de um campo dedicado para cada caso.

### Identificadores flexíveis

Um produto pode ter vários identificadores (GTIN-8/12/13/14, UPC, EAN,
código do fabricante, outros) — nenhum deles é a chave primária. A chave
interna do produto é gerada pelo sistema (`prod_...`), o que permite
cadastrar produtos que ainda não têm código de barras nenhum.

### Toda informação tem fonte

`Product.source` e `FiscalRule.source` registram de onde veio o dado
(Receita Federal, GS1 Brasil, contribuição da comunidade, documentação do
fabricante, portal oficial, etc.) — para rastreabilidade e auditoria.

### Nada de arquivos binários

O banco fica só com dados estruturados/textuais — sem imagens, PDFs ou
qualquer binário. Se um dia for necessário associar imagens, serão só
referências (URL), nunca o arquivo em si.

### Histórico de revisões, ao estilo Git

Toda alteração vira uma ou mais linhas em `Revision` — uma por campo
alterado, com usuário responsável, data, valor anterior, novo valor e o
**motivo da alteração** (campo obrigatório em toda escrita). Consultável
via `/revisions` e `/products/{id}/revisions`.

### Sistema comunitário separado da base pública

Usuários, chaves de API, sessões e fila de moderação vivem num banco **à
parte** (`data/community.sqlite3`) que nunca é distribuído. Quando alguém
baixa a base publica (`/export/*`), recebe só produtos, identificadores,
regras fiscais e revisões — nenhum dado de autenticação ou moderação.

### Reputação e moderação

Todo cadastro/edição exige conta (chave de API pessoal). Contribuições de
usuários com reputação abaixo do limite (`AUTO_APPROVE_REPUTATION`, padrão
20) entram numa fila de moderação (`PendingChange`) em vez de aplicar
direto; moderadores/admins aprovam ou rejeitam via `/moderation/*`.
Reputação sobe a cada contribuição aplicada (direta ou aprovada) e cai um
pouco a cada rejeição.

## Licenciamento

- **Software**: [AGPLv3](LICENSE) — se alguém rodar uma instância
  modificada como serviço web público, é obrigado a disponibilizar o
  código-fonte das modificações.
- **Dados**: [ODbL v1.0](DATA_LICENSE) — licença específica para bancos de
  dados colaborativos (mesma usada pelo OpenStreetMap).

## Rodando localmente

```bash
python -m venv venv
./venv/Scripts/activate        # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`. Página de pesquisa manual em `/`,
classificações NCM em `/view/ncm`, página institucional (o que é o
projeto, licenciamento, ranking de contribuidores) em `/about`,
documentação interativa (OpenAPI/Swagger) em `/docs`.

### Criar uma conta e contribuir

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"seu_user","email":"voce@example.com","password":"senha-forte"}'
```

A resposta inclui uma chave de API pessoal (`X-API-Key`), mostrada uma
única vez — é ela que autentica os cadastros/edições.

### Promover o primeiro moderador (bootstrap)

Contas novas nascem com papel `member`. Para promover alguém a moderador
ou admin (necessário para revisar a fila de moderação):

```bash
python -m scripts.promote_user <username> moderator
```

### Popular com dados de exemplo (opcional)

```bash
python -m scripts.seed_example
```

## Anúncios (opcional)

O projeto é open source e precisa se manter. Cada instância pode exibir
seus próprios anúncios sem precisar mexer no código nem em nenhum painel:
defina `ADS_SNIPPET` no `.env` com o HTML/JS do provedor escolhido (ex:
Google AdSense). Se a variável estiver vazia (padrão), nenhum anúncio é
exibido. O mesmo snippet aparece em alguns espaços fixos e claramente
rotulados ("Publicidade") - rodapé (todas as páginas), início da home
(depois da busca, antes das listagens) e fim da ficha de produto/NCM
(depois do conteúdo) - sempre fora do fluxo de leitura, nunca como popup,
interstitial ou entre parágrafos de conteúdo.

## Baixar a base pública

`GET /export/sqlite`, `/export/sql` ou `/export/csv` — sempre só com
produtos/identificadores/classificações NCM/regras fiscais/revisões,
nunca com dados de comunidade. O arquivo SQLite é o próprio banco em uso,
então também dá para copiar `data/public.sqlite3` diretamente.

## Regras de negócio

- **Leitura é pública**, sem autenticação: busca, detalhe, regras fiscais,
  histórico de revisões, perfil de contribuidor.
- **Limite de 10 itens por requisição** (`MAX_PAGE_SIZE`) em toda busca ou
  listagem, para evitar bots varrendo a base inteira de uma vez.
- **Rate limiting por IP** (`RATE_LIMIT_READ`/`RATE_LIMIT_WRITE`, formato
  slowapi) como proteção contra bots/DDoS. Acima do limite: `429`.
- **Escrita exige conta** (chave de API ou sessão de login) e um motivo
  (`reason`) obrigatório em todo create/update.
- **Reputação decide se aplica na hora ou vai para moderação** — ver acima.

## Rotas principais

| Método | Rota                              | Auth  | Descrição                                          |
|--------|-------------------------------------|-------|-----------------------------------------------------|
| GET    | `/products`                         | não   | Busca por `identifier`, `ncm`, `category` ou `q`     |
| GET    | `/products/{id}`                    | não   | Detalhe de um produto                                |
| POST   | `/products`                         | conta | Cria um produto                                      |
| PUT    | `/products/{id}`                     | conta | Atualiza campos de um produto                        |
| POST   | `/identifiers`                      | conta | Anexa um identificador a um produto                  |
| PUT    | `/identifiers/{id}`                  | conta | Corrige tipo/valor de um identificador existente     |
| DELETE | `/identifiers/{id}`                  | conta | Remove um identificador                              |
| GET    | `/fiscal-rules?ncm=&uf=&country=&date=` | não | Resolve a regra fiscal vigente mais específica (país padrão `BR`) |
| GET    | `/fiscal-rules/history?ncm=&country=` | não | Todas as regras já cadastradas para um NCM           |
| GET    | `/products/{id}/fiscal`             | não   | Regra fiscal resolvida a partir do NCM do produto    |
| POST   | `/fiscal-rules`                      | conta | Cria uma regra fiscal                                |
| PUT    | `/fiscal-rules/{id}`                 | conta | Atualiza uma regra fiscal                            |
| GET    | `/ncm?q=`                            | não   | Busca classificações NCM por código ou descrição      |
| GET    | `/ncm/{codigo}`                      | não   | Ficha do NCM: descrição + regras fiscais + nº de produtos |
| POST   | `/ncm`                               | conta | Cadastra uma classificação NCM                        |
| PUT    | `/ncm/{codigo}`                      | conta | Atualiza uma classificação NCM                        |
| GET    | `/revisions`                        | não   | Histórico global de alterações                       |
| GET    | `/products/{id}/revisions`           | não   | Histórico de um produto                              |
| GET    | `/users`                             | não   | Ranking público de contribuidores por reputação       |
| GET    | `/users/{username}`                 | não   | Perfil público (reputação, papel — sem e-mail)        |
| POST   | `/auth/register`                    | não   | Cria conta + chave de API pessoal                     |
| POST   | `/auth/login`                       | não   | Login (retorna token de sessão)                       |
| GET    | `/moderation/queue`                  | mod   | Fila de contribuições pendentes                       |
| POST   | `/moderation/{id}/approve`           | mod   | Aprova e aplica uma contribuição pendente             |
| POST   | `/moderation/{id}/reject`            | mod   | Rejeita uma contribuição pendente                     |
| GET    | `/export/{sqlite,sql,csv}`          | não   | Baixa a base pública completa                         |

Tipagem completa de cada rota em `/docs` (Swagger) e `/redoc`.

## Deploy em produção

Deploy automático via GitHub Actions a cada push na `main` (ou disparo
manual/"Re-run job" na aba Actions) — conecta por SSH num VPS, atualiza o
código e reinicia o serviço. Passo a passo completo (setup do servidor,
systemd, secrets do GitHub, variáveis de ambiente) em
[`deploy/README.md`](deploy/README.md).

## Testes

```bash
pytest
```

## Stack

FastAPI + SQLAlchemy, duas bases SQLite (pública e de comunidade — ver
"Arquitetura" acima), [slowapi](https://github.com/laurentS/slowapi) para
rate limiting, hashing de senha via `hashlib.pbkdf2_hmac` (stdlib, sem
dependência extra de compilação). Documentação OpenAPI gerada
automaticamente pelo FastAPI.
