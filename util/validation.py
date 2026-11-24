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


CNPJ_FIRST_CHECK_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
CNPJ_SECOND_CHECK_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
WEBSITE_FORMAT = re.compile(r"^https?://[^\s<>\"']{3,240}$", re.IGNORECASE)
PHONE_FORMAT = re.compile(r"^[0-9 ()+\-]{8,30}$")


def clean_cnpj(cnpj):
    """
    CNPJ só com os 14 dígitos, conferindo os dois dígitos verificadores.

        clean_cnpj("11.222.333/0001-81")  ->  "11222333000181"
        clean_cnpj("11.222.333/0001-82")  ->  None  (dígito verificador errado)
    """
    digits = "".join(character for character in str(cnpj or "") if character.isdigit())
    if len(digits) != 14 or digits == digits[0] * 14:
        return None

    first_check_digit = cnpj_check_digit(digits[:12], CNPJ_FIRST_CHECK_WEIGHTS)
    second_check_digit = cnpj_check_digit(digits[:12] + str(first_check_digit), CNPJ_SECOND_CHECK_WEIGHTS)
    if digits[12:] != f"{first_check_digit}{second_check_digit}":
        return None

    return digits


def cnpj_check_digit(digits, weights):
    remainder = sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def clean_website(website):
    """
    Só endereço http ou https. Isso impede que um link "javascript:..." vire código
    rodando na página de quem clicar.

        clean_website("https://www.nestle.com.br")  ->  "https://www.nestle.com.br"
        clean_website("javascript:alert(1)")        ->  None
    """
    website = str(website or "").strip()
    return website if WEBSITE_FORMAT.match(website) else None


def clean_phone(phone):
    """ clean_phone("(11) 3456-7890") -> "(11) 3456-7890". Só dígitos, espaço, parênteses, + e hífen. """
    phone = " ".join(str(phone or "").split())
    return phone if PHONE_FORMAT.match(phone) else None
