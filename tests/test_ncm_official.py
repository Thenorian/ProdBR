from datetime import date

from app.database import PublicSession
from app.ncm_official import apply, parse, source_label

DATA = {
    "Data_Ultima_Atualizacao_NCM": "Vigente em 08/10/2026",
    "Ato": "Resolução Gecex nº 926/2026",
    "Nomenclaturas": [
        {"Codigo": "23", "Descricao": "Resíduos e desperdícios das indústrias alimentares.", "Data_Fim": "31/12/9999"},
        {"Codigo": "23.09", "Descricao": "Preparações do tipo utilizado na alimentação de animais.", "Data_Fim": "31/12/9999"},
        {"Codigo": "2309.10.00", "Descricao": "- Alimentos para cães ou gatos, acondicionados para venda a retalho", "Data_Fim": "31/12/9999"},
        {"Codigo": "2309.90", "Descricao": "- Outras", "Data_Fim": "31/12/9999"},
        {"Codigo": "2309.90.10", "Descricao": "Preparações destinadas a fornecer ao animal a totalidade dos elementos", "Data_Fim": "31/12/9999"},
        {"Codigo": "2309.90.99", "Descricao": "Código extinto", "Data_Fim": "31/12/2020"},
        {"Codigo": "22.03", "Descricao": "Cervejas de malte.", "Data_Fim": "31/12/9999"},
        {"Codigo": "2203.00.00", "Descricao": "Cervejas de malte.", "Data_Fim": "31/12/9999"},
    ],
}


def test_parse_builds_hierarchy_and_skips_expired():
    items = {i["ncm"]: i for i in parse(DATA, today=date(2026, 10, 8))}
    assert set(items) == {"23091000", "23099010", "22030000"}
    assert items["23091000"]["description"] == (
        "Preparações do tipo utilizado na alimentação de animais > "
        "Alimentos para cães ou gatos, acondicionados para venda a retalho"
    )
    assert items["23099010"]["description"].startswith(
        "Preparações do tipo utilizado na alimentação de animais > Outras > Preparações destinadas"
    )
    assert items["22030000"]["description"] == "Cervejas de malte"  # sem repetir posicao = subitem
    assert items["23091000"]["chapter"] == "23"


def test_apply_is_idempotent_and_ncm_route_works(client):
    db = PublicSession()
    try:
        first = apply(db, parse(DATA, today=date(2026, 10, 8)), source_label(DATA))
        second = apply(db, parse(DATA, today=date(2026, 10, 8)), source_label(DATA))
    finally:
        db.close()
    assert first == {"criados": 3, "atualizados": 0, "iguais": 0}
    assert second == {"criados": 0, "atualizados": 0, "iguais": 3}

    res = client.get("/ncm/23091000")
    assert res.status_code == 200
    assert "cães ou gatos" in res.json()["description"]
    assert res.json()["source"] == "Tabela NCM oficial (Siscomex) - Resolução Gecex nº 926/2026"
    assert [n["ncm"] for n in client.get("/ncm", params={"q": "gatos"}).json()] == ["23091000"]
