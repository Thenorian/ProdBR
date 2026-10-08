"""Motor de contribuições: toda escrita na base pública passa por aqui.

    rota -> ContributionService.submit(...)
              ├─ writer.prepare()   valida e normaliza o payload
              ├─ aprovação automática? -> apply() na hora
              └─ senão -> PendingChange (fila de moderação/votação)

    apply() -> writer.create/update/delete + RevisionLog (histórico)

Cada tipo de registro tem o seu EntityWriter (produto, código de barras,
NCM, regra fiscal). Tipo novo = um writer novo registrado em WRITERS, sem
mexer no motor.
"""

import json
from abc import ABC, abstractmethod
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models import (
    Category,
    FiscalRule,
    FiscalRuleRate,
    NcmClassification,
    PendingChange,
    Product,
    ProductIdentifier,
    Revision,
    User,
)
from app.services.errors import ConflictError, InvalidDataError, NotFoundError
from app.services.packaging import PACKAGE_FIELDS, package_fields
from app.services.reputation import can_auto_approve, credit
from app.services.taxes import TaxCatalog


# +--------------------------------------------------------------------+
# |  Histórico                                                         |
# +--------------------------------------------------------------------+
def _json(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value.isoformat() if isinstance(value, date) else value, ensure_ascii=False)


class RevisionLog:
    """Escreve as linhas de `revisions` de uma alteração."""

    def __init__(self, db: DbSession, entity_type: str, contributor: str | None, reason: str):
        self.db = db
        self.entity_type = entity_type
        self.contributor = contributor
        self.reason = reason

    def record(self, action: str, entity_id, field: str, old=None, new=None) -> None:
        self.db.add(
            Revision(
                entity_type=self.entity_type,
                entity_id=str(entity_id),
                contributor=self.contributor,
                action=action,
                field=field,
                old_value=_json(old),
                new_value=_json(new),
                reason=self.reason,
            )
        )


# +--------------------------------------------------------------------+
# |  Writers - um por tipo de registro                                 |
# +--------------------------------------------------------------------+
class EntityWriter(ABC):
    entity_type: str

    def prepare(self, db: DbSession, entity_id: str | None, payload: dict) -> dict:
        """Valida e normaliza antes de aplicar ou mandar pra fila (o que
        vai pra fila já tem que estar válido). Padrão: não muda nada."""
        return payload

    @abstractmethod
    def create(self, db: DbSession, payload: dict, log: RevisionLog): ...

    @abstractmethod
    def update(self, db: DbSession, entity_id: str, payload: dict, log: RevisionLog): ...

    def delete(self, db: DbSession, entity_id: str, log: RevisionLog) -> None:
        raise InvalidDataError(f"{self.entity_type} não pode ser apagado.")


class FieldWriter(EntityWriter):
    """Registro simples: cada campo do payload vira uma coluna do modelo."""

    model: type
    fields: tuple[str, ...]
    label: str

    def find(self, db: DbSession, entity_id: str):
        entity = db.get(self.model, entity_id)
        if entity is None:
            raise NotFoundError(f"{self.label} '{entity_id}' não encontrado.")
        return entity

    def entity_key(self, entity) -> str:
        return entity.id

    def read(self, entity, field: str):
        return getattr(entity, field)

    def write(self, db: DbSession, entity, field: str, value) -> None:
        setattr(entity, field, value)

    def create(self, db, payload, log):
        entity = self.model()
        for field in self.fields:
            if field in payload:
                self.write(db, entity, field, payload[field])
        db.add(entity)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"{self.label} já existe.") from exc
        for field in self.fields:
            if payload.get(field) is not None:
                log.record("create", self.entity_key(entity), field, new=self.read(entity, field))
        return entity

    def update(self, db, entity_id, payload, log):
        entity = self.find(db, entity_id)
        for field in self.fields:
            if field not in payload:
                continue
            old = self.read(entity, field)
            self.write(db, entity, field, payload[field])
            new = self.read(entity, field)
            if old != new:
                log.record("update", self.entity_key(entity), field, old, new)
        return entity


class _CategoryMixin:
    """Categoria chega como texto e é gravada como categories.id (cria a
    categoria na primeira vez que aparece)."""

    def write(self, db, entity, field, value):
        if field != "category":
            return super().write(db, entity, field, value)
        name = (value or "").strip()
        if not name:
            entity.category_ref = None
            return
        category = db.query(Category).filter(Category.name == name).first()
        entity.category_ref = category or Category(name=name)


