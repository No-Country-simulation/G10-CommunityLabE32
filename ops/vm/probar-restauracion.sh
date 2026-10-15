#!/bin/bash
# Restaura un respaldo en recursos desechables (sin red) y lo compara con su manifiesto.
# Uso: probar-restauracion.sh <carpeta-de-respaldo>. Sale con 0 solo si todo coincide.
#
# PostgreSQL: conteos por tabla y columnas iguales a las del manifiesto, que se tomaron en el
#   mismo snapshot que el dump. El esquema esperado es el de la versión respaldada: no se exige
#   la columna de idempotencia a un respaldo anterior a la migración.
# SQLite: cada copia se abre en un contenedor sin red; integridad "ok" y conteos por tabla iguales.
# Solo elimina los recursos que crea (nombres únicos).
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

RESPALDO=${1:?Uso: probar-restauracion.sh <carpeta-de-respaldo>}
[ -f "$RESPALDO/manifiesto.json" ] && [ -f "$RESPALDO/postgres.dump" ] || fallar "respaldo incompleto"
IMAGEN_PG=${POSTGRES_IMAGE:-postgres:16-alpine}
IMAGEN_SQLITE=${DISCORD_IMAGE:-$IMAGEN_PREFIJO-discord:local}
nombre="cl-restauracion-$(sufijo)"
trap 'docker rm -f "$nombre" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$nombre" --network none -e POSTGRES_USER=prueba -e POSTGRES_PASSWORD=prueba \
  -e POSTGRES_DB=prueba "$IMAGEN_PG" >/dev/null
for _ in $(seq 60); do docker exec "$nombre" pg_isready -U prueba -d prueba >/dev/null 2>&1 && break; sleep 1; done
sleep 2
docker exec -i "$nombre" pg_restore -U prueba -d prueba --no-owner --exit-on-error < "$RESPALDO/postgres.dump" \
  || fallar "pg_restore falló"
restaurado=$(docker exec "$nombre" psql -X -At -U prueba -d prueba -c "
  SELECT json_build_object(
    'conteos', (SELECT coalesce(json_object_agg(table_name, (xpath('/row/n/text()',
        query_to_xml(format('SELECT count(*) AS n FROM %I', table_name), false, true, '')))[1]::text::bigint), '{}')
        FROM information_schema.tables WHERE table_schema='public'),
    'columnas', (SELECT coalesce(json_object_agg(t, cols), '{}') FROM (
        SELECT table_name t, json_agg(column_name ORDER BY column_name) cols
        FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) x))")

errores=0
python3 - "$RESPALDO/manifiesto.json" "$restaurado" <<'EOF' || errores=1
import json, sys
manifiesto = json.load(open(sys.argv[1]))["postgres"]
restaurado = json.loads(sys.argv[2])
fallos = []
for clave in ("conteos", "columnas"):
    esperado, real = manifiesto[clave], restaurado[clave]
    for tabla in sorted(set(esperado) | set(real)):
        if esperado.get(tabla) != real.get(tabla):
            fallos.append(f"{clave}.{tabla}: esperado={esperado.get(tabla)} restaurado={real.get(tabla)}")
version = "migrada" if "clave_idempotencia" in manifiesto["columnas"].get("trabajos_worker", []) else "anterior a la migración"
print(f"postgres: {'OK' if not fallos else 'FALLA'} (esquema {version}; conteos {manifiesto['conteos']})")
for f in fallos:
    print("  " + f)
sys.exit(1 if fallos else 0)
EOF

for archivo in $(cd "$RESPALDO" && find sqlite -name '*.sqlite3' 2>/dev/null | sort); do
  volumen=$(cut -d/ -f2 <<<"$archivo"); rel=${archivo#sqlite/$volumen/}
  real=$(docker run --rm -i --network none --name "cl-restauracion-sqlite-$(sufijo)" --entrypoint python \
    "$IMAGEN_SQLITE" -c '
import json, pathlib, sqlite3, sys, tempfile
ruta = pathlib.Path(tempfile.mkdtemp()) / "r.sqlite3"
ruta.write_bytes(sys.stdin.buffer.read())
c = sqlite3.connect(ruta)
tablas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type=\"table\" AND name NOT LIKE \"sqlite_%\"")]
print(json.dumps({"integridad": c.execute("pragma integrity_check").fetchone()[0],
                  "conteos": {t: c.execute(f"SELECT count(*) FROM \"{t}\"").fetchone()[0] for t in tablas}}))
' < "$RESPALDO/$archivo") || { echo "sqlite $volumen/$rel: FALLA (no se pudo abrir)"; errores=1; continue; }
  python3 - "$RESPALDO/manifiesto.json" "$volumen" "$rel" "$real" <<'EOF' || errores=1
import json, sys
manifiesto, volumen, rel, real = sys.argv[1:]
esperado = json.load(open(manifiesto))["sqlite"].get(volumen, {}).get(rel)
real = json.loads(real)
ok = esperado is not None and real["integridad"] == "ok" and real == esperado
print(f"sqlite {volumen}/{rel}: {'OK' if ok else 'FALLA'} {real}")
sys.exit(0 if ok else 1)
EOF
done
# Toda base del manifiesto debe existir en el respaldo.
python3 - "$RESPALDO" <<'EOF' || errores=1
import json, pathlib, sys
r = pathlib.Path(sys.argv[1]); m = json.load(open(r / "manifiesto.json"))["sqlite"]
faltan = [f"{v}/{rel}" for v, bases in m.items() for rel in bases if not (r / "sqlite" / v / rel).exists()]
print("sqlite: faltan " + ", ".join(faltan) if faltan else "sqlite: todas las bases del manifiesto presentes")
sys.exit(1 if faltan else 0)
EOF
[ "$errores" = 0 ] || fallar "la restauración no coincide con el respaldo"
log "restauración comprobada: $RESPALDO"
