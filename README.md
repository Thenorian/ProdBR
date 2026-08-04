# ProdBR

Cadastro público e colaborativo de produtos brasileiros. Dado um código de
barras, NCM ou outro identificador único, a API devolve as informações
fiscais genéricas do produto (NCM, CEST, unidade, alíquotas de referência
de ICMS, IPI, PIS, COFINS, CBS/IBS).

**Não é salvo preço, custo ou fornecedor** — só o que identifica o produto
e o que ajuda a preencher impostos.

A ideia é unificar um cenário hoje espalhado e confuso: qualquer sistema
(inclusive de terceiros) pode consultar e contribuir com cadastros, e a
base inteira pode ser baixada e usada por qualquer pessoa — como baixar uma
Wikipédia inteira de produtos.

## Licença

[GNU GPL v3.0](LICENSE). Qualquer pessoa pode rodar sua própria instância
(self-hosted) deste software, sem restrição.

## Rodando localmente

```bash
python -m venv venv
./venv/Scripts/activate        # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`. A página de pesquisa manual (estilo
Wikipédia) fica na raiz (`/`), e a documentação interativa (OpenAPI/Swagger)
em `/docs`.

### Criar uma chave de API (para cadastrar/editar produtos)

Consultar é público e não precisa de chave. Criar ou editar produtos exige
uma chave de API, gerada por linha de comando:

```bash
python -m scripts.create_api_key "nome de quem vai usar a chave"
```

A chave é impressa uma única vez no terminal — o banco guarda só o hash
(sha256), então não tem como recuperá-la depois, só gerar uma nova.

### Popular com dados de exemplo (opcional)

```bash
python -m scripts.seed_example
```

## Baixar o banco de dados

O banco é um único arquivo SQLite (`prodbr.sqlite3`, caminho configurável
via `DATABASE_URL`). Isso é proposital: qualquer pessoa pode copiar esse
arquivo e ter a base completa, sem precisar rodar um servidor de banco à
parte, exatamente como baixar um dump inteiro de uma wiki.

## Regras de negócio

- **API pública**: qualquer pessoa pode pesquisar por código de barras,
  NCM ou outro identificador único, sem autenticação.
- **Limite de 10 itens por requisição** (`MAX_PAGE_SIZE`), para evitar
  bots varrendo a base inteira de uma vez. Requisições pedindo mais que
  isso são limitadas ao teto silenciosamente; use `offset` para paginar.
- **Proteção contra bots/DDoS**: rate limiting por IP (`RATE_LIMIT_READ`
  e `RATE_LIMIT_WRITE`, formato slowapi, ex. `60/minute`). Requisições
  acima do limite recebem `429 Too Many Requests`.
- **Edição exige chave de API** (header `X-API-Key`). Qualquer alteração
  fica registrada, com autor (chave) e diff, como um "git log" público —
  ver `GET /products/{id}/changelog` e `GET /changelog`.

## Rotas principais

| Método | Rota                          | Auth | Descrição                                   |
|--------|--------------------------------|------|----------------------------------------------|
| GET    | `/products`                    | não  | Busca por `barcode`, `ncm` ou `q` (texto)     |
| GET    | `/products/{id}`               | não  | Detalhe de um produto                         |
| POST   | `/products`                    | sim  | Cria um produto                               |
| PUT    | `/products/{id}`                | sim  | Atualiza campos de um produto                 |
| GET    | `/products/{id}/changelog`     | não  | Histórico de alterações do produto            |
| GET    | `/changelog`                   | não  | Últimas alterações em qualquer produto        |

A tipagem completa de cada campo (request/response) está documentada
automaticamente em `/docs` (Swagger) e `/redoc`.

## Testes

```bash
pytest
```

## Stack

FastAPI + SQLAlchemy + SQLite, com [slowapi](https://github.com/laurentS/slowapi)
para rate limiting. Documentação OpenAPI gerada automaticamente pelo
FastAPI, servindo tanto como docs pública quanto como fonte de tipagem
das rotas.
