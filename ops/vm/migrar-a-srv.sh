#!/bin/bash
# Migración única de la aplicación a la ruta canónica, con un usuario de servicio dedicado.
#   /home/tareck/G10-CommunityLabE32 (cuenta personal)  ->  /srv/communitylab (usuario communitylab)
# Además instala los cl-* (incluido cl-token-operador) y la regla sudo del grupo operadores
# (ops/vm/sudoers-operadores, validada con visudo antes y después de instalarla).
# Uso (root):
#   migrar-a-srv.sh comprobar   solo comprueba requisitos y muestra el plan; no cambia nada
#   migrar-a-srv.sh ejecutar    respaldo comprobado, corte corto, mudanza y verificación
#   migrar-a-srv.sh deshacer    devuelve la aplicación a la ruta y al dueño anteriores
#
# No mueve datos: PostgreSQL y los SQLite de Discord están en volúmenes de Docker, y el .env fija
# COMPOSE_PROJECT_NAME, así que el proyecto conserva sus volúmenes. Nunca usa `down -v` ni `prune`.
# Si algo falla después de detener los servicios, se deshace automáticamente.
set -Eeuo pipefail  # -E: el trap ERR del corte también actúa dentro de funciones

ORIGEN=${ORIGEN:-/home/tareck/G10-CommunityLabE32}
DESTINO=${DESTINO:-/srv/communitylab}
USUARIO=${USUARIO_APP:-communitylab}
PROYECTO_ESPERADO=${PROYECTO_ESPERADO:-g10-communitylabe32}
ESTADO=${ESTADO_MIGRACION:-/var/lib/communitylab/migracion-srv}
BIN=${BIN:-/usr/local/sbin}
COMANDOS="cl-actualizar cl-estado cl-logs cl-reiniciar cl-respaldo cl-revertir cl-token-operador"
SUDOERS_DESTINO=${SUDOERS_DESTINO:-/etc/sudoers.d/50-operadores}
VISUDO=${VISUDO:-visudo}
HOOKS="certbot-pre certbot-post"
RESPALDO_CMD=${RESPALDO_CMD:-}
RESTAURAR_CMD=${RESTAURAR_CMD:-}
export VERIFICAR_URLS=${VERIFICAR_URLS-"https://communitylab.nodnexa.com/healthz=200 http://communitylab.nodnexa.com/=301"}

MODO=${1:?Uso: migrar-a-srv.sh comprobar|ejecutar|deshacer}
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }
fallar() { log "ERROR: $*"; exit 1; }
# PERMITIR_NO_ROOT solo para las pruebas automatizadas (usuario existente, rutas temporales).
[ "$(id -u)" = 0 ] || [ -n "${PERMITIR_NO_ROOT:-}" ] || fallar "ejecutar como root"
logger -t cl-operador "migrar-a-srv $MODO por ${SUDO_USER:-?}" 2>/dev/null || true

instalar_operacion() {  # $1 = raíz de la aplicación cuyos cl-* y hooks se instalan
  for c in $COMANDOS; do install -m 755 "$1/ops/vm/$c" "$BIN/$c"; done
  for h in $HOOKS; do install -m 750 "$1/ops/vm/$h" "$BIN/communitylab-$h"; done
}

instalar_sudoers() {  # $1 = plantilla validada; se instala 440 y se revalida toda la configuración
  "$VISUDO" -cf "$1" >/dev/null || fallar "la regla sudo $1 no es válida"
  install -m 440 "$1" "$SUDOERS_DESTINO"
  if ! "$VISUDO" -c >/dev/null; then
    [ -f "$ESTADO/sudoers.anterior" ] && install -m 440 "$ESTADO/sudoers.anterior" "$SUDOERS_DESTINO"
    fallar "configuración sudo inválida tras instalar la regla; se restauró la anterior"
  fi
}

levantar_y_verificar() {  # $1 = raíz de la aplicación
  APP="$1"
  # shellcheck source=/dev/null
  source "$1/ops/vm/comun.sh"
  APP="$1"
  dc up -d --no-build --remove-orphans
  esperar_salud "${ESPERA_SALUD:-300}"
  VERIFICAR="$1/ops/vm/verificar.sh"; APP="$1" "$VERIFICAR"
}

