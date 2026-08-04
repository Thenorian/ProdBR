from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.models_public import FiscalRule


def resolve_fiscal_rule(
    db: DbSession, ncm: str, uf: str | None, on_date: date, cest: str | None = None
) -> FiscalRule | None:
    """Regra fiscal mais especifica e vigente para o NCM (+CEST opcional)
    na UF e data pedidas. Regras com uf/cest nulos sao "nacional/default"
    e servem de fallback quando nao ha regra especifica para o estado.
    """
    query = (
        db.query(FiscalRule)
        .filter(FiscalRule.ncm == ncm)
        .filter(FiscalRule.valid_from <= on_date)
        .filter(or_(FiscalRule.valid_until.is_(None), FiscalRule.valid_until >= on_date))
    )
    candidates = [
        rule
        for rule in query.all()
        if (rule.cest is None or rule.cest == cest) and (rule.uf is None or rule.uf == uf)
    ]
    if not candidates:
        return None

    def specificity(rule: FiscalRule) -> tuple[int, date]:
        score = (2 if rule.cest is not None and rule.cest == cest else 0) + (
            1 if rule.uf is not None and rule.uf == uf else 0
        )
        return (score, rule.valid_from)

    candidates.sort(key=specificity, reverse=True)
    return candidates[0]
