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
from database.company import ESTABLISHMENT_FIELDS, CompanyDB
from database.contributor import can_write_directly
from database.product import ProductDB
from database.revision import RevisionDB
from util.validation import (
    clean_cnpj, clean_ibge_city_code, clean_phone, clean_state_registration, clean_uf, clean_website, clean_zip_code,
)

router = APIRouter(tags=["Empresas"])

MAXIMUM_LIST_SIZE = 100


class EstablishmentInput(BaseModel):
    """Um CNPJ da empresa (matriz ou filial), com a razão social e o endereço separado como na NF-e."""
    cnpj: str | None = Field(None, max_length=18, description="Numérico ou alfanumérico, com ou sem pontuação.")
    legal_name: str | None = Field(None, max_length=200, description="Razão social deste CNPJ.")
    state_registration: str | None = Field(None, max_length=20, description='Inscrição estadual, ou "ISENTO".')
    is_headquarters: bool = Field(False, description="true na matriz. Sem nenhuma marcada, a primeira da lista é a matriz.")
    zip_code: str | None = Field(None, max_length=9, description="CEP. Ex: 01310-100")
    street: str | None = Field(None, max_length=200, description="Logradouro. Ex: Avenida Paulista")
    number: str | None = Field(None, max_length=20, description='Número. Ex: 1000 ou "S/N"')
    complement: str | None = Field(None, max_length=120)
    district: str | None = Field(None, max_length=120, description="Bairro.")
    city: str | None = Field(None, max_length=120)
    city_ibge_code: str | None = Field(None, max_length=7, description="Código IBGE do município (7 dígitos), usado na NF-e.")
    uf: str | None = None


class PhoneInput(BaseModel):
    phone: str = Field(..., max_length=30)
    description: str | None = Field(None, max_length=60, description="Para que serve. Ex: SAC, Suporte, Comercial")


class CompanyInput(BaseModel):
    """
    Na criação, só name é obrigatório. Na edição, mande só o que quer mudar (null apaga o campo).
    brands, establishments e phones são listas: a lista enviada substitui a anterior inteira.

    cnpj, legal_name, address, city, uf e phone são da primeira versão da API e continuam aceitos:
    mexem na matriz e no primeiro telefone. Prefira establishments e phones.
    """
    name: str | None = Field(None, max_length=200, description="Nome como a empresa é conhecida. Ex: Nestlé")
    description: str | None = Field(None, max_length=2000)
    website: str | None = Field(None, max_length=255, description="Começando com http:// ou https://")
    brands: list[str] | None = Field(
        None, max_length=MAXIMUM_LIST_SIZE, description='Marcas da empresa. Ex: ["Nescau", "Ninho"]',
    )
    establishments: list[EstablishmentInput] | None = Field(
        None, max_length=MAXIMUM_LIST_SIZE, description="CNPJs da empresa (matriz e filiais), cada um com razão social e endereço.",
    )
    phones: list[PhoneInput] | None = Field(None, max_length=MAXIMUM_LIST_SIZE, description="Telefones com a descrição de cada um.")
    source: str | None = Field(None, max_length=255, description="De onde veio a informação.")
    legal_name: str | None = Field(None, max_length=200, description="Primeira versão: razão social da matriz.")
    cnpj: str | None = Field(None, max_length=18, description="Primeira versão: CNPJ da matriz.")
    phone: str | None = Field(None, max_length=30, description="Primeira versão: primeiro telefone.")
    address: str | None = Field(None, max_length=255, description="Primeira versão: logradouro da matriz.")
    city: str | None = Field(None, max_length=120, description="Primeira versão: cidade da matriz.")
    uf: str | None = Field(None, description="Primeira versão: UF da matriz.")
    reason: str = Field(..., min_length=3, max_length=300, description="Motivo da alteração, como uma mensagem de commit.")


FIRST_VERSION_HEADQUARTERS_FIELDS = {"cnpj": "cnpj", "legal_name": "legal_name", "address": "street", "city": "city", "uf": "uf"}


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
    return clean_company_input(payload, payload.model_fields_set, current_establishments=[], current_phones=[])


def check_company_changes(company_id, payload):
    company_exists = result_or_error(CompanyDB().exists("companies", {"id": company_id}), 500)
    if not company_exists:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    sent_fields = payload.model_fields_set - {"reason"}
    if "name" in sent_fields and not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="O nome da empresa não pode ficar vazio.")

    companies = CompanyDB()
    current_establishments = result_or_error(companies._list_establishments_as_saved(company_id), 500)
    current_phones = result_or_error(companies.list_phones(company_id), 500)
    return clean_company_input(payload, sent_fields, current_establishments, current_phones)


def apply_new_company(_target_id, payload, contributor):
    """Grava a empresa. Chamado direto pela rota ou quando a votação aprova."""
    data, brands, establishments, phones = check_new_company(payload)
    companies = CompanyDB()
    company_id = result_or_error(
        companies.create(data, brands or [], establishments or [], phones or [], contributor["username"], payload.reason)
    )

    filled_lists = [field for field, values in (("brands", brands), ("establishments", establishments), ("phones", phones)) if values]
    register_contribution(contributor, [field for field in data if data[field] is not None] + filled_lists)
    return result_or_error(companies.get_full(company_id), 500)


def apply_company_changes(company_id, payload, contributor):
    """Grava a alteração. Chamado direto pela rota ou quando a votação aprova."""
    changes, brands, establishments, phones = check_company_changes(company_id, payload)
    companies = CompanyDB()
    changed_fields = result_or_error(
        companies.update(company_id, changes, brands, establishments, phones, contributor["username"], payload.reason)
    )

    register_contribution(contributor, changed_fields)
    return {"changed_fields": changed_fields, "company": result_or_error(companies.get_full(company_id), 500)}


