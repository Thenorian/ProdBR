import pytest

from app.packaging import parse_package


@pytest.mark.parametrize(
    "text,expected",
    [
        ("15 kg", {"net_quantity": 15.0, "net_unit": "kg"}),
        ("15kg", {"net_quantity": 15.0, "net_unit": "kg"}),
        ("15 KG", {"net_quantity": 15.0, "net_unit": "kg"}),
        ("10,1 kg", {"net_quantity": 10.1, "net_unit": "kg"}),
        ("10,1kg", {"net_quantity": 10.1, "net_unit": "kg"}),
        ("2.5 Kg", {"net_quantity": 2.5, "net_unit": "kg"}),
        ("100 g", {"net_quantity": 100.0, "net_unit": "g"}),
        ("500gr", {"net_quantity": 500.0, "net_unit": "g"}),
        ("Pacote 15 kg", {"net_quantity": 15.0, "net_unit": "kg"}),
        ("Lata 350ml", {"net_quantity": 350.0, "net_unit": "ml"}),
        ("Garrafa 2 Litros", {"net_quantity": 2.0, "net_unit": "l"}),
        ("1 lt", {"net_quantity": 1.0, "net_unit": "l"}),
        ("6x350ml", {"units_per_pack": 6, "net_quantity": 350.0, "net_unit": "ml"}),
        ("Fardo 12 x 1L", {"units_per_pack": 12, "net_quantity": 1.0, "net_unit": "l"}),
        ("Cx c/ 12 un", {"units_per_pack": 12, "net_quantity": 12.0, "net_unit": "un"}),
        ("Caixa com 24 unidades", {"units_per_pack": 24, "net_quantity": 24.0, "net_unit": "un"}),
        ("Display c/ 10 de 100 g", {"net_quantity": 100.0, "net_unit": "g", "units_per_pack": 10}),
    ],
)
def test_parses_common_formats(text, expected):
    assert parse_package(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "Embalagem econômica",  # sem medida
        "1 kg + 200 g grátis",  # duas medidas diferentes
        "1.000 g",  # ponto ambiguo (milhar ou decimal)
        "6x350ml + 2x1l",  # duas embalagens multiplas
        "15 kgf",  # unidade desconhecida
    ],
)
def test_unsure_returns_empty(text):
    assert parse_package(text) == {}
