from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

Path("./data").mkdir(exist_ok=True)


def _make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


class PublicBase(DeclarativeBase):
    """Metadata da base publica/distribuivel (produtos, fiscal, revisoes)."""


class CommunityBase(DeclarativeBase):
    """Metadata da base de comunidade (usuarios, chaves, moderacao) - fica
    so no servidor, nunca e exportada junto com a base publica."""


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


def public_db_path() -> str:
    """Caminho de arquivo do banco publico, para as rotas de exportacao
    (/export/*). So funciona quando PUBLIC_DATABASE_URL e sqlite."""
    prefix = "sqlite:///"
    if not settings.public_database_url.startswith(prefix):
        raise RuntimeError("Exportacao de arquivo so e suportada com PUBLIC_DATABASE_URL sqlite.")
    return settings.public_database_url[len(prefix):]


def ensure_column(engine, table: str, column: str, ddl_type: str) -> None:
    """Adiciona uma coluna nova numa tabela que ja existe. create_all so
    cria tabelas que faltam, nunca colunas - sem isso, uma coluna nova no
    modelo quebraria o banco ja em producao (SQLite)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    if column in {c["name"] for c in insp.get_columns(table)}:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