class ProductWriter(_CategoryMixin, FieldWriter):
    entity_type = "product"
    model = Product
    label = "Produto"
    fields = ("name", "brand", "manufacturer", "ncm", "cest", "category", "commercial_unit", "description", "source")


class NcmWriter(FieldWriter):
    entity_type = "ncm_classification"
    model = NcmClassification
    label = "NCM"
    fields = ("ncm", "description", "source")

    def entity_key(self, entity) -> str:
        return entity.ncm


class IdentifierWriter(EntityWriter):
    """O código inteiro é a unidade de mudança: o histórico mostra
    "gtin13:789..." em vez de tipo e valor separados."""

    entity_type = "identifier"

    def prepare(self, db, entity_id, payload):
        if entity_id is not None and not payload:
            return payload  # apagar
        data = {k: v for k, v in payload.items() if k not in PACKAGE_FIELDS}
        if "value" in data and data["value"] is not None:
            data["value"] = data["value"].strip()
        try:
            data.update(package_fields(payload))
        except ValueError as exc:
            raise InvalidDataError(str(exc)) from exc
        if entity_id is not None and not data:
            raise InvalidDataError("Informe o que mudar no código.")
        return data

    def _find(self, db, entity_id) -> ProductIdentifier:
        identifier = db.get(ProductIdentifier, int(entity_id))
        if identifier is None:
            raise NotFoundError(f"Código {entity_id} não encontrado.")
        return identifier

    def _flush_or_conflict(self, db, value) -> None:
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"O código '{value}' já pertence a outro produto.") from exc

    def create(self, db, payload, log):
        if db.get(Product, payload["product_id"]) is None:
            raise NotFoundError(f"Produto '{payload['product_id']}' não encontrado.")
        identifier = ProductIdentifier(
            product_id=payload["product_id"],
            type=payload["type"],
            value=payload["value"],
            **{k: payload.get(k) for k in PACKAGE_FIELDS},
        )
        db.add(identifier)
        self._flush_or_conflict(db, payload["value"])
        log.record("create", identifier.id, "value", new=f"{identifier.type}:{identifier.value}")
        for field in PACKAGE_FIELDS:
            if payload.get(field) is not None:
                log.record("create", identifier.id, field, new=payload[field])
        return identifier

    def update(self, db, entity_id, payload, log):
        identifier = self._find(db, entity_id)
        for field in ("type", "value", *PACKAGE_FIELDS):
            new = payload.get(field)
            old = getattr(identifier, field)
            if new is None or new == old:
                continue
            setattr(identifier, field, new)
            log.record("update", identifier.id, field, old, new)
        self._flush_or_conflict(db, payload.get("value"))
        return identifier

    def delete(self, db, entity_id, log):
        identifier = self._find(db, entity_id)
        log.record("delete", identifier.id, "value", old=f"{identifier.type}:{identifier.value}")
        db.delete(identifier)


