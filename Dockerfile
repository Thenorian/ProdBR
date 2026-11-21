FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY website ./website
COPY database ./database
COPY docs ./docs
COPY util ./util
COPY scripts ./scripts
COPY importers ./importers
COPY reference_data ./reference_data
COPY server.py LICENSE DATA_LICENSE ./

# Os bancos ficam no volume e sobrevivem à troca de container.
# public.sqlite3 e community.sqlite3 são os da versão antiga: copiados uma vez para os novos ao iniciar.
VOLUME ["/app/data"]
ENV DB_PATH=/app/data/prodbr.sqlite3
ENV COMMUNITY_DB_PATH=/app/data/prodbr_community.sqlite3
ENV LEGACY_PUBLIC_DB_PATH=/app/data/public.sqlite3
ENV LEGACY_COMMUNITY_DB_PATH=/app/data/community.sqlite3

EXPOSE 8000

# O container só é acessado pelo nginx, então os cabeçalhos dele (https e IP real) são confiáveis.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
