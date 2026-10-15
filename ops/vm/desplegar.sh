#!/bin/bash
# Despliegue con puertas. Uso (root): desplegar.sh <sha> <env-nuevo>
#   <sha>       commit a desplegar (se resuelve contra origin; debe existir).
#   <env-nuevo> archivo .env privado de la versión nueva (se instala solo en el corte).
#
# Etapas y qué ocurre si fallan:
#   1 conservar   Registra contenedores, ids de imagen EN EJECUCIÓN (no la etiqueta :local), .env y
#                 commit; etiqueta esas imágenes :prev-<id>. Falla -> nada cambió.
#   2 construir   Build en un worktree aislado con etiquetas :<sha> y pruebas dentro de las imágenes.
#                 Falla -> nada cambió en producción (las etiquetas :local no se tocan).
#   3 respaldar   respaldo.sh + probar-restauracion.sh. Falla -> nada cambió (puente reanudado).
#   4 migrar      db-init de la versión nueva (migración aditiva) con la app vieja aún en servicio.
#                 Falla -> se detiene; la app anterior sigue funcionando sobre el esquema.
#   5 cortar      Instala el .env nuevo, checkout del sha, :<sha> -> :local, up -d --remove-orphans.
#   6 verificar   Salud de todos los servicios + comprobación HTTP(S).
#                 Falla en 5 o 6 -> revertir.sh automático (imágenes, .env, commit) y salida 1.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

SHA_PEDIDO=${1:?Uso: desplegar.sh <sha> <env-nuevo>}
ENV_NUEVO=${2:?Uso: desplegar.sh <sha> <env-nuevo>}
PROBAR_IMAGENES=${PROBAR_IMAGENES:-$OPS/probar-imagenes.sh}
VERIFICAR=${VERIFICAR:-$OPS/verificar.sh}
ESPERA_SALUD=${ESPERA_SALUD:-300}

[ -f "$ENV_NUEVO" ] || fallar "no existe $ENV_NUEVO"
grep -q '^COMPOSE_FILE=.*compose.https.yml' "$ENV_NUEVO" || [ -n "${PERMITIR_SIN_HTTPS:-}" ] \
  || fallar "el .env nuevo debe definir COMPOSE_FILE con compose.https.yml"
[ -z "$(cd "$APP" && git status --porcelain --untracked-files=no)" ] || fallar "cambios locales en $APP"
(cd "$APP" && git fetch --quiet origin) || log "aviso: git fetch falló; se usa el sha local"
SHA=$(cd "$APP" && git rev-parse --verify "$SHA_PEDIDO^{commit}") || fallar "sha inexistente: $SHA_PEDIDO"
CORTO=${SHA:0:12}
ID=$(date -u +%Y%m%dT%H%M%SZ)
ESTADO="$DESPLIEGUES/$ID"
umask 077
mkdir -p "$ESTADO"
log "despliegue $ID: $CORTO (estado en $ESTADO)"

# --- 1. Conservar el estado realmente desplegado ---
cp "$APP/.env" "$ESTADO/env.anterior"
(cd "$APP" && git rev-parse HEAD) > "$ESTADO/commit.anterior"
: > "$ESTADO/imagenes.anteriores"
for c in $(dc ps -q); do
  servicio=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$c")
  imagen=$(docker inspect -f '{{.Image}}' "$c")
  repo=$(repo_de_servicio "$servicio")
  [ -n "$repo" ] || continue
  docker tag "$imagen" "communitylab-$repo:prev-$ID"
  printf '%s %s %s\n' "$servicio" "$repo" "$imagen" >> "$ESTADO/imagenes.anteriores"
done
sort -u -o "$ESTADO/imagenes.anteriores" "$ESTADO/imagenes.anteriores"
log "1/6 conservado: $(wc -l < "$ESTADO/imagenes.anteriores") servicios con imagen propia"

# --- 2. Construir y probar sin tocar producción ---
ARBOL="$ESTADO/arbol"
(cd "$APP" && git worktree add --detach --quiet "$ARBOL" "$SHA") || fallar "no se pudo preparar el árbol de build"
limpiar_arbol() { (cd "$APP" && git worktree remove --force "$ARBOL" >/dev/null 2>&1) || true; }
trap limpiar_arbol EXIT
export API_IMAGE="communitylab-api:$CORTO" WORKER_IMAGE="communitylab-worker:$CORTO"
export WEB_IMAGE="communitylab-web:$CORTO" DISCORD_IMAGE="communitylab-discord:$CORTO"
archivos=$(sed -n 's/^COMPOSE_FILE=//p' "$ENV_NUEVO" | tail -1)
(cd "$ARBOL" && COMPOSE_FILE="${archivos:-docker-compose.yml}" COMPOSE_PATH_SEPARATOR=: \
  docker compose --env-file "$ENV_NUEVO" build) || fallar "2/6 build falló; producción intacta"
"$PROBAR_IMAGENES" "$CORTO" "$ARBOL" || fallar "2/6 pruebas de imágenes fallaron; producción intacta"
log "2/6 imágenes $CORTO construidas y probadas"

# --- 3. Respaldo consistente y restauración comprobada (con la versión en servicio) ---
RESPALDO=$(env -u API_IMAGE -u WORKER_IMAGE -u WEB_IMAGE -u DISCORD_IMAGE "$OPS/respaldo.sh") \
  || fallar "3/6 respaldo falló; producción intacta"
RESPALDO=$(tail -1 <<<"$RESPALDO")
echo "$RESPALDO" > "$ESTADO/respaldo"
DISCORD_IMAGE="communitylab-discord:$CORTO" "$OPS/probar-restauracion.sh" "$RESPALDO" \
  || fallar "3/6 la restauración no coincide; producción intacta"
log "3/6 respaldo $RESPALDO restaurado y comprobado"

# --- 4. Migración aditiva (la app anterior sigue en servicio) ---
(cd "$ARBOL" && COMPOSE_FILE=docker-compose.yml COMPOSE_PROJECT_NAME="$(proyecto)" \
  docker compose --env-file "$ENV_NUEVO" run --rm --no-deps db-init) \
  || fallar "4/6 migración falló; la app anterior sigue en servicio (revisar $ESTADO)"
log "4/6 migración aplicada"

# --- 5 y 6. Corte y verificación; ante fallo, reversión automática ---
revertir() {
  log "fallo en $1: revirtiendo a $(cat "$ESTADO/commit.anterior" | cut -c1-12)"
  "$OPS/revertir.sh" "$ESTADO" || log "LA REVERSIÓN TAMBIÉN FALLÓ: intervención manual (ver docs/operacion-vm.md)"
  exit 1
}
echo "$SHA" > "$ESTADO/commit.nuevo"
cp "$ENV_NUEVO" "$APP/.env" && chmod 600 "$APP/.env"
(cd "$APP" && git checkout --quiet --detach "$SHA") || revertir "5/6 checkout"
for repo in $REPOS_IMAGEN; do
  docker image inspect "communitylab-$repo:$CORTO" >/dev/null 2>&1 \
    && docker tag "communitylab-$repo:$CORTO" "communitylab-$repo:local"
done
unset API_IMAGE WORKER_IMAGE WEB_IMAGE DISCORD_IMAGE
dc up -d --remove-orphans --no-build || revertir "5/6 up"
esperar_salud "$ESPERA_SALUD" || revertir "6/6 salud"
"$VERIFICAR" || revertir "6/6 verificación"
log "6/6 desplegado $CORTO y verificado (anterior conservado en $ESTADO)"
