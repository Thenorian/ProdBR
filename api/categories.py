from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import register_contribution, require_contributor
from api.common import found_or_404, result_or_error
from api.rate_limit import limit_reads, limit_writes
from api.review_queue import send_to_review
from database.contributor import can_write_directly
from database.category import CategoryDB, delete_empty_category
from util.validation import clean_category_path, clean_cest, clean_ncm

router = APIRouter(tags=["Categorias"])


class NewCategoryInput(BaseModel):
    path: str = Field(..., max_length=600, description='Caminho completo. Ex: "Bebidas > Cervejas". Cria os níveis que faltarem.')
    ncm: str | None = Field(None, description="NCM padrão dos produtos dessa categoria (8 dígitos).")
    cest: str | None = Field(None, description="CEST padrão (7 dígitos).")
    origin: int | None = Field(None, ge=0, le=8, description="Origem padrão da mercadoria (0 a 8).")
    reason: str = Field(..., min_length=3, max_length=300)


class CategoryChangesInput(BaseModel):
    """Mande só o que quer mudar. null apaga o NCM, CEST ou origem."""
    name: str | None = Field(None, max_length=150)
    ncm: str | None = None
    cest: str | None = None
    origin: int | None = Field(None, ge=0, le=8)
    reason: str = Field(..., min_length=3, max_length=300)


@router.get("/categories", dependencies=[Depends(limit_reads)])
def list_categories():
    """
    Todas as categorias com o caminho completo e os dados fiscais padrão.
    O produto sem NCM, CEST ou origem usa o da categoria (ou da categoria acima).
    """
    return {"items": result_or_error(CategoryDB().list_all(), 500)}


@router.get("/categories/{category_id}", dependencies=[Depends(limit_reads)])
def get_category(category_id: str):
    """Categoria com os dados fiscais dela e os herdados de cima (campo inherited)."""
    category = result_or_error(CategoryDB().get(category_id), 500)
    return found_or_404(category, "Categoria não encontrada.")


@router.post("/categories", status_code=201, dependencies=[Depends(limit_writes)])
def create_category(payload: NewCategoryInput, contributor=Depends(require_contributor)):
    """Quem ainda é Iniciante recebe 202: a categoria vai para a votação (GET /pending-changes)."""
    check_new_category(payload)
    if not can_write_directly(contributor):
        return send_to_review("create_category", None, payload, contributor)
    return apply_new_category(None, payload, contributor)


@router.put("/categories/{category_id}", dependencies=[Depends(limit_writes)])
def update_category(category_id: str, payload: CategoryChangesInput, contributor=Depends(require_contributor)):
    """Quem ainda é Iniciante recebe 202: a alteração vai para a votação (GET /pending-changes)."""
    check_category_changes(category_id, payload)
    if not can_write_directly(contributor):
        return send_to_review("update_category", category_id, payload, contributor)
    return apply_category_changes(category_id, payload, contributor)


class DeleteCategoryInput(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


@router.delete("/categories/{category_id}", dependencies=[Depends(limit_writes)])
def delete_category(category_id: str, payload: DeleteCategoryInput, contributor=Depends(require_contributor)):
    """
    Apaga uma categoria vazia (sem produtos e sem subcategorias). Fica registrado no histórico.
    Quem ainda é Iniciante recebe 202: o pedido vai para a votação (GET /pending-changes).
    """
    category_or_404(category_id)
    if not can_write_directly(contributor):
        return send_to_review("delete_category", category_id, payload, contributor)
    return apply_category_deletion(category_id, payload, contributor)


def category_or_404(category_id):
    category = result_or_error(CategoryDB().get(category_id), 500)
    return found_or_404(category, "Categoria não encontrada.")


def check_new_category(payload):
    names = clean_category_path(payload.path)
    if not names:
        raise HTTPException(status_code=400, detail="Informe o caminho da categoria.")
    return names, clean_category_fiscal_data(payload, payload.model_fields_set)


def check_category_changes(category_id, payload):
    category_or_404(category_id)
    changes = clean_category_fiscal_data(payload, payload.model_fields_set)
    if "name" in payload.model_fields_set:
        name = " ".join((payload.name or "").replace(">", " ").split())
        if not name:
            raise HTTPException(status_code=400, detail="O nome da categoria não pode ficar vazio.")
        changes["name"] = name
    return changes


def apply_new_category(_target_id, payload, contributor):
    """Grava a categoria. Chamado direto pela rota ou quando a votação aprova."""
    names, fiscal_data = check_new_category(payload)
    categories = CategoryDB()
    category_id = result_or_error(categories.find_or_create_path(names, contributor["username"], payload.reason))
    changed_fields = result_or_error(categories.update(category_id, fiscal_data, contributor["username"], payload.reason))

    register_contribution(contributor, ["name", *changed_fields])
    return result_or_error(categories.get(category_id), 500)


def apply_category_changes(category_id, payload, contributor):
    """Grava a alteração. Chamado direto pela rota ou quando a votação aprova."""
    changes = check_category_changes(category_id, payload)
    categories = CategoryDB()
    changed_fields = result_or_error(categories.update(category_id, changes, contributor["username"], payload.reason))

    register_contribution(contributor, changed_fields)
    return {"changed_fields": changed_fields, "category": result_or_error(categories.get(category_id), 500)}


def apply_category_deletion(category_id, payload, contributor):
    """Apaga a categoria. Chamado direto pela rota ou quando a votação aprova."""
    result_or_error(delete_empty_category(category_id, contributor["username"], payload.reason))
    register_contribution(contributor, ["category"])
    return {"deleted": category_id}


def clean_category_fiscal_data(payload, sent_fields):
    data = {}

    if "ncm" in sent_fields:
        data["ncm_code"] = clean_ncm(payload.ncm) if payload.ncm else None
        if payload.ncm and not data["ncm_code"]:
            raise HTTPException(status_code=400, detail="NCM inválido: use 8 dígitos.")

    if "cest" in sent_fields:
        data["cest"] = clean_cest(payload.cest) if payload.cest else None
        if payload.cest and not data["cest"]:
            raise HTTPException(status_code=400, detail="CEST inválido: use 7 dígitos.")

    if "origin" in sent_fields:
        data["origin"] = payload.origin

    return data
