from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./prodbr.sqlite3"
    max_page_size: int = 10
    rate_limit_read: str = "60/minute"
    rate_limit_write: str = "10/minute"


settings = Settings()
