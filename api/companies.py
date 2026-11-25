"""
Perfil de empresa, como um verbete da Wikipedia: qualquer pessoa cadastra e completa.
Os produtos aparecem no perfil quando estão ligados à empresa (company_id do produto)
ou, sem isso, quando a marca é dela ou o fabricante tem o nome dela.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from api.auth import register_contribution, require_contributor
from api.common import DEFAULT_PAGE_SIZE, found_or_404, page_limits, result_or_error
from api.rate_limit import limit_reads, limit_writes
from api.review_queue import send_to_review
from database.company import CompanyDB
from database.contributor import can_write_directly
from database.product import ProductDB
from database.revision import RevisionDB
from util.validation import clean_cnpj, clean_phone, clean_uf, clean_website

router = APIRouter(tags=["Empresas"])

MAXIMUM_BRANDS_PER_COMPANY = 100


class CompanyInput(BaseModel):
    """Na criação, só name é obrigatório. Na edição, mande só o que quer mudar (null apaga o campo)."""
    name: str | None = Field(None, max_length=200, description="Nome como a empresa é conhecida. Ex: Nestlé")
    legal_name: str | None = Field(None, max_length=200, description="Razão social.")
    cnpj: str | None = Field(None, max_length=18, description="Opcional. Numérico ou alfanumérico, com ou sem pontuação.")
    description: str | None = Field(None, max_length=2000)
    website: str | None = Field(None, max_length=255, description="Começando com http:// ou https://")
    phone: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=120)
    uf: str | None = None
    brands: list[str] | None = Field(
        None, max_length=MAXIMUM_BRANDS_PER_COMPANY,
        description='Marcas da empresa. Substitui a lista inteira. Ex: ["Nescau", "Ninho"]',
    )
    source: str | None = Field(None, max_length=255, description="De onde veio a informação.")
    reason: str = Field(..., min_length=3, max_length=300, description="Motivo da alteração, como uma mensagem de commit.")


COMPANY_PATH = Path(
    ...,
    description="CNPJ da empresa, numérico ou alfanumérico, sem a barra (ex: 60409075000152 ou 12ABC34501DE35). "
                "Empresa sem CNPJ usa o id.",
)


def company_id_or_404(cnpj_or_id):
    company_id = result_or_error(CompanyDB().find_id(cnpj_or_id), 500)
    return found_or_404(company_id, "Empresa não encontrada.")


@router.get("/companies", dependencies=[Depends(limit_reads)])
def search_companies(q: str | None = None, uf: str | None = None, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Busca empresas por nome, razão social, CNPJ ou marca. Sem filtro, lista todas em ordem alfabética."""
    limit, offset = page_limits(limit, offset)
    text = " ".join((q or "").split())[:100] or None
    found = result_or_error(CompanyDB().search(text, clean_uf(uf), limit, offset), 500)
    return {**found, "limit": limit, "offset": offset}


@router.get("/companies/{company}", dependencies=[Depends(limit_reads)])
def get_company(company: str = COMPANY_PATH):
    """Perfil da empresa pelo CNPJ (ou pelo id, para empresa sem CNPJ), com as marcas e quantos produtos ela tem."""
    return result_or_error(CompanyDB().get_full(company_id_or_404(company)), 500)


