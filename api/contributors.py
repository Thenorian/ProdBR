from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_contributor
from api.common import result_or_error
from api.rate_limit import limit_new_contributors
from database.contributor import ContributorDB, can_write_directly
from util.validation import clean_username

router = APIRouter(tags=["Contribuidores"])


class NewContributorInput(BaseModel):
    username: str


@router.post("/contributors", status_code=201, dependencies=[Depends(limit_new_contributors)])
def create_contributor(payload: NewContributorInput):
    """
    Cria seu acesso de contribuidor, como um usuário do Git: só um nome.
    O token volta uma única vez. Guarde: ele assina tudo que você alterar (cabeçalho X-API-Key).
    """
    username = clean_username(payload.username)
    if not username:
        raise HTTPException(status_code=400, detail="Nome de usuário: 3 a 40 letras, números, ponto, hífen ou sublinhado.")

    return result_or_error(ContributorDB().create(username))


@router.post("/contributors/me/tokens", status_code=201, dependencies=[Depends(limit_new_contributors)])
def create_another_token(contributor=Depends(require_contributor)):
    """Gera mais um token para o mesmo usuário (ex: um para cada ERP). Os antigos continuam valendo."""
    return result_or_error(ContributorDB().create_new_token(contributor))


@router.get("/contributors/me")
def who_am_i(contributor=Depends(require_contributor)):
    """
    Confere se o token vale e diz de quem ele é.
    changes_need_votes=true: as suas alterações ainda passam pela votação da comunidade.
    """
    return {"username": contributor["username"], "changes_need_votes": not can_write_directly(contributor)}
