from fastapi import HTTPException

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


def page_limits(limit, offset):
    """Limita o tamanho da página: no máximo 50 itens por requisição."""
    return max(1, min(int(limit), MAX_PAGE_SIZE)), max(0, int(offset))


def result_or_error(result, status_code=400):
    """
    Os métodos de banco devolvem (True, resultado) ou (False, erro).
    Aqui o erro vira uma resposta HTTP e o resultado segue em frente.
    """
    ok, value = result
    if not ok:
        raise HTTPException(status_code=status_code, detail=value)
    return value


def found_or_404(value, message):
    if value is None:
        raise HTTPException(status_code=404, detail=message)
    return value
