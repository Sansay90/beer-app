# Агент brewapp: связь с пивоварней (Tuya, домашняя сеть) и с сервисом (WebSocket).
# Ключи (devices.json) в образ не входят — подключаются томом; память агента — в /data (см. ../service/compose.yaml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Moscow \
    BREWAPP_DEVICES=/config/devices.json \
    BREWAPP_STATE=/data/state.json

# tzdata — чтобы время в журнале агента было местным, а не UTC
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent ./agent

RUN useradd --create-home --uid 1000 brew
USER brew

CMD ["python", "-m", "agent"]
