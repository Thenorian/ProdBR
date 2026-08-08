# Deploy em produção (VPS via SSH)

Duas coisas são configuradas **uma vez só, na mão, no servidor**: o
processo (`systemd`) e o arquivo `.env` com a configuração da instância.
Depois disso, todo `git push` na `main` (ou um "Re-run job" manual na aba
Actions do GitHub) atualiza o servidor sozinho.

## 1. Preparar o servidor (uma vez só)

```bash
# No servidor, como root ou com sudo:
adduser --disabled-password --gecos "" prodbr
mkdir -p /opt/prodbr
chown prodbr:prodbr /opt/prodbr

su - prodbr
git clone https://github.com/<seu-usuario>/ProdBR.git /opt/prodbr
cd /opt/prodbr
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite o .env com os valores da sua instancia (ver secao 3 abaixo)
exit  # volta a ser root/sudo
```

Copie o serviço systemd (ajuste `User`/`WorkingDirectory` em
`deploy/prodbr.service` se seu caminho/usuário for diferente de
`prodbr`/`/opt/prodbr`):

```bash
cp /opt/prodbr/deploy/prodbr.service /etc/systemd/system/prodbr.service
systemctl daemon-reload
systemctl enable --now prodbr
systemctl status prodbr
```

A API sobe em `127.0.0.1:8000` (não exposta direto à internet de
propósito). Configure um reverse proxy com HTTPS na frente (nginx ou
Caddy) apontando pro `127.0.0.1:8000` — isso é independente do deploy
automático e só precisa ser feito uma vez.

### Permitir que o deploy reinicie o serviço sem senha

O workflow conecta como um usuário via SSH e roda `sudo systemctl
restart prodbr`. Pra isso não pedir senha, adicione uma regra **restrita**
(só esse comando, não sudo total) com `visudo`:

```
# /etc/sudoers.d/prodbr-deploy
prodbr ALL=(root) NOPASSWD: /usr/bin/systemctl restart prodbr, /usr/bin/systemctl status prodbr
```

### Gerar a chave SSH que o GitHub vai usar

```bash
# Na sua máquina (não no servidor), gere um par de chaves dedicado ao deploy:
ssh-keygen -t ed25519 -C "github-actions-deploy" -f deploy_key -N ""

# Copie a chave PUBLICA pro servidor (usuario prodbr):
ssh-copy-id -i deploy_key.pub prodbr@SEU_SERVIDOR

# A chave PRIVADA (deploy_key, sem extensao) vai virar o secret
# SSH_PRIVATE_KEY no GitHub - conteudo completo do arquivo, incluindo as
# linhas "-----BEGIN ... KEY-----" e "-----END ... KEY-----".
```

## 2. Configurar os Secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New
repository secret**. Esses secrets autenticam só o *mecanismo de
deploy* (conexão SSH) — não são a configuração da aplicação, que vive no
`.env` do servidor (seção 3).

| Secret            | Valor                                                        |
|--------------------|---------------------------------------------------------------|
| `SSH_HOST`         | IP ou domínio do servidor                                     |
| `SSH_USER`         | `prodbr` (o usuário criado no passo 1)                        |
| `SSH_PRIVATE_KEY`  | Conteúdo completo da chave privada gerada acima               |
| `SSH_PORT`         | Porta do SSH, só se não for a 22 (opcional)                   |
| `DEPLOY_PATH`      | `/opt/prodbr` (ou o caminho que você usou)                    |

## 3. Variáveis de ambiente da aplicação (`.env` no servidor)

Essas ficam **só no `.env` do servidor** (nunca em secret do GitHub nem
commitadas) — o deploy não mexe nelas, então configure uma vez e elas
persistem entre deploys:

| Variável                  | Padrão                              | Pra que serve                                                        |
|----------------------------|--------------------------------------|-----------------------------------------------------------------------|
| `PUBLIC_DATABASE_URL`      | `sqlite:///./data/public.sqlite3`    | Base pública (produtos/NCM/fiscal/revisões) - a que é exportável.     |
| `COMMUNITY_DATABASE_URL`   | `sqlite:///./data/community.sqlite3` | Base de comunidade (usuários/chaves/moderação) - nunca exportada.     |
| `MAX_PAGE_SIZE`            | `10`                                  | Limite de itens por página em buscas/listagens.                      |
| `RATE_LIMIT_READ`          | `60/minute`                          | Limite de requisições de leitura por IP.                              |
| `RATE_LIMIT_WRITE`         | `10/minute`                          | Limite de requisições de escrita por IP.                              |
| `AUTO_APPROVE_REPUTATION`  | `20`                                  | Reputação mínima pra uma contribuição ser aplicada direto.            |
| `REPUTATION_PER_CREATE`    | `3`                                   | Reputação ganha ao criar algo (aplicado ou aprovado).                 |
| `REPUTATION_PER_UPDATE`    | `1`                                   | Reputação ganha ao editar algo.                                       |
| `REPUTATION_PENALTY_REJECT`| `2`                                   | Reputação perdida quando uma contribuição é rejeitada.                |
| `SESSION_TTL_HOURS`        | `336` (14 dias)                      | Validade do token de sessão (login via usuário/senha).                |
| `ADS_SNIPPET`              | *(vazio = sem anúncio)*              | HTML/JS do provedor de anúncios da sua instância (ex: AdSense).       |

Nenhuma delas é obrigatória — sem `.env`, a aplicação sobe com os
padrões acima (bases SQLite locais, sem anúncio). Ajuste só o que quiser
mudar.

## 4. Rodar o deploy

- **Automático:** todo `git push` na `main` dispara o workflow
  `.github/workflows/deploy.yml`.
- **Manual ("Re-run job"):** aba **Actions** do GitHub → workflow
  **Deploy** → **Run workflow** (ou, num run que já existir, o botão
  **Re-run all jobs**) — útil se o deploy falhou por uma instabilidade
  passageira do servidor e não precisa de commit novo pra tentar de novo.

O workflow faz `git reset --hard origin/main` na pasta do servidor - por
isso a pasta em `/opt/prodbr` deve ser tratada como só-leitura por
humanos (nenhuma edição manual lá, sempre via commit + push).
