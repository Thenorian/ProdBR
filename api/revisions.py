from fastapi import APIRouter, Depends

from api.common import DEFAULT_PAGE_SIZE, page_limits, result_or_error
from api.rate_limit import limit_reads
from database.revision import RevisionDB

router = APIRouter(tags=["Histórico"])


@router.get("/revisions", dependencies=[Depends(limit_reads)])
def list_recent_revisions(contributor: str | None = None, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Últimas alterações de toda a base (o "git log" do ProdBR). Filtra por contribuidor se informado."""
    limit, offset = page_limits(limit, offset)
    revisions = result_or_error(RevisionDB().list_recent(limit, offset, (contributor or "").strip() or None), 500)
    return {**revisions, "limit": limit, "offset": offset}
