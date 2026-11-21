from fastapi import Header, HTTPException

from database.contributor import ContributorDB


def require_contributor(x_api_key: str | None = Header(None, description="Seu token de contribuidor.")):
    """
    Toda escrita exige o token no cabeçalho X-API-Key. Leitura nunca exige.
    Devolve o contribuidor dono do token: {"id", "username", ...}.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Envie o seu token no cabeçalho X-API-Key.")

    ok, contributor = ContributorDB().find_by_token(x_api_key)
    if not ok:
        raise HTTPException(status_code=500, detail="Erro ao conferir o token.")
    if contributor is None:
        raise HTTPException(status_code=401, detail="Token inválido.")

    return contributor


def register_contribution(contributor, changed_fields):
    """Soma a reputação de quem contribuiu. A reputação só aparece no site, nunca na API."""
    if changed_fields:
        ContributorDB().register_contribution(contributor["id"], len(changed_fields))
