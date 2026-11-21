"""
Limite de requisições por IP, para um robô não derrubar a API.
Fica na memória: zera quando o app reinicia, o que é suficiente aqui.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

READ_LIMIT_PER_MINUTE = 120
WRITE_LIMIT_PER_MINUTE = 20
NEW_CONTRIBUTOR_LIMIT_PER_HOUR = 5

request_times_by_key = defaultdict(deque)


def client_ip(request):
    """
    Em produção o caminho é Cloudflare -> nginx -> app. O IP de quem chegou no nginx é do
    Cloudflare (o mesmo para muita gente), então vale o IP real que o Cloudflare manda no
    CF-Connecting-IP; sem Cloudflare, o X-Real-IP do nginx; sem os dois, a conexão direta.
    """
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-real-ip")
        or (request.client.host if request.client else "unknown")
    )


def is_internal_request(request):
    """Requisição de 127.0.0.1 sem cabeçalho de proxy é o próprio site do ProdBR montando uma página."""
    came_through_proxy = "x-real-ip" in request.headers or "cf-connecting-ip" in request.headers
    return not came_through_proxy and request.client is not None and request.client.host == "127.0.0.1"


def check_limit(request, group, limit, window_in_seconds):
    if is_internal_request(request):
        return

    key = f"{group}:{client_ip(request)}"
    now = time.monotonic()
    request_times = request_times_by_key[key]

    while request_times and request_times[0] <= now - window_in_seconds:
        request_times.popleft()

    if len(request_times) >= limit:
        raise HTTPException(status_code=429, detail="Muitas requisições. Espere um pouco e tente de novo.")

    request_times.append(now)


def limit_reads(request: Request):
    check_limit(request, "read", READ_LIMIT_PER_MINUTE, 60)


def limit_writes(request: Request):
    check_limit(request, "write", WRITE_LIMIT_PER_MINUTE, 60)


def limit_new_contributors(request: Request):
    check_limit(request, "new_contributor", NEW_CONTRIBUTOR_LIMIT_PER_HOUR, 3600)


DOWNLOAD_LIMIT_PER_HOUR = 5


def limit_downloads(request: Request):
    check_limit(request, "download", DOWNLOAD_LIMIT_PER_HOUR, 3600)
