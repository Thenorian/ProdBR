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

    session_ttl_hours: int = 24 * 14


settings = Settings()
