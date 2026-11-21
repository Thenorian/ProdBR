# Deploy em produção (VPS via Docker)

A cada `git push` na `main` (ou um "Re-run job" manual na aba Actions do
GitHub), o workflow `.github/workflows/deploy.yml`:

1. Builda a imagem Docker do projeto (`Dockerfile` na raiz) e publica em
   `ghcr.io/thenorian/prodbr`.
2. Conecta no servidor via SSH e substitui o container `prodbr` em
   execução pela nova imagem.

O banco (SQLite) fica num volume Docker nomeado (`prodbr_data`), então
sobrevive normalmente à troca de container a cada deploy.

## 1. Preparar o servidor (uma vez só)

Nada de systemd, venv ou usuário dedicado - só Docker. O usuário usado
pelo deploy (`deploy`, configurado no secret `SSH_USER`) já precisa estar
no grupo `docker` do servidor (sem isso, ele não consegue rodar
`docker run`/`docker pull` sem senha de root).

O container sobe conectado à rede Docker `nginx_default` (mesma rede do
`nginx-proxy-manager`), sem porta exposta direto no host - assim como
`ThenorianSite`. Configure o proxy reverso apontando pro container:

- No nginx-proxy-manager, crie um "Proxy Host" apontando pro endereço
  interno `prodbr:8000` (nome do container:porta exposta no
  `Dockerfile`), com o domínio/HTTPS desejado.

## 2. Tornar a imagem pública no GHCR (uma vez só, após o primeiro push)

Pacotes no GitHub Container Registry nascem **privados** mesmo em
repositórios públicos. Depois do primeiro deploy bem-sucedido:

`github.com/orgs/Thenorian/packages/container/prodbr/settings` → **Change
visibility** → **Public**.

Sem isso, o `docker pull` no servidor falha com `unauthorized` (o
projeto é de dados públicos, então não faz sentido manter a imagem
privada e ter que gerenciar credencial de registry pra isso).

## 3. Secrets no GitHub (Settings → Secrets and variables → Actions)

Já configurados (reaproveitados dos outros projetos no mesmo servidor):

| Secret            | Valor                                          |
|--------------------|------------------------------------------------|
| `SSH_HOST`         | IP ou domínio do servidor                       |
| `SSH_USER`         | `deploy`                                        |
| `SSH_PRIVATE_KEY`  | Chave privada já autorizada nesse usuário        |
| `SSH_PORT`         | Porta do SSH, só se não for a 22                |

O secret `DEPLOY_PATH` (usado pelo deploy antigo, baseado em systemd) não
é mais necessário e pode ser removido.

## 4. Variáveis de ambiente da aplicação (opcional)

Nenhuma delas é obrigatória - sem configurar nada, o app sobe com os
padrões abaixo (bases SQLite locais dentro do volume, sem anúncio):

| Variável            | Padrão (Dockerfile)                       | Pra que serve                                                  |
|---------------------|-------------------------------------------|----------------------------------------------------------------|
| `DB_PATH`           | `/app/data/prodbr.sqlite3`                | Banco público (produtos, NCM, fiscal, histórico).              |
| `COMMUNITY_DB_PATH` | `/app/data/prodbr_community.sqlite3`      | Contribuidores e tokens. Nunca é baixado pelo público.         |
| `LEGACY_PUBLIC_DB_PATH` / `LEGACY_COMMUNITY_DB_PATH` | `/app/data/public.sqlite3` / `community.sqlite3` | Bancos da versão antiga, copiados uma vez para os novos. |
| `PUBLIC_URL`          | *(vazio = lido do acesso)*                | Endereço público usado no sitemap.                             |
| `ADS_SNIPPET`       | *(vazio = sem anúncio)*                   | HTML/JS do provedor de anúncios (ex: AdSense).                 |

Variáveis da versão antiga (`PUBLIC_DATABASE_URL`, `RATE_LIMIT_*`,
`REPUTATION_*`, `SESSION_TTL_HOURS` etc.) não são mais usadas e podem
ser removidas do `~/prodbr.env`.

Pra customizar alguma, crie `~/prodbr.env` no servidor (usuário
`deploy`), no formato `VARIAVEL=valor` (uma por linha, sem aspas/export -
mesmo formato de um `.env`). O workflow detecta o arquivo sozinho no
próximo deploy e passa pro container via `--env-file`. Esse arquivo é só
local ao servidor - o deploy nunca sobrescreve nem apaga ele.

## 5. Backup automático

Todo deploy para o container, faz um `.tar.gz` do volume `prodbr_data`
inteiro (bancos público e da comunidade) em `~/prodbr_backups/` no servidor
e só depois sobe a versão nova. Ficam os 10 mais recentes. Para voltar um
backup: pare o container, apague o conteúdo do volume e extraia o arquivo nele.

## 6. Rodar o deploy

- **Automático:** todo `git push` na `main` dispara o workflow.
- **Manual ("Re-run job"):** aba **Actions** do GitHub → workflow
  **Deploy** → **Run workflow** (ou, num run que já existir, o botão
  **Re-run all jobs**) - útil se o deploy falhou por uma instabilidade
  passageira do servidor e não precisa de commit novo pra tentar de novo.
