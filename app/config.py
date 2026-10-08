from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Base publica: produtos, identificadores, regras fiscais, historico de
    # revisoes. E o unico banco distribuido/baixavel (ver rotas /export).
    public_database_url: str = "sqlite:///./data/public.sqlite3"

    # Base de comunidade: usuarios, chaves de API, sessoes, fila de
    # moderacao. Nunca sai do servidor, nunca e distribuida.
    community_database_url: str = "sqlite:///./data/community.sqlite3"

    max_page_size: int = 10
    rate_limit_read: str = "60/minute"
    rate_limit_write: str = "10/minute"

    # Reputacao minima para uma contribuicao ser aplicada direto na base
    # publica. Abaixo disso, a alteracao entra na fila de moderacao.
    auto_approve_reputation: int = 20
    reputation_per_create: int = 3
    reputation_per_update: int = 1
    reputation_penalty_reject: int = 2
    # Votacao da comunidade na fila de moderacao: saldo (a favor - contra)
    # que aprova/rejeita sozinho, sem moderador. Conta nova nao vota (evita
    # alguem criar N contas pra aprovar a propria contribuicao).
    community_vote_threshold: int = 30
    vote_min_account_age_hours: int = 24

    session_ttl_hours: int = 24 * 14

    # Snippet de anuncio (HTML/JS do provedor escolhido pelo operador da
    # instancia, ex: Google AdSense). Vazio = nenhum anuncio. Configurado
    # so por variavel de ambiente - de proposito, sem painel/admin UI,
    # ja que e uma configuracao por instancia (self-hosted), nao um dado
    # da base publica.
    ads_snippet: str = ""

    # Doacoes pra manter a instancia no ar. Mesma logica do ads_snippet:
    # configuracao por instancia (variavel de ambiente), vazio = a secao de
    # doacao nao aparece - quem hospeda a propria copia nunca exibe a chave
    # Pix de outra pessoa.
    donation_pix_key: str = ""
    donation_pix_holder: str = ""  # nome do recebedor, pra conferir antes de enviar
    donation_url: str = ""  # ex: GitHub Sponsors, Apoia.se, Catarse
    donation_url_label: str = "Apoiar pelo site"

    # URL publica da instancia (ex: https://prodbr.thenorian.com) - usada no
    # sitemap.xml e no llms.txt. Vazio = deduz da requisicao.
    public_url: str = ""

    # Atualiza a tabela NCM oficial (Siscomex) sozinho, uma vez por dia, em
    # segundo plano - quem hospeda nao precisa configurar cron nenhum.
    ncm_auto_update: bool = True


settings = Settings()
