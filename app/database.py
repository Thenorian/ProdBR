"""Conexão com os dois bancos do ProdBR.

- **Base pública** (`PUBLIC_DATABASE_URL`): produtos, NCM, regras fiscais e
  histórico. É o arquivo que qualquer pessoa baixa em /export/sqlite e
  leva pro próprio sistema - a estrutura dela está documentada em
  app/models/public.py e na página /estrutura.
- **Base de comunidade** (`COMMUNITY_DATABASE_URL`): usuários, chaves,
  sessões e fila de moderação. Fica só no servidor, nunca é distribuída.
"""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

Path("./data").mkdir(exist_ok=True)


def _make_engine(url: str):
    if not url.startswith("sqlite"):
        return create_engine(url)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite só confere chave estrangeira se pedir, conexão por conexão.
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


class PublicBase(DeclarativeBase):
    """Tabelas da base pública (a que é distribuída)."""


class CommunityBase(DeclarativeBase):
    """Tabelas da base de comunidade (só no servidor)."""


public_engine = _make_engine(settings.public_database_url)
community_engine = _make_engine(settings.community_database_url)

PublicSession = sessionmaker(autocommit=False, autoflush=False, bind=public_engine)
CommunitySession = sessionmaker(autocommit=False, autoflush=False, bind=community_engine)


def get_public_db():
    db = PublicSession()
    try:
        yield db
    finally:
        db.close()


def get_community_db():
    db = CommunitySession()
    try:
        yield db
    finally:
        db.close()


def sqlite_path(url: str) -> str:
    """Caminho do arquivo de um banco SQLite (`sqlite:///./data/x.sqlite3`
    -> `./data/x.sqlite3`). Exportação e migração só funcionam com SQLite."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise RuntimeError("Essa operação só é suportada com banco SQLite.")
    return url[len(prefix):]


def public_db_path() -> str:
    return sqlite_path(settings.public_database_url)