def text_or_none(value):
    value = " ".join(str(value).split()) if value is not None else ""
    return value or None


def clean_company_input(payload, sent_fields, current_establishments, current_phones):
    """
    Valida e converte os campos enviados. Só entra o que foi enviado.
    Devolve (dados da empresa, marcas, estabelecimentos, telefones); cada lista é None se não foi enviada.
    """
    data = {}
    errors = []

    for field in ("name", "description", "source"):
        if field in sent_fields:
            data[field] = text_or_none(getattr(payload, field))

    if "website" in sent_fields:
        website = text_or_none(payload.website)
        data["website"] = clean_website(website) if website else None
        if website and data["website"] is None:
            errors.append("Site inválido: use um endereço começando com http:// ou https://.")

    brands = None
    if "brands" in sent_fields:
        brands = []
        for brand in payload.brands or []:
            brand = " ".join(str(brand).split())[:120]
            if brand and brand.casefold() not in [already.casefold() for already in brands]:
                brands.append(brand)

    establishments = None
    if "establishments" in sent_fields:
        establishments = [clean_establishment(item, position, errors) for position, item in enumerate(payload.establishments or [])]
        mark_headquarters(establishments, errors)
    elif sent_fields & FIRST_VERSION_HEADQUARTERS_FIELDS.keys():
        establishments = headquarters_with_first_version_fields(payload, sent_fields, current_establishments, errors)

    phones = None
    if "phones" in sent_fields:
        phones = [clean_phone_item(item.phone, item.description, position, errors) for position, item in enumerate(payload.phones or [])]
    elif "phone" in sent_fields:
        phones = [dict(phone) for phone in current_phones]
        new_number = text_or_none(payload.phone)
        if new_number is None:
            phones = phones[1:]
        elif phones:
            phones[0] = clean_phone_item(new_number, phones[0]["description"], 0, errors)
        else:
            phones = [clean_phone_item(new_number, None, 0, errors)]

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))

    return data, brands, establishments, phones


def clean_establishment(item, position, errors):
    """Confere um estabelecimento. Os erros vão para a lista, dizendo de qual linha são."""
    line = f"Estabelecimento {position + 1}:"
    establishment = {
        "legal_name": text_or_none(item.legal_name),
        "is_headquarters": int(item.is_headquarters),
        "street": text_or_none(item.street),
        "number": text_or_none(item.number),
        "complement": text_or_none(item.complement),
        "district": text_or_none(item.district),
        "city": text_or_none(item.city),
    }

    checks = (
        ("cnpj", item.cnpj, clean_cnpj, "CNPJ inválido, confira os dígitos."),
        ("state_registration", item.state_registration, clean_state_registration, "inscrição estadual inválida."),
        ("zip_code", item.zip_code, clean_zip_code, "CEP inválido, use 8 dígitos."),
        ("city_ibge_code", item.city_ibge_code, clean_ibge_city_code, "código IBGE do município inválido, use 7 dígitos."),
        ("uf", item.uf, clean_uf, "UF inválida."),
    )
    for field, value, clean, error_message in checks:
        value = text_or_none(value)
        establishment[field] = clean(value) if value else None
        if value and establishment[field] is None:
            errors.append(f"{line} {error_message}")

    if not any(establishment[field] for field in ("cnpj", "legal_name", "zip_code", "street", "city")):
        errors.append(f"{line} preencha ao menos o CNPJ, a razão social ou o endereço.")
    return establishment


def mark_headquarters(establishments, errors):
    """Uma matriz só. Sem nenhuma marcada, a primeira da lista vira a matriz."""
    headquarters_count = sum(establishment["is_headquarters"] for establishment in establishments)
    if headquarters_count > 1:
        errors.append("Marque só um estabelecimento como matriz.")
    elif establishments and headquarters_count == 0:
        establishments[0]["is_headquarters"] = 1


def headquarters_with_first_version_fields(payload, sent_fields, current_establishments, errors):
    """
    Primeira versão da API: cnpj, legal_name, address, city e uf soltos na empresa.
    Eles alteram a matriz (ou criam uma, se a empresa ainda não tem estabelecimento).
    """
    establishments = [dict(establishment) for establishment in current_establishments]
    headquarters = next((item for item in establishments if item["is_headquarters"]), establishments[0] if establishments else None)
    if headquarters is None:
        headquarters = {field: None for field in ESTABLISHMENT_FIELDS}
        headquarters["is_headquarters"] = 1
        establishments.append(headquarters)

    for old_field, field in FIRST_VERSION_HEADQUARTERS_FIELDS.items():
        if old_field not in sent_fields:
            continue
        value = text_or_none(getattr(payload, old_field))
        if old_field == "cnpj":
            headquarters["cnpj"] = clean_cnpj(value) if value else None
            if value and headquarters["cnpj"] is None:
                errors.append("CNPJ inválido: confira os dígitos.")
        elif old_field == "uf":
            headquarters["uf"] = clean_uf(value) if value else None
            if value and headquarters["uf"] is None:
                errors.append("UF inválida.")
        else:
            headquarters[field] = value
    return establishments


def clean_phone_item(number, description, position, errors):
    phone = clean_phone(number)
    if phone is None:
        errors.append(f"Telefone {position + 1}: use só números, espaço, parênteses, + e hífen.")
    return {"phone": phone, "description": text_or_none(description)}
