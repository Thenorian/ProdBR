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

    background_tasks.add_task(copy_path.unlink, missing_ok=True)
    background_tasks.add_task(copy_path.parent.rmdir)
    return FileResponse(copy_path, filename="prodbr.sqlite3", media_type="application/vnd.sqlite3")
