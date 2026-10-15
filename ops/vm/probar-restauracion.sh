#!/bin/bash
# Restaura un respaldo en un PostgreSQL desechable (sin red ni volumen persistente) y compara conteos.
# No toca producción. Uso: probar-restauracion.sh /var/backups/communitylab/AAAAMMDDTHHMMSSZ
set -euo pipefail
RESPALDO=$1
nombre=communitylab-restauracion-prueba
docker rm -f "$nombre" >/dev/null 2>&1 || true
docker run -d --name "$nombre" --network none -e POSTGRES_USER=prueba -e POSTGRES_PASSWORD=prueba \
  -e POSTGRES_DB=prueba postgres:16-alpine >/dev/null
trap 'docker rm -f "$nombre" >/dev/null' EXIT
for _ in $(seq 30); do docker exec "$nombre" pg_isready -U prueba >/dev/null 2>&1 && break; sleep 1; done
docker exec -i "$nombre" pg_restore -U prueba -d prueba --no-owner --exit-on-error < "$RESPALDO/postgres.dump"
restaurado=$(docker exec "$nombre" psql -U prueba -d prueba -tAc "select (select count(*) from trabajos_worker), (select count(*) from mensajes), (select count(*) from activos)")
esquema=$(docker exec "$nombre" psql -U prueba -d prueba -tAc "select count(*) from information_schema.columns where table_name='trabajos_worker' and column_name='clave_idempotencia'")
echo "respaldo=$(cat "$RESPALDO/conteos.txt") restaurado=$restaurado columna_idempotencia=$esquema"
[ "$restaurado" = "$(cat "$RESPALDO/conteos.txt")" ]
