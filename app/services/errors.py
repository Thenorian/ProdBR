"""Erros de regra de negócio. Os serviços levantam estes erros sem saber de
HTTP; app/main.py converte cada um no status certo (ver ERROR_STATUS)."""


class DomainError(Exception):
    """Base - a mensagem vai como está pro `detail` da resposta."""


class NotFoundError(DomainError):
    """Registro pedido não existe (404)."""


class InvalidDataError(DomainError, ValueError):
    """Dado recebido não faz sentido pra regra de negócio (400)."""


class ConflictError(DomainError):
    """Já existe / está em uso (409)."""


ERROR_STATUS = {NotFoundError: 404, InvalidDataError: 400, ConflictError: 409}
