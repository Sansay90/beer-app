# Образ для сервера: сервис и собранный интерфейс в одном контейнере — сервис сам раздаёт его на корне.
# Собирается в GitHub Actions (.github/workflows/deploy.yml) из корня репозитория:
#   docker build -f deploy/Dockerfile .
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run generate

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Moscow \
    SERVICE_HOST=0.0.0.0 \
    SERVICE_PORT=8000 \
    BREWAPP_WEB_DIR=/app/web

# tzdata — чтобы время в журналах было местным, а не UTC
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY service/requirements.txt .
RUN pip install -r requirements.txt

COPY service/alembic.ini ./
COPY service/migrations ./migrations
COPY service/app ./app
COPY --from=web /web/.output/public ./web

RUN useradd --create-home --uid 1000 brew
USER brew

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

CMD ["python", "-m", "app.server"]
