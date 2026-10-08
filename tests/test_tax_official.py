from datetime import date

from app.database import PublicSession
from app.models_public import FiscalRule
from app.tax_official import _short_act, apply, parse_tec, parse_tipi, source_label, tec_url

TIPI = {
    "Tabela Completa": [
        ["Atualizações:\nDecreto nº 11.182, de 24 de agosto de 2022\nAto Declaratório Executivo RFB nº 1, de 30 de janeiro de 2026 (Retificado)"],
        ["NCM ", "EX", "DESCRIÇÃO ", "ALÍQUOTA (%)"],
        ["0101.21.00", None, "-- Reprodutores de raça pura ", "NT"],
        ["2309.10.00", None, "- Alimentos para cães ou gatos ", 6.5],
        ["2309.90.10", None, "Preparações ... completos ", 0.0],
        ["2309.90.10", 1.0, "Para cães e gatos", 6.5],
        ["2402.20.00", None, "- Cigarros ", 300.0],
    ]
}
TEC = {
    "Anexo I - TEC": [
        ["* Atualizado até Resolução Gecex nº 926, de 24 de junho de 2026"],
        ["2309.10.00", "-Alimentos para cães ou gatos", 12.6],
        ["2309.90.10", "Preparações", 7.2],
        ["8517.13.00", "--Smartphones", "16BIT"],
    ],
    "Anexo II - Diferentes da TEC": [
        ["NCM", "Descrição", "TEC (%)", "BIT/BK", None, "Alíquota aplicada (%) "],
        ["8517.13.00", "--Smartphones", 16, "BIT", None, 0],
    ],
}


def test_parse_tipi_handles_nt_zero_and_ex():
    rates, exes, act = parse_tipi(TIPI)
    assert rates == {"01012100": None, "23091000": 6.5, "23099010": 0.0, "24022000": 300.0}
    assert exes == {"23099010": ["Ex 01 (Para cães e gatos): 6,5%"]}
    assert act == "Ato Declaratório Executivo RFB nº 1/2026"


def test_parse_tec_applies_brazilian_exceptions():
    rates, act = parse_tec(TEC)
    assert rates == {"23091000": 12.6, "23099010": 7.2, "85171300": 0.0}
    assert act == "Resolução Gecex nº 926/2026"
    assert _short_act("*Atualizado até a Resolução Gecex nº 963, de 2 de outubro de 2026") == "Resolução Gecex nº 963/2026"


def test_tec_url_found_in_page():
    html = '<a href="https://www.gov.br/x/05-10-2026-anexos-i-a-x-resolucao-gecex-272-21.xlsx">TEC</a>'
    assert tec_url(html).endswith("anexos-i-a-x-resolucao-gecex-272-21.xlsx")
    assert tec_url("<html></html>") is None


def test_apply_versions_rates_and_merges_with_state_rule(client, trusted_headers):
    tipi, exes, tipi_act = parse_tipi(TIPI)
    tec, tec_act = parse_tec(TEC)
    source = source_label(tipi_act, tec_act)
    db = PublicSession()
    try:
        first = apply(db, tipi, exes, tec, source, today=date(2026, 1, 1))
        again = apply(db, tipi, exes, tec, source, today=date(2026, 1, 2))
        changed = apply(db, {**tipi, "23091000": 5.0}, exes, tec, source, today=date(2026, 3, 1))
        history = db.query(FiscalRule).filter(FiscalRule.ncm == "23091000").order_by(FiscalRule.valid_from).all()
    finally:
        db.close()
    assert first["criadas"] == 5 and again["iguais"] == 5 and changed["alteradas"] == 1
    assert [(r.ipi_rate, r.valid_until) for r in history] == [(6.5, date(2026, 2, 28)), (5.0, None)]

    nt = client.get("/fiscal-rules", params={"ncm": "01012100"}).json()
    assert nt["ipi_rate"] is None and nt["notes"].startswith("IPI: NT")
    assert client.get("/fiscal-rules", params={"ncm": "24022000"}).json()["ipi_rate"] == 300.0

    # Regra da UF (comunidade) traz o ICMS; o IPI/II oficial continua aparecendo.
    res = client.post(
        "/fiscal-rules",
        json={"ncm": "23091000", "uf": "SP", "icms_rate": 18.0, "valid_from": "2026-01-01", "source": "RICMS/SP", "reason": "Aliquota interna SP"},
        headers=trusted_headers,
    )
    assert res.status_code == 201, res.text
    sp = client.get("/fiscal-rules", params={"ncm": "23091000", "uf": "SP"}).json()
    assert (sp["uf"], sp["icms_rate"], sp["ipi_rate"], sp["ii_rate"]) == ("SP", 18.0, 5.0, 12.6)
    assert sp["source"].startswith("RICMS/SP + Oficial: TIPI")
    rj = client.get("/fiscal-rules", params={"ncm": "23091000", "uf": "RJ"}).json()
    assert rj["icms_rate"] is None and rj["ipi_rate"] == 5.0
