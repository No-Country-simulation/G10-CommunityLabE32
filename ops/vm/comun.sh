#!/bin/bash
# Funciones comunes de operación. Se incluye con `source`; no se ejecuta solo.
set -euo pipefail

APP=${APP:-/home/tareck/G10-CommunityLabE32}
RESPALDOS=${RESPALDOS:-/var/backups/communitylab}
DESPLIEGUES=${DESPLIEGUES:-/var/lib/communitylab/despliegues}
OPS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
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
