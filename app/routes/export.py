from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from app.config import settings
from app.database import public_db_path
from app.export import generate_csv_zip, generate_sql_dump
from app.rate_limit import limiter

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/sqlite")
@limiter.limit(settings.rate_limit_read)
def export_sqlite(request: Request):
    """Baixa o arquivo SQLite completo da base publica (produtos,
    identificadores, regras fiscais, revisoes). Nunca inclui dados de
    usuarios/moderacao - isso vive num banco separado."""
    return FileResponse(
        public_db_path(), media_type="application/vnd.sqlite3", filename="prodbr_public.sqlite3"
    )


@router.get("/sql")
@limiter.limit(settings.rate_limit_read)
def export_sql(request: Request):
    dump = generate_sql_dump()
    return Response(
        content=dump,
        media_type="application/sql",
        headers={"Content-Disposition": "attachment; filename=prodbr_public.sql"},
    )


@router.get("/csv")
@limiter.limit(settings.rate_limit_read)
def export_csv(request: Request):
    content = generate_csv_zip()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=prodbr_public_csv.zip"},
    )
