FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# db/schema.sql is mounted at /app/db by docker-compose (single source of truth
# for the initial migration). The migration resolves it relative to repo root.
EXPOSE 8000
# Shell form so $PORT expands: PaaS hosts (Railway, Render, Fly) inject the port
# they route to and expect the process to bind it. Falls back to 8000 locally.
CMD uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
