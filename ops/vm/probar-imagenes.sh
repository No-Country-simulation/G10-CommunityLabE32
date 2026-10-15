#!/bin/bash
# Pruebas dentro de las imágenes nuevas, antes del corte. Uso: probar-imagenes.sh <etiqueta> <arbol-fuente>
# Usa un PostgreSQL desechable (nombre único) en 127.0.0.1:15439 compartiendo su red.
# Instala pytest solo en contenedores efímeros (no queda en las imágenes).
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
ETIQUETA=${1:?}; FUENTE=${2:?}
pg="cl-pruebas-pg-$(sufijo)"
trap 'docker rm -f "$pg" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$pg" -e POSTGRES_USER=worker -e POSTGRES_PASSWORD=local_test_only \
  -e POSTGRES_DB=worker_local "${POSTGRES_IMAGE:-postgres:16-alpine}" -c port=15439 >/dev/null
for _ in $(seq 60); do docker exec "$pg" pg_isready -p 15439 -U worker >/dev/null 2>&1 && break; sleep 1; done
sleep 2
url=postgresql://worker:local_test_only@127.0.0.1:15439/worker_local
comun=(--rm --network "container:$pg" -u root -v "$FUENTE:/src:ro" -w /src -e PYTHONDONTWRITEBYTECODE=1
       -e PYTHONIOENCODING=utf-8 -e LANGSMITH_TRACING=false -e LANGCHAIN_TRACING_V2=false)
log "pruebas worker/grafo en communitylab-worker:$ETIQUETA"
docker run "${comun[@]}" -e WORKER_TEST_DATABASE_URL=$url -e DATABASE_URL=${url/postgresql:/postgresql+asyncpg:} \
  --entrypoint sh "communitylab-worker:$ETIQUETA" -c "pip install -q pytest==9.1.1 && python -m worker.init_db \
  && python -B -m pytest -q -p no:cacheprovider --import-mode=importlib worker/tests/test_worker.py worker/tests/test_ia_contract.py \
  && python -B -m unittest discover -s pipelines/communitylab/tests" || fallar "pruebas del worker"
log "pruebas Discord en communitylab-discord:$ETIQUETA"
docker run "${comun[@]}" --entrypoint sh "communitylab-discord:$ETIQUETA" -c "pip install -q pytest==9.1.1 \
  && python -B integrations/discord/processor/tools/validate.py \
  && cd integrations/discord/reader && python -B -m unittest discover -s tests" || fallar "pruebas de Discord"
log "importación de la API en communitylab-api:$ETIQUETA"
docker run --rm --network none -e DATABASE_URL=postgresql+asyncpg://x:y@127.0.0.1/x --entrypoint python \
  "communitylab-api:$ETIQUETA" -c "import backend.app.main" || fallar "la API no importa"
log "pruebas de imágenes $ETIQUETA aprobadas"
