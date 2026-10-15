#!/bin/bash
# Reversión de APLICACIÓN al estado conservado por desplegar.sh. Uso (root): revertir.sh <carpeta-estado>
# No restaura datos: la migración es aditiva y la versión anterior funciona sobre el esquema nuevo.
#   1. Detiene los consumidores nuevos (bot, lector, puente y worker) antes de cambiar nada.
#   2. Restaura el .env y el commit anteriores. Si REVERTIR_CONSERVAR_HTTPS=1 (por defecto) y la
#      versión anterior tiene compose.https.yml, mantiene el override HTTPS en COMPOSE_FILE.
#   3. Devuelve a :local las imágenes que estaban en ejecución (:prev-<id>).
#   4. up -d --remove-orphans: elimina contenedores de servicios que la versión anterior no tenía
#      (los volúmenes se conservan). 5. Verifica salud.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

ESTADO=${1:?Uso: revertir.sh <carpeta-estado>}
ID=$(basename "$ESTADO")
VERIFICAR=${VERIFICAR:-$OPS/verificar.sh}
for f in env.anterior commit.anterior imagenes.anteriores; do [ -f "$ESTADO/$f" ] || fallar "falta $ESTADO/$f"; done

log "revertir 1/5: deteniendo consumidores nuevos"
for s in discord-bot discord-reader discord-bridge worker; do
  dc ps -q "$s" >/dev/null 2>&1 && dc stop "$s" >/dev/null 2>&1 || true
done

log "revertir 2/5: .env y commit anteriores"
cp "$ESTADO/env.anterior" "$APP/.env" && chmod 600 "$APP/.env"
(cd "$APP" && git checkout --quiet --detach "$(cat "$ESTADO/commit.anterior")") || fallar "checkout anterior falló"
if [ "${REVERTIR_CONSERVAR_HTTPS:-1}" = 1 ] && [ -f "$APP/compose.https.yml" ] \
   && ! grep -q '^COMPOSE_FILE=.*compose.https.yml' "$APP/.env"; then
  sed -i '/^COMPOSE_FILE=/d; /^COMPOSE_PATH_SEPARATOR=/d' "$APP/.env"
  printf 'COMPOSE_PATH_SEPARATOR=:\nCOMPOSE_FILE=docker-compose.yml:compose.https.yml\n' >> "$APP/.env"
  log "se mantiene el override HTTPS en la versión anterior"
fi

log "revertir 3/5: imágenes anteriores"
while read -r servicio repo imagen; do
  docker tag "communitylab-$repo:prev-$ID" "communitylab-$repo:local" || fallar "falta communitylab-$repo:prev-$ID"
done < "$ESTADO/imagenes.anteriores"

log "revertir 4/5: up con la configuración anterior"
dc up -d --remove-orphans --no-build || fallar "up anterior falló"
log "revertir 5/5: verificación"
esperar_salud "${ESPERA_SALUD:-300}" || fallar "la versión anterior no quedó sana"
"$VERIFICAR" || fallar "verificación de la versión anterior falló"
log "reversión completa a $(cut -c1-12 "$ESTADO/commit.anterior")"
