# data/

Local dos bancos SQLite (caminho configurável no `.env`, ver `.env.example`):

- `prodbr.sqlite3`: produtos, códigos de barras, categorias, NCM, regras
  fiscais, preços e histórico. É o arquivo público, baixável em
  `/api/download/prodbr.sqlite3`.
- `prodbr_community.sqlite3`: contribuidores e tokens. Nunca é distribuído.
- `public.sqlite3` e `community.sqlite3`: bancos da versão antiga. Se
  existirem, são copiados uma vez para os novos e depois ficam só de backup.

Nenhum arquivo `.sqlite3` é versionado no git (ver `.gitignore`).