deshacer() {
  trap - ERR  # que un fallo aquí no vuelva a invocar deshacer
  log "deshacer: volviendo a $ORIGEN"
  [ -d "$DESTINO" ] && (cd "$DESTINO" && docker compose down --remove-orphans) || true
  if [ -d "$DESTINO" ] && [ ! -e "$ORIGEN" ]; then mv "$DESTINO" "$ORIGEN"; fi
  [ -f "$ESTADO/duenio.anterior" ] && chown -R "$(cat "$ESTADO/duenio.anterior")" "$ORIGEN"
  chmod 600 "$ORIGEN/.env"
  if [ -d "$ESTADO/sbin.anterior" ]; then
    for f in "$ESTADO"/sbin.anterior/*; do install -m "$(stat -c %a "$f")" "$f" "$BIN/$(basename "$f")"; done
    # Comandos nuevos que no existían antes (p. ej. cl-token-operador): se retiran.
    for c in $COMANDOS; do [ -e "$ESTADO/sbin.anterior/$c" ] || rm -f "$BIN/$c"; done
  fi
  if [ -f "$ESTADO/sudoers.anterior" ]; then instalar_sudoers "$ESTADO/sudoers.anterior"; fi
  levantar_y_verificar "$ORIGEN"
  log "deshacer completo: aplicación en $ORIGEN"
}

if [ "$MODO" = deshacer ]; then deshacer; exit 0; fi

# --- Comprobaciones (no cambian nada) ---
[ -d "$ORIGEN/.git" ] && [ -f "$ORIGEN/.env" ] || fallar "no hay checkout con .env en $ORIGEN"
[ ! -e "$DESTINO" ] || fallar "$DESTINO ya existe"
mkdir -p "$(dirname "$DESTINO")" 2>/dev/null || true
[ "$(stat -c %d "$(dirname "$ORIGEN")")" = "$(stat -c %d "$(dirname "$DESTINO")")" ] \
  || fallar "origen y destino en sistemas de archivos distintos: mv no sería atómico"
grep -qx "COMPOSE_PROJECT_NAME=$PROYECTO_ESPERADO" "$ORIGEN/.env" \
  || fallar ".env sin COMPOSE_PROJECT_NAME=$PROYECTO_ESPERADO: la mudanza crearía volúmenes vacíos"
grep -q '^COMPOSE_FILE=.*compose.https.yml' "$ORIGEN/.env" || fallar ".env sin COMPOSE_FILE canónico (HTTPS)"
source "$ORIGEN/ops/vm/comun.sh"
APP="$ORIGEN"
[ -z "$(git_app status --porcelain --untracked-files=no)" ] || fallar "cambios locales en $ORIGEN"
for v in $VOLUMENES_SQLITE postgres_data; do
  docker volume inspect "${PROYECTO_ESPERADO}_$v" >/dev/null 2>&1 && log "volumen ${PROYECTO_ESPERADO}_$v presente" \
    || log "aviso: volumen ${PROYECTO_ESPERADO}_$v no encontrado (revisar nombre)"
done
for c in $COMANDOS; do [ -f "$ORIGEN/ops/vm/$c" ] || fallar "falta ops/vm/$c"; done
"$VISUDO" -cf "$ORIGEN/ops/vm/sudoers-operadores" >/dev/null || fallar "ops/vm/sudoers-operadores no es válido"
log "plan: respaldo -> usuario $USUARIO -> down (sin -v) -> mv $ORIGEN $DESTINO -> chown $USUARIO -> cl-*/hooks/sudo -> up -> verificar"
if [ "$MODO" = comprobar ]; then log "comprobación correcta; no se cambió nada"; exit 0; fi
[ "$MODO" = ejecutar ] || fallar "modo desconocido: $MODO"

# --- 1. Respaldo comprobado (con la aplicación en servicio) ---
RESPALDO=$("${RESPALDO_CMD:-$ORIGEN/ops/vm/respaldo.sh}" | tail -1) || fallar "respaldo falló; nada cambió"
"${RESTAURAR_CMD:-$ORIGEN/ops/vm/probar-restauracion.sh}" "$RESPALDO" || fallar "restauración no coincide; nada cambió"
log "1/6 respaldo $RESPALDO comprobado"

# --- 2. Estado para deshacer y usuario de servicio ---
umask 077
mkdir -p "$ESTADO/sbin.anterior"
stat -c '%U:%G' "$ORIGEN" > "$ESTADO/duenio.anterior"
for f in $COMANDOS; do [ -f "$BIN/$f" ] && cp -p "$BIN/$f" "$ESTADO/sbin.anterior/"; done
for h in $HOOKS; do [ -f "$BIN/communitylab-$h" ] && cp -p "$BIN/communitylab-$h" "$ESTADO/sbin.anterior/"; done
[ -f "$SUDOERS_DESTINO" ] && cp -p "$SUDOERS_DESTINO" "$ESTADO/sudoers.anterior"
echo "$RESPALDO" > "$ESTADO/respaldo"
getent passwd "$USUARIO" >/dev/null || useradd --system --user-group --no-create-home \
  --home-dir "$DESTINO" --shell /usr/sbin/nologin "$USUARIO"
log "2/6 usuario de servicio $USUARIO listo; estado en $ESTADO"

# --- 3 a 6. Corte: a partir de aquí, cualquier fallo deshace la mudanza ---
trap 'log "fallo durante el corte"; deshacer; exit 1' ERR
log "3/6 inicio del corte: deteniendo servicios (volúmenes conservados)"
(cd "$ORIGEN" && docker compose down --remove-orphans)
mv "$ORIGEN" "$DESTINO"
chown -R "$USUARIO:" "$DESTINO"   # solo la carpeta de la aplicación (grupo de login del usuario)
chmod 750 "$DESTINO" && chmod 600 "$DESTINO/.env"
log "4/6 aplicación en $DESTINO (dueño $USUARIO)"
instalar_operacion "$DESTINO"
instalar_sudoers "$DESTINO/ops/vm/sudoers-operadores"
log "5/6 cl-*, hooks de certbot y regla sudo de operadores instalados desde $DESTINO"
levantar_y_verificar "$DESTINO"
trap - ERR
log "6/6 migración completa: $DESTINO (deshacer: migrar-a-srv.sh deshacer)"
