#!/bin/bash
# Respaldo consistente de CommunityLab en la VM. Ejecutar como root desde la raíz del repositorio.
# PostgreSQL: pg_dump (instantánea transaccional). SQLite: API de backup de SQLite (segura con
# escrituras concurrentes y WAL). El puente se pausa para que su estado y PostgreSQL formen un corte
# coherente; lector y bot siguen capturando (su bandeja es la fuente y se respalda igual).
set -euo pipefail
APP=${APP:-/home/tareck/G10-CommunityLabE32}
DESTINO=${DESTINO:-/var/backups/communitylab}/$(date -u +%Y%m%dT%H%M%SZ)
cd "$APP"
leer_env() { sed -n "s/^$1=//p" .env | tail -1; }
PROYECTO=$(leer_env COMPOSE_PROJECT_NAME); PROYECTO=${PROYECTO:-g10-communitylabe32}
CONFIG_DISCORD=$(leer_env DISCORD_CONFIG_DIR)
umask 077
mkdir -p "$DESTINO"
servicios=$(docker compose config --services)
pausado=0
if grep -qx discord-bridge <<<"$servicios" && [ -n "$(docker compose ps -q discord-bridge)" ]; then
  docker compose stop discord-bridge && pausado=1
fi
trap '[ "$pausado" = 1 ] && docker compose start discord-bridge >/dev/null' EXIT
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DESTINO/postgres.dump"
for par in discord_bandeja:discord.sqlite3 discord_puente:entregas.sqlite3 discord_bot:bot.sqlite3; do
  volumen="${PROYECTO}_${par%%:*}"
  docker volume inspect "$volumen" >/dev/null 2>&1 || continue
  docker run --rm -v "$volumen:/origen" -v "$DESTINO:/destino" --entrypoint python \
    "${DISCORD_IMAGE:-communitylab-discord:local}" -c "
import sqlite3, pathlib, sys
origen = next(pathlib.Path('/origen').rglob('${par#*:}'), None)
if origen is None: sys.exit(0)
a = sqlite3.connect(f'file:{origen}?mode=ro', uri=True); b = sqlite3.connect('/destino/${par%%:*}.sqlite3')
a.backup(b); ok = b.execute('pragma integrity_check').fetchone()[0]; b.close(); a.close()
print('${par%%:*}', ok); sys.exit(ok != 'ok')"
done
# Configuración privada (contiene secretos): solo root, nunca dentro del repositorio.
tar --force-local -czf "$DESTINO/configuracion-privada.tgz" -C "$APP" .env ${CONFIG_DISCORD:+-C "$CONFIG_DISCORD" .}
git rev-parse HEAD > "$DESTINO/commit.txt"
docker compose images --format json > "$DESTINO/imagenes.json"
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select (select count(*) from trabajos_worker), (select count(*) from mensajes), (select count(*) from activos)"' > "$DESTINO/conteos.txt"
chmod -R go-rwx "$DESTINO"
echo "respaldo=$DESTINO conteos=$(cat "$DESTINO/conteos.txt")"
