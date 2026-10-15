#!/bin/bash
# Pruebas dentro de las imágenes nuevas, antes del corte. Uso: probar-imagenes.sh <etiqueta> <arbol-fuente>
# Corre con el usuario real de cada imagen (no root), así también fallan permisos de archivos de /app.
# Usa un PostgreSQL desechable (nombre único) en 127.0.0.1:15439 compartiendo su red.
# pytest se instala solo en el contenedor efímero (--user), no en las imágenes.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
ETIQUETA=${1:?Uso: probar-imagenes.sh <etiqueta> <arbol-fuente>}
FUENTE=${2:?Uso: probar-imagenes.sh <etiqueta> <arbol-fuente>}
pg="cl-pruebas-pg-$(sufijo)"
trap 'docker rm -f "$pg" >/dev/null 2>&1 || true' EXIT

log "importación desde /app con el usuario de cada imagen"
docker run --rm --network none -e DATABASE_URL=postgresql+asyncpg://x:y@127.0.0.1/x \
  --entrypoint python "$IMAGEN_PREFIJO-worker:$ETIQUETA" -c \
  "import worker.run, worker.init_db, pipelines.communitylab.componentes_gemini" \
  || fallar "el worker no importa desde /app"
docker run --rm --network none --entrypoint python "$IMAGEN_PREFIJO-discord:$ETIQUETA" -c \
  "import discord_reader.__main__, bot_discord.__main__, community_processor.integrated, pipelines.communitylab.puente_discord" \
  || fallar "los servicios de Discord no importan desde /app"
docker run --rm --network none -e DATABASE_URL=postgresql+asyncpg://x:y@127.0.0.1/x --entrypoint python \
  "$IMAGEN_PREFIJO-api:$ETIQUETA" -c "import backend.app.main" || fallar "la API no importa desde /app"

docker run -d --name "$pg" -e POSTGRES_USER=worker -e POSTGRES_PASSWORD=local_test_only \
  -e POSTGRES_DB=worker_local "${POSTGRES_IMAGE:-postgres:16-alpine}" -c port=15439 >/dev/null
for _ in $(seq 60); do docker exec "$pg" pg_isready -p 15439 -U worker >/dev/null 2>&1 && break; sleep 1; done
sleep 2
url=postgresql://worker:local_test_only@127.0.0.1:15439/worker_local
comun=(--rm --network "container:$pg" -v "$FUENTE:/src:ro" -w /src -e PYTHONDONTWRITEBYTECODE=1
       -e PYTHONIOENCODING=utf-8 -e LANGSMITH_TRACING=false -e LANGCHAIN_TRACING_V2=false)
instalar="pip install --user -q --no-warn-script-location pytest==9.1.1"

log "pruebas worker/grafo en $IMAGEN_PREFIJO-worker:$ETIQUETA"
docker run "${comun[@]}" -e WORKER_TEST_DATABASE_URL="$url" -e DATABASE_URL="${url/postgresql:/postgresql+asyncpg:}" \
  --entrypoint sh "$IMAGEN_PREFIJO-worker:$ETIQUETA" -c "$instalar && python -m worker.init_db \
  && python -B -m pytest -q -p no:cacheprovider --import-mode=importlib worker/tests/test_worker.py worker/tests/test_ia_contract.py \
  && python -B -m unittest discover -s pipelines/communitylab/tests" || fallar "pruebas del worker"

log "pruebas Discord en $IMAGEN_PREFIJO-discord:$ETIQUETA"
docker run "${comun[@]}" --entrypoint sh "$IMAGEN_PREFIJO-discord:$ETIQUETA" -c "$instalar \
  && python -B integrations/discord/processor/tools/validate.py \
  && cd integrations/discord/reader && python -B -m unittest discover -s tests" || fallar "pruebas de Discord"
log "pruebas de imágenes $ETIQUETA aprobadas"
