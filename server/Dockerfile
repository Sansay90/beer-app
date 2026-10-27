# Посредник brewapp: HTTP API + SSE для интерфейса, локальная связь с пивоварней по Tuya.
# Данные — в Postgres (сервис db в compose.yaml, адрес — DATABASE_URL); миграции применяются при старте.
# Ключи (devices.json) в образ не входят — подключаются томом, см. compose.yaml.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Moscow \
    BRIDGE_HOST=0.0.0.0 \
    BRIDGE_PORT=8000 \
    BREWAPP_DEVICES=/config/devices.json

# tzdata — чтобы время в журналах варки было местным, а не UTC
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY bridge ./bridge

RUN useradd --create-home --uid 1000 brew
USER brew

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/limits', timeout=3)"]

CMD ["python", "-m", "bridge.server"]
