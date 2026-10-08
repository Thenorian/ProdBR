"""Qual alíquota vale pra um NCM num lugar e numa data.

Um NCM pode ter várias regras ao mesmo tempo - a nacional oficial (IPI/II
da TIPI e da TEC), a do estado (ICMS/FCP), uma específica de um CEST... A
resposta junta todas, tributo a tributo: cada alíquota vem da regra mais
específica que tem aquele tributo (CEST > subdivisão > nacional; empate,
a mais recente). Assim o ICMS de SP e o IPI nacional saem juntos.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from app.models import FiscalRule


@dataclass
class ResolvedFiscalRule:
    """Regra montada (não gravada). id/escopo/datas são da regra mais
    específica; `rates`, `notes` e `source` juntam todas que contribuíram."""

    id: int
    ncm: str
    cest: str | None
    country_id: str
    state_code: str | None
    valid_from: date
    valid_until: date | None
    created_at: datetime
    rates: dict[str, float] = field(default_factory=dict)
    notes: str | None = None
    source: str = ""

    @property
    def sources(self) -> list[str]:
        return self.source.split(" + ") if self.source else []


class FiscalRuleResolver:
    def __init__(self, db: DbSession):
        self.db = db

    def resolve(
        self,
        ncm: str,
        country_id: str = "BR",
        state_code: str | None = None,
        on_date: date | None = None,
        cest: str | None = None,
    ) -> ResolvedFiscalRule | None:
        on_date = on_date or date.today()
        candidates = self._candidates(ncm, country_id, state_code, on_date, cest)
        if not candidates:
            return None

        top = candidates[0]
        rates: dict[str, float] = {}
        used: list[FiscalRule] = []
        for rule in candidates:
            for code, rate in rule.rates.items():
                if code not in rates:
                    rates[code] = rate
                    if rule not in used:
                        used.append(rule)
        used = used or [top]

        notes = " ".join(rule.notes for rule in used if rule.notes)[:500] or None
        source = " + ".join(dict.fromkeys(rule.source for rule in used))[:120]
        return ResolvedFiscalRule(
            id=top.id,
            ncm=top.ncm,
            cest=top.cest,
            country_id=top.country_id,
            state_code=top.state_code,
            valid_from=top.valid_from,
            valid_until=top.valid_until,
            created_at=top.created_at,
            rates=rates,
            notes=notes,
            source=source,
        )

    def _candidates(self, ncm, country_id, state_code, on_date, cest) -> list[FiscalRule]:
        """Regras vigentes que se aplicam, da mais específica pra menos."""
        rules = (
            self.db.query(FiscalRule)
            .filter(FiscalRule.ncm == ncm, FiscalRule.country_id == country_id)
            .filter(FiscalRule.valid_from <= on_date)
            .filter(or_(FiscalRule.valid_until.is_(None), FiscalRule.valid_until >= on_date))
            .all()
        )
        applicable = [
            rule
            for rule in rules
            if rule.cest in (None, cest) and rule.state_code in (None, state_code)
        ]

        def specificity(rule: FiscalRule) -> tuple[int, date]:
            score = (2 if rule.cest is not None else 0) + (1 if rule.state_code is not None else 0)
            return (score, rule.valid_from)

        return sorted(applicable, key=specificity, reverse=True)
