#!/bin/bash
# Respaldo consistente de CommunityLab. Ejecutar como root. Imprime la carpeta creada.
#
# PostgreSQL: una transacción REPEATABLE READ exporta un snapshot; los conteos y el esquema
#   del manifiesto se leen en ella y pg_dump usa el MISMO snapshot (--snapshot), aunque API y
#   worker sigan escribiendo.
# SQLite: el puente se pausa (su estado y PostgreSQL forman un corte coherente). Cada base se
#   copia con la API de backup de SQLite (incluye el WAL) dentro de un contenedor con la
#   identidad dueña del volumen; la copia sale por stdout como tar y el host la escribe en el
#   destino privado (root, 0700/0600). El contenedor nunca escribe en el destino.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

DESTINO=${1:-$RESPALDOS/$(date -u +%Y%m%dT%H%M%SZ)}
umask 077
mkdir -p "$DESTINO"
chmod 700 "$DESTINO"
PROYECTO=$(proyecto)
IMAGEN_DISCORD=${DISCORD_IMAGE:-$IMAGEN_PREFIJO-discord:local}

pausado=0
reanudar() { [ "$pausado" = 1 ] && dc start discord-bridge >/dev/null 2>&1 || true; }
trap reanudar EXIT
if [ -n "$(dc ps -q discord-bridge 2>/dev/null)" ]; then
  dc stop discord-bridge >/dev/null && pausado=1 && log "puente pausado"
fi

# --- PostgreSQL: snapshot exportado y retenido mientras corre pg_dump ---
coproc SNAP {
  # Servicio worker de Compose: recibe PGHOST/PGUSER/PGPASSWORD/PGDATABASE por entorno (sin argumentos visibles).
  dc run --rm --no-deps -T --name "cl-respaldo-snapshot-$(sufijo)" --entrypoint python worker -u -c '
import json, sys, psycopg
with psycopg.connect(autocommit=False) as c:
    c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    snap = c.execute("SELECT pg_export_snapshot()").fetchone()[0]
    tablas = [r[0] for r in c.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY 1")]
    conteos = {t: c.execute(f"SELECT count(*) FROM \"{t}\"").fetchone()[0] for t in tablas}
    columnas = {t: [r[0] for r in c.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
        "AND table_name=%s ORDER BY 1", (t,))] for t in tablas}
    print(json.dumps({"snapshot": snap, "conteos": conteos, "columnas": columnas}), flush=True)
    sys.stdin.read()  # mantiene la transacción abierta hasta que el host cierre stdin
'
}
IFS= read -r -t 120 -u "${SNAP[0]}" linea_pg || fallar "no se obtuvo el snapshot de PostgreSQL"
snapshot=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["snapshot"])' "$linea_pg")
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --snapshot="$1"' _ "$snapshot" \
  > "$DESTINO/postgres.dump" || fallar "pg_dump falló"
exec {SNAP[1]}>&-
wait "$SNAP_PID" 2>/dev/null || true
dc exec -T postgres pg_restore --list < "$DESTINO/postgres.dump" > /dev/null || fallar "dump ilegible"

# --- SQLite: copia por stdout (tar), integridad y conteos por tabla ---
echo '{}' > "$DESTINO/sqlite.json"
for volumen in $VOLUMENES_SQLITE; do
  nombre_vol="${PROYECTO}_${volumen}"
  docker volume inspect "$nombre_vol" >/dev/null 2>&1 || continue
  mkdir -p "$DESTINO/sqlite/$volumen"
  docker run --rm --name "cl-respaldo-sqlite-$(sufijo)" --network none -v "$nombre_vol:/origen" \
    --entrypoint python "$IMAGEN_DISCORD" -c '
import io, json, pathlib, sqlite3, sys, tarfile, tempfile
salida = tarfile.open(fileobj=sys.stdout.buffer, mode="w|")
meta = {}
for origen in sorted(pathlib.Path("/origen").rglob("*.sqlite3")):
    rel = str(origen.relative_to("/origen"))
    copia = pathlib.Path(tempfile.mkdtemp()) / "copia.sqlite3"
    a = sqlite3.connect(f"file:{origen}?mode=ro", uri=True, timeout=30)
    b = sqlite3.connect(copia)
    a.backup(b)  # copia consistente que incluye las páginas aún en el WAL
    a.close()
    integridad = b.execute("pragma integrity_check").fetchone()[0]
    tablas = [r[0] for r in b.execute("SELECT name FROM sqlite_master WHERE type=\"table\" AND name NOT LIKE \"sqlite_%\"")]
    meta[rel] = {"integridad": integridad, "conteos": {t: b.execute(f"SELECT count(*) FROM \"{t}\"").fetchone()[0] for t in tablas}}
    b.close()
    if integridad != "ok":
        sys.exit(f"integridad {rel}: {integridad}")
    salida.add(copia, arcname=rel)
datos = json.dumps(meta).encode()
info = tarfile.TarInfo("meta.json"); info.size = len(datos)
salida.addfile(info, io.BytesIO(datos)); salida.close()
' | tar -x -C "$DESTINO/sqlite/$volumen" || fallar "respaldo SQLite de $volumen falló"
  python3 - "$DESTINO/sqlite.json" "$volumen" "$DESTINO/sqlite/$volumen/meta.json" <<'EOF'
import json, sys
ruta, volumen, meta = sys.argv[1:]
datos = json.load(open(ruta)); datos[volumen] = json.load(open(meta)); json.dump(datos, open(ruta, "w"))
EOF
  rm "$DESTINO/sqlite/$volumen/meta.json"
  log "sqlite $volumen respaldado"
done
reanudar; pausado=0

# --- Configuración privada y manifiesto ---
# DISCORD_CONFIG_DIR_RESPALDO permite respaldar la config desde otra ruta (ajuste traído de la VM).
config_discord=${DISCORD_CONFIG_DIR_RESPALDO:-$(leer_env DISCORD_CONFIG_DIR)}
python3 - "$DESTINO/configuracion-privada.tgz" "$APP/.env" "$config_discord" <<'EOF'
import os, sys, tarfile
destino, env, config = sys.argv[1:]
with tarfile.open(destino, "w:gz") as t:
    t.add(env, arcname=".env")
    if config and os.path.isdir(config):
        t.add(config, arcname="discord-config")
EOF
python3 - "$DESTINO" "$linea_pg" "$(cd "$APP" && git rev-parse HEAD)" "$PROYECTO" <<'EOF'
import json, pathlib, sys
destino, pg, commit, proyecto = sys.argv[1:]
pg = json.loads(pg); pg.pop("snapshot")
manifiesto = {"commit": commit, "proyecto": proyecto, "postgres": pg,
              "sqlite": json.loads((pathlib.Path(destino) / "sqlite.json").read_text())}
(pathlib.Path(destino) / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2))
EOF
rm "$DESTINO/sqlite.json"
chmod -R go-rwx "$DESTINO"
log "respaldo completo en $DESTINO"
echo "$DESTINO"