class FiscalRuleWriter(EntityWriter):
    """Regra fiscal: escopo (NCM, país, subdivisão, CEST, período) +
    alíquotas, que ficam uma por linha em fiscal_rule_rates.

    No payload os campos têm o nome da API (`country`, `uf`, `rates`); no
    banco são `country_id`, `state_code` e as linhas de alíquota."""

    entity_type = "fiscal_rule"
    # nome na API -> coluna do modelo
    COLUMNS = {
        "ncm": "ncm",
        "cest": "cest",
        "country": "country_id",
        "uf": "state_code",
        "valid_from": "valid_from",
        "valid_until": "valid_until",
        "notes": "notes",
        "source": "source",
    }
    DATE_FIELDS = ("valid_from", "valid_until")

    def prepare(self, db, entity_id, payload):
        current = self._find(db, entity_id) if entity_id is not None else None
        data = dict(payload)
        catalog = TaxCatalog(db)

        country = catalog.country(current.country_id if current else data.get("country") or "BR")
        if current is None:
            data["country"] = country.id
        if data.get("uf"):
            data["uf"] = catalog.state(country, data["uf"]).code

        if data.get("rates"):
            types = catalog.tax_types_by_code(country.id)
            rates = {}
            for code, value in data["rates"].items():
                code = code.strip().upper()
                if code not in types:
                    known = ", ".join(sorted(types)) or "nenhum"
                    raise InvalidDataError(f"Tributo '{code}' não existe em {country.name} (cadastrados: {known}).")
                if value is not None and value < 0:
                    raise InvalidDataError(f"Alíquota de {code} não pode ser negativa.")
                rates[code] = value
            data["rates"] = rates

        valid_from = data.get("valid_from") or (current.valid_from.isoformat() if current else None)
        valid_until = data.get("valid_until") if "valid_until" in data else (current.valid_until and current.valid_until.isoformat())
        if valid_from and valid_until and str(valid_until) < str(valid_from):
            raise InvalidDataError("A vigência termina antes de começar.")
        return data

    def _find(self, db, entity_id) -> FiscalRule:
        rule = db.get(FiscalRule, int(entity_id))
        if rule is None:
            raise NotFoundError(f"Regra fiscal {entity_id} não encontrada.")
        return rule

    def _value(self, field, value):
        if field in self.DATE_FIELDS and isinstance(value, str):
            return date.fromisoformat(value)
        return value

    def create(self, db, payload, log):
        rule = FiscalRule(
            **{column: self._value(field, payload.get(field)) for field, column in self.COLUMNS.items() if field in payload}
        )
        db.add(rule)
        db.flush()
        for field, column in self.COLUMNS.items():
            if payload.get(field) is not None:
                log.record("create", rule.id, field, new=getattr(rule, column))
        self._apply_rates(db, rule, payload.get("rates") or {}, log, "create")
        return rule

    def update(self, db, entity_id, payload, log):
        rule = self._find(db, entity_id)
        for field, column in self.COLUMNS.items():
            if field not in payload or field in ("ncm", "country"):
                continue
            old, new = getattr(rule, column), self._value(field, payload[field])
            if old != new:
                setattr(rule, column, new)
                log.record("update", rule.id, field, old, new)
        self._apply_rates(db, rule, payload.get("rates") or {}, log, "update")
        return rule

    def _apply_rates(self, db, rule: FiscalRule, rates: dict, log: RevisionLog, action: str) -> None:
        """`rates` = {código: alíquota ou None}. None remove a linha."""
        if not rates:
            return
        types = TaxCatalog(db).tax_types_by_code(rule.country_id)
        current = {row.tax_type.code: row for row in rule.rate_rows}
        for code, value in rates.items():
            row = current.get(code)
            old = row.rate if row else None
            if value == old:
                continue
            if value is None:
                rule.rate_rows.remove(row)
            elif row is None:
                rule.rate_rows.append(FiscalRuleRate(tax_type=types[code], rate=value))
            else:
                row.rate = value
            log.record(action if old is None else "update", rule.id, f"rates.{code}", old, value)


WRITERS: dict[str, EntityWriter] = {
    writer.entity_type: writer
    for writer in (ProductWriter(), NcmWriter(), IdentifierWriter(), FiscalRuleWriter())
}


# +--------------------------------------------------------------------+
# |  Serviço                                                           |
# +--------------------------------------------------------------------+
class ContributionService:
    def __init__(self, db_public: DbSession, db_community: DbSession | None = None):
        self.db_public = db_public
        self.db_community = db_community

    def submit(self, user: User, entity_type: str, entity_id: str | None, payload: dict, reason: str) -> dict:
        """Ponto de entrada das rotas de escrita. `payload` já em JSON
        (ex: `model_dump(mode="json")`). Devolve
        {"status": "applied", "entity": ...} ou {"status": "pending", "pending_change": ...}."""
        payload = WRITERS[entity_type].prepare(self.db_public, entity_id, payload)

        if can_auto_approve(user):
            entity = self.apply(entity_type, entity_id, payload, user.username, reason)
            credit(user, is_creation=entity_id is None)
            self.db_community.commit()
            return {"status": "applied", "entity": entity}

        pending = PendingChange(entity_type=entity_type, entity_id=entity_id, payload=payload, reason=reason, user_id=user.id)
        self.db_community.add(pending)
        self.db_community.commit()
        self.db_community.refresh(pending)
        return {"status": "pending", "pending_change": pending}

    def apply(self, entity_type: str, entity_id: str | None, payload: dict, contributor: str | None, reason: str):
        """Grava uma mudança já aprovada (na hora ou pela moderação) e o
        histórico dela. Payload vazio numa edição = apagar."""
        writer = WRITERS[entity_type]
        log = RevisionLog(self.db_public, entity_type, contributor, reason)
        if entity_id is None:
            entity = writer.create(self.db_public, payload, log)
        elif not payload:
            writer.delete(self.db_public, entity_id, log)
            entity = None
        else:
            entity = writer.update(self.db_public, entity_id, payload, log)
        self.db_public.commit()
        if entity is not None:
            self.db_public.refresh(entity)
        return entity
