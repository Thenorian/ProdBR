import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse

from api.rate_limit import limit_downloads
from database.database import Database

router = APIRouter(tags=["Download"])


@router.get("/download/prodbr.sqlite3", dependencies=[Depends(limit_downloads)])
def download_database(background_tasks: BackgroundTasks):
    """
    Base pública inteira num arquivo SQLite (licença ODbL). Não inclui nada dos contribuidores
    além do nome de usuário que já aparece no histórico público.
    A tabela do IBPT fica de fora: ela é quase 10 vezes maior que o resto da base e é
    publicada pelo próprio IBPT. Ela continua disponível em GET /ibpt/{código}?uf=.
    """
    copy_path = Path(tempfile.mkdtemp()) / "prodbr.sqlite3"

    # A cópia usa o backup do próprio SQLite, que é seguro mesmo com o banco sendo usado.
    source = sqlite3.connect(Database().path)
    destination = sqlite3.connect(copy_path)
    try:
        source.backup(destination)
    finally:
        source.close()
        destination.close()

    remove_tables_left_out_of_download(copy_path)

    background_tasks.add_task(copy_path.unlink, missing_ok=True)
    background_tasks.add_task(copy_path.parent.rmdir)
    return FileResponse(copy_path, filename="prodbr.sqlite3", media_type="application/vnd.sqlite3")


TABLES_LEFT_OUT_OF_DOWNLOAD = ("ibpt_rates",)


def remove_tables_left_out_of_download(copy_path):
    """Esvazia, só na cópia, as tabelas que não vão no download, e compacta o arquivo."""
    copy = sqlite3.connect(copy_path)
    try:
        for table in TABLES_LEFT_OUT_OF_DOWNLOAD:
            copy.execute(f'DELETE FROM "{table}"')
        copy.commit()
        copy.execute("VACUUM")
    finally:
        copy.close()
