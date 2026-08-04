# data/

Local padrão dos dois bancos SQLite (caminho configurável via
`PUBLIC_DATABASE_URL` / `COMMUNITY_DATABASE_URL` no `.env`):

- `public.sqlite3` — produtos, identificadores, regras fiscais e histórico
  de revisões. **Este é o arquivo distribuído** (ver rotas `/export/*`).
- `community.sqlite3` — usuários, chaves de API, sessões e fila de
  moderação. **Nunca é distribuído** — fica só na instância que o hospeda.

Nenhum dos dois arquivos `.sqlite3` é versionado no git (ver `.gitignore`).
