"""Países, subdivisões e tributos.

- TaxCatalog: leitura (usado pela consulta, pelo formulário de regra e pela
  validação das alíquotas).
- TaxCatalogEditor: o que o admin cadastra em /admin/tributos.

Tributo não é apagado - regras antigas podem usar. Desativa (`active`).
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models import Country, FiscalRule, State, TaxType
from app.services.errors import ConflictError, NotFoundError


def language_of(country: Country, lang: str | None) -> str:
    """"pt", "es", "en"... - o pedido (?lang=) ou o idioma do país."""
    chosen = (lang or country.language or "pt").strip()
    return chosen.split("-")[0].lower()


def tax_name(tax: TaxType, country: Country, lang: str) -> str:
    """Nome do tributo no idioma pedido (o oficial, se não tiver tradução)."""
    if lang == language_of(country, None):
        return tax.name
    return (tax.translations or {}).get(lang) or tax.name


class TaxCatalog:
    def __init__(self, db: DbSession):
        self.db = db

    def countries(self) -> list[Country]:
        return self.db.query(Country).order_by(Country.name).all()

    def country(self, code: str) -> Country:
        country = self.db.get(Country, code.strip().upper())
        if country is None:
            raise NotFoundError(f"País '{code.upper()}' não cadastrado. Veja /countries.")
        return country

    def states(self, country_id: str) -> list[State]:
        return self.db.query(State).filter(State.country_id == country_id.strip().upper()).order_by(State.name).all()

    def state(self, country: Country, code: str) -> State:
        state = self.db.get(State, (country.id, code.strip().upper()))
        if state is None:
            raise NotFoundError(
                f"{country.subdivision_label} '{code.upper()}' não existe em {country.name}. Veja /countries/{country.id}/states."
            )
        return state

    def tax_types(self, country_id: str, include_inactive: bool = False) -> list[TaxType]:
        query = self.db.query(TaxType).filter(TaxType.country_id == country_id.strip().upper())
        if not include_inactive:
            query = query.filter(TaxType.active.is_(True))
        return query.order_by(TaxType.sort_order, TaxType.code).all()

    def tax_types_by_code(self, country_id: str) -> dict[str, TaxType]:
        """Todos, inclusive desativados - pra validar e gravar alíquota."""
        return {t.code: t for t in self.tax_types(country_id, include_inactive=True)}


class TaxCatalogEditor:
    def __init__(self, db: DbSession):
        self.db = db
        self.catalog = TaxCatalog(db)

    def create_country(self, data: dict) -> Country:
        code = data["id"].strip().upper()
        if self.db.get(Country, code) is not None:
            raise ConflictError(f"País '{code}' já existe.")
        country = Country(**{**data, "id": code, "name": data["name"].strip()})
        self.db.add(country)
        self.db.commit()
        return country

    def update_country(self, country_id: str, data: dict) -> Country:
        country = self.catalog.country(country_id)
        for field, value in data.items():
            if value is not None:
                setattr(country, field, value.strip())
        self.db.commit()
        return country

    def add_state(self, country_id: str, code: str, name: str) -> State:
        country = self.catalog.country(country_id)
        state = State(country_id=country.id, code=code.strip().upper(), name=name.strip())
        self.db.add(state)
        self._commit_or_conflict(f"'{state.code}' já existe em {country.name}.")
        return state

    def remove_state(self, country_id: str, code: str) -> None:
        country = self.catalog.country(country_id)
        state = self.catalog.state(country, code)
        in_use = self.db.query(FiscalRule.id).filter(
            FiscalRule.country_id == country.id, FiscalRule.state_code == state.code
        ).first()
        if in_use:
            raise ConflictError(f"Há regras fiscais usando '{state.code}' - não dá pra remover.")
        self.db.delete(state)
        self.db.commit()

    def create_tax_type(self, data: dict) -> TaxType:
        country = self.catalog.country(data["country_id"])
        tax = TaxType(**{**data, "country_id": country.id, "code": data["code"].strip().upper()})
        self.db.add(tax)
        self._commit_or_conflict(f"{country.name} já tem o tributo '{tax.code}'.")
        return tax

    # Campos que o admin pode zerar de propósito (mandando null).
    CLEARABLE_TAX_FIELDS = {"default_rate", "default_source", "translations", "description"}

    def update_tax_type(self, tax_id: int, data: dict) -> TaxType:
        tax = self.db.get(TaxType, tax_id)
        if tax is None:
            raise NotFoundError("Tributo não encontrado.")
        for field, value in data.items():
            if value is None and field not in self.CLEARABLE_TAX_FIELDS:
                continue
            setattr(tax, field, value)
        self.db.commit()
        return tax

    def _commit_or_conflict(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(message) from exc
