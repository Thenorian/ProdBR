"""Motor central de contribuicoes: toda escrita na base publica passa por
aqui. Usuarios com reputacao/papel suficiente tem a mudanca aplicada na
hora; os demais caem numa fila de moderacao (PendingChange). Em ambos os
casos, uma vez aplicada, a mudanca vira uma ou mais linhas de Revision -
para produtos/regras fiscais, uma por campo alterado; para identificadores,
uma so (o registro inteiro e a unidade de mudanca).
"""

import json
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.models_community import PendingChange, User
from app.models_public import FiscalRule, NcmClassification, Product, ProductIdentifier, Revision

ENTITY_MODELS = {"product": Product, "fiscal_rule": FiscalRule, "ncm_classification": NcmClassification}

WRITABLE_FIELDS = {
    "product": [
        "name",
        "brand",
        "ncm",
        "cest",
        "category",
        "commercial_unit",
        "description",
        "manufacturer",
        "source",
    ],
    "fiscal_rule": [
        "ncm",
        "cest",
        "country",
        "uf",
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
        "notes",
        "valid_from",
        "valid_until",
        "source",
    ],
    # "ncm" so entra aqui porque na criacao ele e a propria chave primaria
    # (fornecida pelo contribuidor, nao gerada pelo sistema como
    # Product.id) - por isso NcmUpdate nao expoe esse campo, so criacao.
    "ncm_classification": ["ncm", "description", "chapter", "unit", "source"],
}

DATE_FIELDS = {"fiscal_rule": {"valid_from", "valid_until"}}
INT_PK_ENTITIES = {"fiscal_rule"}
# Nome do atributo de chave primaria de cada entidade - "id" pra maioria,
# mas ncm_classification usa o proprio codigo NCM como chave.
PK_ATTR = {"ncm_classification": "ncm"}


def _coerce(entity_type: str, field: str, value):
    if value is not None and field in DATE_FIELDS.get(entity_type, set()) and isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _serialize(value):
    if isinstance(value, date):
        return value.isoformat()
    return value


def can_auto_approve(user: User) -> bool:
    return user.role in ("moderator", "admin") or user.reputation >= settings.auto_approve_reputation


def apply_entity_change(
    db_public: DbSession,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
    contributor: str | None,
    reason: str,
):
    model = ENTITY_MODELS[entity_type]
    fields = WRITABLE_FIELDS[entity_type]

    if entity_id is None:
        kwargs = {f: _coerce(entity_type, f, payload[f]) for f in fields if f in payload}
        entity = model(**kwargs)
        db_public.add(entity)
        try:
            db_public.flush()
        except IntegrityError as exc:
            db_public.rollback()
            raise ValueError(f"{entity_type} ja existe ou viola uma restricao unica.") from exc
        pk_value = getattr(entity, PK_ATTR.get(entity_type, "id"))
        for field in fields:
            if field in payload and payload[field] is not None:
                db_public.add(
                    Revision(
                        entity_type=entity_type,
                        entity_id=str(pk_value),
                        contributor=contributor,
                        action="create",
                        field=field,
                        old_value=None,
                        new_value=json.dumps(_serialize(getattr(entity, field))),
                        reason=reason,
                    )
                )
    else:
        pk = int(entity_id) if entity_type in INT_PK_ENTITIES else entity_id
        entity = db_public.get(model, pk)
        if entity is None:
            raise ValueError(f"{entity_type} '{entity_id}' nao encontrado.")
        pk_value = getattr(entity, PK_ATTR.get(entity_type, "id"))
        for field, raw_value in payload.items():
            if field not in fields:
                continue
            new_value = _coerce(entity_type, field, raw_value)
            old_value = getattr(entity, field)
            if old_value == new_value:
                continue
            setattr(entity, field, new_value)
            db_public.add(
                Revision(
                    entity_type=entity_type,
                    entity_id=str(pk_value),
                    contributor=contributor,
                    action="update",
                    field=field,
                    old_value=json.dumps(_serialize(old_value)),
                    new_value=json.dumps(_serialize(new_value)),
                    reason=reason,
                )
            )

    db_public.commit()
    db_public.refresh(entity)
    return entity


def apply_identifier_create(db_public: DbSession, payload: dict, contributor: str | None, reason: str):
    identifier = ProductIdentifier(
        product_id=payload["product_id"], type=payload["type"], value=payload["value"]
    )
    db_public.add(identifier)
    try:
        db_public.flush()
    except IntegrityError as exc:
        db_public.rollback()
        raise ValueError(f"Identificador '{payload['value']}' ja pertence a outro produto.") from exc
    db_public.add(
        Revision(
            entity_type="identifier",
            entity_id=str(identifier.id),
            contributor=contributor,
            action="create",
            field="value",
            old_value=None,
            new_value=json.dumps(f"{identifier.type}:{identifier.value}"),
            reason=reason,
        )
    )
    db_public.commit()
    db_public.refresh(identifier)
    return identifier


def apply_identifier_delete(db_public: DbSession, identifier_id: int, contributor: str | None, reason: str):
    identifier = db_public.get(ProductIdentifier, identifier_id)
    if identifier is None:
        raise ValueError(f"Identificador {identifier_id} nao encontrado.")
    old_value = f"{identifier.type}:{identifier.value}"
    db_public.delete(identifier)
    db_public.add(
        Revision(
            entity_type="identifier",
            entity_id=str(identifier_id),
            contributor=contributor,
            action="delete",
            field="value",
            old_value=json.dumps(old_value),
            new_value=None,
            reason=reason,
        )
    )
    db_public.commit()
    return None


def dispatch_apply(db_public: DbSession, entity_type: str, entity_id: str | None, payload: dict, contributor: str | None, reason: str):
    """Aplica uma mudanca ja aprovada (auto ou por moderador). Retorna a
    entidade resultante (None para delete de identificador)."""
    if entity_type == "identifier":
        if entity_id is None:
            return apply_identifier_create(db_public, payload, contributor, reason)
        return apply_identifier_delete(db_public, int(entity_id), contributor, reason)
    return apply_entity_change(db_public, entity_type, entity_id, payload, contributor, reason)


def reputation_delta(entity_id: str | None) -> int:
    return settings.reputation_per_create if entity_id is None else settings.reputation_per_update


def propose_or_apply(
    db_public: DbSession,
    db_community: DbSession,
    user: User,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
    reason: str,
):
    """Ponto de entrada usado pelas rotas de escrita. `payload` deve estar
    em formato JSON-serializavel (ex: `model_dump(mode="json")`)."""
    if can_auto_approve(user):
        entity = dispatch_apply(db_public, entity_type, entity_id, payload, user.username, reason)
        user.reputation += reputation_delta(entity_id)
        db_community.commit()
        return {"status": "applied", "entity": entity}

    pending = PendingChange(
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        reason=reason,
        user_id=user.id,
    )
    db_community.add(pending)
    db_community.commit()
    db_community.refresh(pending)
    return {"status": "pending", "pending_change": pending}
