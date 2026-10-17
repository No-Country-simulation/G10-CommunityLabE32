#!/bin/bash
# Funciones comunes de operación. Se incluye con `source`; no se ejecuta solo.
set -euo pipefail

OPS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Raíz de la aplicación: la del propio checkout (ops/vm/ -> ../..). Funciona igual en la ruta
# histórica (/home/tareck/G10-CommunityLabE32) y en la canónica (/srv/communitylab).
APP=${APP:-$(cd "$OPS/../.." && pwd)}
RESPALDOS=${RESPALDOS:-/var/backups/communitylab}
DESPLIEGUES=${DESPLIEGUES:-/var/lib/communitylab/despliegues}
# Repositorios de imagen propios (communitylab-<x>) y servicios que los usan.
REPOS_IMAGEN="api worker web discord"
# Prefijo de las imágenes propias (<prefijo>-<repo>:<etiqueta>). En la VM: communitylab.
IMAGEN_PREFIJO=${IMAGEN_PREFIJO:-communitylab}
VOLUMENES_SQLITE="discord_bandeja discord_puente discord_bot"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }
fallar() { log "ERROR: $*"; exit 1; }
sufijo() { printf '%s-%s-%s' "$(date -u +%Y%m%dT%H%M%SZ)" "$$" "$RANDOM"; }

leer_env() { [ -f "$APP/.env" ] && sed -n "s/^$1=//p" "$APP/.env" | tail -1 || true; }
proyecto() { local p; p=$(leer_env COMPOSE_PROJECT_NAME); printf '%s' "${p:-g10-communitylabe32}"; }
dc() { (cd "$APP" && docker compose "$@"); }

# Git sobre el checkout SIEMPRE con el usuario dueño de $APP (umask 022): evita archivos de root
# en el repositorio y el rechazo de git por propiedad dudosa. Si ya somos el dueño, se ejecuta
# directamente (pruebas y CI).
git_app() {
  local duenio; duenio=$(stat -c %U "$APP")
  if [ "$(id -un)" = "$duenio" ]; then
    (cd "$APP" && umask 022 && git "$@")
  elif command -v runuser >/dev/null; then   # Ubuntu (util-linux)
    (cd "$APP" && umask 022 && runuser -u "$duenio" -- git "$@")
  elif command -v sudo >/dev/null; then
    (cd "$APP" && umask 022 && sudo -u "$duenio" -- git "$@")
  else
    fallar "se necesita runuser o sudo para ejecutar git como $duenio"
  fi
}
# Worktrees de build bajo $DESPLIEGUES (root, 700): se crean como root; safe.directory solo
# para este proceso, sin tocar la configuración global.
git_root() {
  (cd "$APP" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" git "$@")
}

repo_de_servicio() {
  case "$1" in
    api) echo api ;; worker|db-init) echo worker ;; web) echo web ;;
    discord-reader|discord-bridge|discord-bot) echo discord ;; *) echo "" ;;
  esac
}

# Espera a que todos los servicios en ejecución estén sanos (db-init puede haber terminado).
esperar_salud() {
  local limite=$(( $(date +%s) + ${1:-300} )) estado malos
  while :; do
    estado=$(dc ps -a --format '{{.Service}}|{{.State}}|{{.Health}}|{{.ExitCode}}')
    malos=$(awk -F'|' '$1=="db-init" { if (!($2=="exited" && $4=="0")) print; next }
                       $2!="running" || ($3!="" && $3!="healthy") { print }' <<<"$estado")
    [ -z "$malos" ] && [ -n "$estado" ] && return 0
    [ "$(date +%s)" -ge "$limite" ] && { log "servicios sin salud: $(tr '\n' ';' <<<"$malos")"; return 1; }
    sleep 5
  done
}
