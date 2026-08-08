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

| Variável                  | Padrão                                          | Pra que serve                                                        |
|----------------------------|--------------------------------------------------|-----------------------------------------------------------------------|
| `PUBLIC_DATABASE_URL`      | `sqlite:////app/data/public.sqlite3` (Dockerfile) | Base pública (produtos/NCM/fiscal/revisões) - a que é exportável.     |
| `COMMUNITY_DATABASE_URL`   | `sqlite:////app/data/community.sqlite3` (Dockerfile) | Base de comunidade (usuários/chaves/moderação) - nunca exportada. |
| `MAX_PAGE_SIZE`            | `10`                                              | Limite de itens por página em buscas/listagens.                      |
| `RATE_LIMIT_READ`          | `60/minute`                                       | Limite de requisições de leitura por IP.                              |
| `RATE_LIMIT_WRITE`         | `10/minute`                                       | Limite de requisições de escrita por IP.                              |
| `AUTO_APPROVE_REPUTATION`  | `20`                                              | Reputação mínima pra uma contribuição ser aplicada direto.            |
| `REPUTATION_PER_CREATE`    | `3`                                               | Reputação ganha ao criar algo (aplicado ou aprovado).                 |
| `REPUTATION_PER_UPDATE`    | `1`                                               | Reputação ganha ao editar algo.                                       |
| `REPUTATION_PENALTY_REJECT`| `2`                                               | Reputação perdida quando uma contribuição é rejeitada.                |
| `SESSION_TTL_HOURS`        | `336` (14 dias)                                   | Validade do token de sessão (login via usuário/senha).                |
| `ADS_SNIPPET`              | *(vazio = sem anúncio)*                           | HTML/JS do provedor de anúncios da sua instância (ex: AdSense).       |

Pra customizar alguma, crie `~/prodbr.env` no servidor (usuário
`deploy`), no formato `VARIAVEL=valor` (uma por linha, sem aspas/export -
mesmo formato de um `.env`). O workflow detecta o arquivo sozinho no
próximo deploy e passa pro container via `--env-file`. Esse arquivo é só
local ao servidor - o deploy nunca sobrescreve nem apaga ele.

## 5. Rodar o deploy

- **Automático:** todo `git push` na `main` dispara o workflow.
- **Manual ("Re-run job"):** aba **Actions** do GitHub → workflow
  **Deploy** → **Run workflow** (ou, num run que já existir, o botão
  **Re-run all jobs**) - útil se o deploy falhou por uma instabilidade
  passageira do servidor e não precisa de commit novo pra tentar de novo.