@router.get("/companies/{company}/products", dependencies=[Depends(limit_reads)])
def list_company_products(company: str = COMPANY_PATH, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Produtos da empresa: os ligados a ela e os sem empresa cuja marca ou fabricante é dela."""
    limit, offset = page_limits(limit, offset)
    found = result_or_error(CompanyDB().list_product_ids(company_id_or_404(company), limit, offset), 500)

    products = ProductDB()
    items = [result_or_error(products.get_full(product_id), 500) for product_id in found["ids"]]
    return {"items": items, "total": found["total"], "limit": limit, "offset": offset}


@router.get("/companies/{company}/revisions", dependencies=[Depends(limit_reads)])
def list_company_revisions(company: str = COMPANY_PATH, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0):
    """Histórico de alterações do perfil, do mais novo para o mais antigo."""
    limit, offset = page_limits(limit, offset)
    revisions = result_or_error(RevisionDB().list_for("company", company_id_or_404(company), limit, offset), 500)
    return {**revisions, "limit": limit, "offset": offset}


@router.post("/companies", status_code=201, dependencies=[Depends(limit_writes)])
def create_company(payload: CompanyInput, contributor=Depends(require_contributor)):
    """Cadastra uma empresa. Quem ainda é Iniciante recebe 202: o cadastro vai para a votação."""
    check_new_company(payload)
    if not can_write_directly(contributor):
        return send_to_review("create_company", None, payload, contributor)
    return apply_new_company(None, payload, contributor)


@router.put("/companies/{company}", dependencies=[Depends(limit_writes)])
def update_company(company: str = COMPANY_PATH, *, payload: CompanyInput, contributor=Depends(require_contributor)):
    """Altera o perfil. Mande só o que quer mudar. Quem ainda é Iniciante recebe 202: vai para a votação."""
    company_id = company_id_or_404(company)
    check_company_changes(company_id, payload)
    if not can_write_directly(contributor):
        return send_to_review("update_company", company_id, payload, contributor)
    return apply_company_changes(company_id, payload, contributor)


def check_new_company(payload):
    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Informe o nome da empresa.")
    return clean_company_input(payload, payload.model_fields_set)


def check_company_changes(company_id, payload):
    company_exists = result_or_error(CompanyDB().exists("companies", {"id": company_id}), 500)
    if not company_exists:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    sent_fields = payload.model_fields_set - {"reason"}
    if "name" in sent_fields and not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="O nome da empresa não pode ficar vazio.")
    return clean_company_input(payload, sent_fields)


def apply_new_company(_target_id, payload, contributor):
    """Grava a empresa. Chamado direto pela rota ou quando a votação aprova."""
    data, brands = check_new_company(payload)
    companies = CompanyDB()
    company_id = result_or_error(companies.create(data, brands or [], contributor["username"], payload.reason))

    register_contribution(contributor, [field for field in data if data[field] is not None] + (["brands"] if brands else []))
    return result_or_error(companies.get_full(company_id), 500)


def apply_company_changes(company_id, payload, contributor):
    """Grava a alteração. Chamado direto pela rota ou quando a votação aprova."""
    changes, brands = check_company_changes(company_id, payload)
    companies = CompanyDB()
    changed_fields = result_or_error(companies.update(company_id, changes, brands, contributor["username"], payload.reason))

    register_contribution(contributor, changed_fields)
    return {"changed_fields": changed_fields, "company": result_or_error(companies.get_full(company_id), 500)}


def clean_company_input(payload, sent_fields):
    """
    Valida e converte os campos enviados para as colunas do banco. Só entra o que foi enviado.
    Devolve (dados, marcas ou None se as marcas não foram enviadas).
    """
    data = {}
    errors = []

    def text_or_none(value):
        value = " ".join(str(value).split()) if value is not None else ""
        return value or None

    for field in ("name", "legal_name", "description", "address", "city", "source"):
        if field in sent_fields:
            data[field] = text_or_none(getattr(payload, field))

    checks = {
        "cnpj": (clean_cnpj, "CNPJ inválido: confira os dígitos."),
        "website": (clean_website, "Site inválido: use um endereço começando com http:// ou https://."),
        "phone": (clean_phone, "Telefone inválido: use só números, espaço, parênteses, + e hífen."),
        "uf": (clean_uf, "UF inválida."),
    }
    for field, (clean, error_message) in checks.items():
        if field in sent_fields:
            value = text_or_none(getattr(payload, field))
            data[field] = clean(value) if value else None
            if value and data[field] is None:
                errors.append(error_message)

    brands = None
    if "brands" in sent_fields:
        brands = []
        for brand in payload.brands or []:
            brand = " ".join(str(brand).split())[:120]
            if brand and brand.casefold() not in [already.casefold() for already in brands]:
                brands.append(brand)

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))

    return data, brands
