from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.models_public import FiscalRule

# Campos que se completam entre regras: a regra estadual (ICMS da UF) nao
# esconde o IPI/II da regra nacional oficial, e vice-versa.
MERGEABLE_FIELDS = (
    "origin",
    "icms_rate",
    "ipi_rate",
    "pis_rate",
    "cofins_rate",
    "cbs_rate",
    "ibs_rate",
    "ii_rate",
    "fcp_rate",
    "icms_st_mva_rate",
)


def resolve_fiscal_rule(
    db: DbSession,
    ncm: str,
    uf: str | None,
    on_date: date,
    cest: str | None = None,
    country: str = "BR",
) -> FiscalRule | None:
    """Regra fiscal vigente para o NCM (+CEST opcional) na UF e data
    pedidas, dentro do pais informado (`country`, padrao "BR" - o NCM e
    do Mercosul, mas cada pais membro tributa com suas proprias regras).

    Campo a campo: cada aliquota vem da regra mais especifica (CEST > UF >
    nacional, depois a mais recente) que tem aquele campo preenchido. Assim
    a regra nacional oficial (IPI/II da TIPI/TEC) e a regra da UF cadastrada
    pela comunidade (ICMS/FCP) se somam. Devolve um FiscalRule montado (nao
    gravado) com id/datas da regra mais especifica e as fontes de todas as
    que contribuiram.
    """
    query = (
        db.query(FiscalRule)
        .filter(FiscalRule.ncm == ncm)
        .filter(FiscalRule.country == country)
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
    top = candidates[0]
    if len(candidates) == 1:
        return top

    merged = FiscalRule(
        id=top.id,
        ncm=top.ncm,
        cest=top.cest,
        country=top.country,
        uf=top.uf,
        valid_from=top.valid_from,
        valid_until=top.valid_until,
        created_at=top.created_at,
    )
    used = []
    for field in MERGEABLE_FIELDS:
        for rule in candidates:
            value = getattr(rule, field)
            if value is not None:
                setattr(merged, field, value)
                if rule not in used:
                    used.append(rule)
                break
    used = used or [top]
    notes = [rule.notes for rule in used if rule.notes]
    merged.notes = " ".join(notes)[:500] or None
    merged.source = " + ".join(dict.fromkeys(rule.source for rule in used))[:120]
    return merged
