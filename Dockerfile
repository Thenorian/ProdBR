FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

VOLUME ["/app/data"]
ENV PUBLIC_DATABASE_URL=sqlite:////app/data/public.sqlite3
ENV COMMUNITY_DATABASE_URL=sqlite:////app/data/community.sqlite3

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
