"""
Regras de validação usadas pela API e pelas importações.
Cada função devolve o valor já limpo, ou None se o valor não for válido.
"""
import re

BRAZILIAN_STATES = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
)

TAX_REGIMES = ("simples_nacional", "lucro_presumido", "lucro_real")

BARCODE_LENGTHS = (8, 12, 13, 14)

ONLY_DIGITS = re.compile(r"^[0-9]+$")
USERNAME_FORMAT = re.compile(r"^[a-zA-Z0-9_.-]{3,40}$")


def clean_barcode(barcode):
    """
    Aceita GTIN-8, 12, 13 ou 14 com o dígito verificador certo.

        clean_barcode(" 7891000100103 ")  ->  "7891000100103"
        clean_barcode("7891000100104")    ->  None  (dígito verificador errado)
    """
    barcode = str(barcode or "").strip()

    if not ONLY_DIGITS.match(barcode) or len(barcode) not in BARCODE_LENGTHS:
        return None

    if calculate_barcode_check_digit(barcode[:-1]) != int(barcode[-1]):
        return None

    return barcode


def calculate_barcode_check_digit(digits_without_check_digit):
    """
    Cálculo oficial do GS1: da direita para a esquerda, os dígitos são multiplicados
    alternadamente por 3 e por 1; o verificador é o que falta para chegar na próxima dezena.
    """
    total = 0
    for position_from_right, digit in enumerate(reversed(digits_without_check_digit)):
        weight = 3 if position_from_right % 2 == 0 else 1
        total += int(digit) * weight

    return (10 - total % 10) % 10


def clean_ncm(ncm):
    """
    NCM com 8 dígitos. Aceita com ou sem pontos.

        clean_ncm("2203.00.00")  ->  "22030000"
    """
    ncm = str(ncm or "").replace(".", "").strip()
    if ONLY_DIGITS.match(ncm) and len(ncm) == 8:
        return ncm
    return None


def clean_cest(cest):
    """CEST com 7 dígitos. Aceita com ou sem pontos. Ex: "03.021.00" -> "0302100"."""
    cest = str(cest or "").replace(".", "").strip()
    if ONLY_DIGITS.match(cest) and len(cest) == 7:
        return cest
    return None


def clean_uf(uf):
    uf = str(uf or "").strip().upper()
    return uf if uf in BRAZILIAN_STATES else None


def clean_tax_regime(tax_regime):
    tax_regime = str(tax_regime or "").strip().lower()
    return tax_regime if tax_regime in TAX_REGIMES else None


def clean_username(username):
    """Letras, números, ponto, hífen e sublinhado, de 3 a 40 caracteres. Igual a um usuário do Git."""
    username = str(username or "").strip()
    return username if USERNAME_FORMAT.match(username) else None


def clean_category_path(category_path):
    """
    Categoria em árvore, escrita com ">" entre os níveis.

        clean_category_path(" Bebidas >  Cervejas ")  ->  ["Bebidas", "Cervejas"]
    """
    names = [" ".join(name.split()) for name in str(category_path or "").split(">")]
    names = [name[:150] for name in names if name]
    return names or None
