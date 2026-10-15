# Imagen única para los servicios de Discord: lector, puente y bot (comandos distintos en Compose).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false \
    PYTHONPATH=/app:/app/integrations/discord/reader:/app/integrations/discord/bot:/app/integrations/discord/processor
WORKDIR /app

COPY integrations/discord/requirements-servicios.lock.txt ./integrations/discord/requirements-servicios.lock.txt
RUN pip install --no-cache-dir -r integrations/discord/requirements-servicios.lock.txt \
    && useradd --uid 10002 --create-home discord \
    && mkdir -p /data/bandeja /data/puente /data/bot \
    && chown -R discord:discord /data

COPY pipelines ./pipelines
COPY integrations/discord/reader/discord_reader ./integrations/discord/reader/discord_reader
COPY integrations/discord/bot/bot_discord ./integrations/discord/bot/bot_discord
COPY integrations/discord/processor/community_processor ./integrations/discord/processor/community_processor

USER discord
