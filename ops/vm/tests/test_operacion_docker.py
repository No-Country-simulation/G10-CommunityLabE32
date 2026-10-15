"""Operación con Docker real (Linux). Opt-in: CL_OPS_DOCKER=1.

Variables:
  CL_OPS_TMP        carpeta visible para el daemon de Docker (worktrees, configuración, estados).
  CL_OPS_IMAGENES   prefijo de imágenes YA construidas de la versión actual (por defecto communitylab).
  CL_OPS_VIEJO      commit de la versión anterior para la reversión (por defecto a2d7e86).
  CL_OPS_VIEJAS     prefijo de imágenes de la versión anterior (api y worker; web se comparte).
Todos los recursos usan nombres únicos (proyecto y prefijo de imagen propios) y se eliminan al final.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

import pytest

OPS = Path(__file__).resolve().parents[1]
REPO = OPS.parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("CL_OPS_DOCKER") != "1", reason="opt-in: CL_OPS_DOCKER=1")
TMP = Path(os.environ.get("CL_OPS_TMP", "/tmp"))
ACTUALES = os.environ.get("CL_OPS_IMAGENES", "communitylab")
VIEJO = os.environ.get("CL_OPS_VIEJO", "a2d7e86")
VIEJAS = os.environ.get("CL_OPS_VIEJAS", "communitylab-viejo")


def sh(*args, check=True, **kw):
    p = subprocess.run(list(args), capture_output=True, text=True, **kw)
    if check and p.returncode:
        raise AssertionError(f"{' '.join(args)} -> {p.returncode}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    return p


class Entorno:
    def __init__(self, nombre, commit):
        self.id = f"{nombre}{uuid.uuid4().hex[:8]}"
        self.prefijo = f"cltest-{self.id}"
        self.base = TMP / f"clops-{self.id}"
        self.app = self.base / "app"
        self.config = self.base / "config"
        self.config.mkdir(parents=True)
        # Respaldos y estados en un FS Linux nativo (permisos reales); el árbol y la configuración,
        # visibles para el daemon (montajes de Compose).
        self.local = Path(tempfile.mkdtemp(prefix=f"clops-{self.id}-"))
        sh("git", "-C", str(REPO), "worktree", "add", "--detach", "-q", str(self.app), commit)
        for nombre_cfg, db in (("lector.json", "/data/bandeja/discord.sqlite3"), ("bot.json", "/data/bot/bot.sqlite3")):
            datos = json.loads((REPO / "integrations/discord/config-servicios.example" / nombre_cfg).read_text())
            datos["database"] = db
            (self.config / nombre_cfg).write_text(json.dumps(datos))
        self.env = {"APP": str(self.app), "IMAGEN_PREFIJO": self.prefijo,
                    "RESPALDOS": str(self.local / "respaldos"), "DESPLIEGUES": str(self.local / "despliegues"),
                    "ESPERA_SALUD": "240", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                    "GIT_CONFIG_VALUE_0": "*"}

    def escribir_env(self, ruta, discord, extra=""):
        archivos = "docker-compose.yml:compose.discord.yml" if discord else "docker-compose.yml"
        ruta.write_text(
            f"COMPOSE_PROJECT_NAME={self.id}\nCOMPOSE_PATH_SEPARATOR=:\nCOMPOSE_FILE={archivos}\n"
            f"POSTGRES_PASSWORD=solo_prueba_{self.id}\nDOCKER_PLATFORM=linux/amd64\n"
            f"HTTP_BIND_ADDRESS=127.0.0.1\nHTTP_PORT={20000 + int(self.id[-4:], 16) % 9000}\n"
            f"WORKER_MODE=simulado\nAPI_IMAGE={self.prefijo}-api:local\nWORKER_IMAGE={self.prefijo}-worker:local\n"
            f"WEB_IMAGE={self.prefijo}-web:local\nDISCORD_IMAGE={self.prefijo}-discord:local\n"
            f"DISCORD_CONFIG_DIR={self.config}\nDISCORD_BOT_TOKEN=token-ficticio-no-valido\n"
            f"GEMINI_API_KEY=clave-ficticia\nGEMINI_MODELOS=gemini-ficticio\nPUENTE_PERIODO=dia\n" + extra)

    def dc(self, *args, check=True):
        return sh("docker", "compose", *args, cwd=self.app, check=check, env={**os.environ, **self.env})

    def ops(self, script, *args, check=True, **extra):
        return sh("bash", str(OPS / script), *args, check=check, env={**os.environ, **self.env, **extra}, timeout=1800)

    def etiquetar(self, origen, repos=("api", "worker", "web", "discord")):
        for repo in repos:
            fuente = f"{origen}-{repo}:local" if ":" not in origen else origen
            sh("docker", "tag", fuente, f"{self.prefijo}-{repo}:local")

    def psql(self, sql):
        return self.dc("exec", "-T", "postgres", "sh", "-c",
                       f'psql -X -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "{sql}"').stdout.strip()

    def esperar(self, segundos=240):
        limite = time.time() + segundos
        while time.time() < limite:
            filas = self.dc("ps", "-a", "--format", "{{.Service}}|{{.State}}|{{.Health}}|{{.ExitCode}}").stdout.split()
            if filas and all((s.startswith("db-init|exited") and s.endswith("|0")) or
                             (s.split("|")[1] == "running" and s.split("|")[2] in ("", "healthy")) for s in filas):
                return
            time.sleep(4)
        raise AssertionError(f"sin salud: {filas}")

    def cerrar(self):
        self.dc("down", "-v", "--remove-orphans", check=False)  # proyecto desechable de la prueba
        for c in sh("docker", "ps", "-aq", "--filter", f"name={self.id}", check=False).stdout.split():
            sh("docker", "rm", "-f", c, check=False)
        imagenes = sh("docker", "images", "--format", "{{.Repository}}:{{.Tag}}", check=False).stdout.split()
        for i in imagenes:
            if i.startswith(self.prefijo):
                sh("docker", "rmi", i, check=False)
        sh("git", "-C", str(REPO), "worktree", "remove", "--force", str(self.app), check=False)
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.local, ignore_errors=True)


ESCRITOR = r'''
import pathlib, sqlite3, sys, time, uuid
sys.path[:0] = ["/app/integrations/discord/reader", "/app/integrations/discord/bot", "/app"]
from discord_reader.store import Inbox
from bot_discord.store import Store
from pipelines.communitylab.entregas_discord import Entregas
Inbox("/data/bandeja/discord.sqlite3", 100000); Store(pathlib.Path("/data/bot/bot.sqlite3")); Entregas("/data/puente/entregas.sqlite3")
conexiones = []
for ruta in ("/data/bandeja/discord.sqlite3", "/data/puente/entregas.sqlite3", "/data/bot/bot.sqlite3"):
    c = sqlite3.connect(ruta, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA wal_autocheckpoint=0")
    c.execute("CREATE TABLE IF NOT EXISTS prueba_escrituras (id TEXT PRIMARY KEY, t REAL)")
    conexiones.append(c)
print("listo", flush=True)
while True:  # escrituras concurrentes sin checkpoint: el WAL sigue creciendo
    for c in conexiones:
        c.execute("INSERT INTO prueba_escrituras VALUES (?, ?)", (uuid.uuid4().hex, time.time()))
    time.sleep(0.05)
'''

CARGA_API = r'''
import json, time, urllib.request, uuid
while True:
    p = uuid.uuid4().hex[:8]
    lote = {"origen_comunidad": "carga", "periodo_referencia": "S", "cierre_periodo": False, "interacciones": [
        {"id": f"{p}-{i}", "autor": "a", "canal": "c", "fecha": "2026-10-15T10:00:00Z", "texto": f"m {i}"} for i in range(3)]}
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/api/v1/trabajos",
            data=json.dumps(lote).encode(), headers={"Content-Type": "application/json"}, method="POST"), timeout=5)
    except Exception:
        pass
    time.sleep(0.05)
'''


@pytest.fixture(scope="module")
def actual():
    e = Entorno("act", "HEAD")
    try:
        e.etiquetar(ACTUALES)
        e.escribir_env(e.app / ".env", discord=True)
        e.dc("up", "-d", "postgres", "db-init", "api", "worker", "discord-bridge")
        e.esperar()
        sh("docker", "run", "-d", "--name", f"cl-escritor-{e.id}", "--network", "none",
           "-v", f"{e.id}_discord_bandeja:/data/bandeja", "-v", f"{e.id}_discord_puente:/data/puente",
           "-v", f"{e.id}_discord_bot:/data/bot", "--entrypoint", "python", f"{e.prefijo}-discord:local", "-c", ESCRITOR)
        time.sleep(4)
        registro = sh("docker", "logs", f"cl-escritor-{e.id}", check=False)
        assert "listo" in registro.stdout, registro.stdout + registro.stderr
        e.dc("exec", "-d", "api", "python", "-c", CARGA_API)
        time.sleep(4)
        yield e
    finally:
        e.cerrar()


def test_respaldo_con_wal_y_escrituras_concurrentes_se_restaura_igual(actual):
    destino = actual.local / "respaldos" / "r1"
    antes = int(actual.psql("SELECT count(*) FROM trabajos_worker"))
    p = actual.ops("respaldo.sh", str(destino))
    assert p.stdout.strip().splitlines()[-1] == str(destino)
    manifiesto = json.loads((destino / "manifiesto.json").read_text())
    assert set(manifiesto["sqlite"]) == {"discord_bandeja", "discord_puente", "discord_bot"}
    for volumen, bases in manifiesto["sqlite"].items():
        for meta in bases.values():
            assert meta["integridad"] == "ok" and meta["conteos"].get("prueba_escrituras", 0) > 0, volumen
    assert oct(destino.stat().st_mode & 0o777) == "0o700"
    assert all(f.stat().st_mode & 0o077 == 0 for f in destino.rglob("*") if f.is_file())
    # La API y el worker siguieron escribiendo: el estado vivo ya difiere del snapshot respaldado...
    assert manifiesto["postgres"]["conteos"]["trabajos_worker"] >= antes
    time.sleep(2)
    assert int(actual.psql("SELECT count(*) FROM trabajos_worker")) > manifiesto["postgres"]["conteos"]["trabajos_worker"]
    # ...y aun así el dump corresponde exactamente al manifiesto.
    r = actual.ops("probar-restauracion.sh", str(destino))
    assert "postgres: OK (esquema migrada" in r.stdout and r.stdout.count("sqlite discord_") == 3
    assert actual.dc("ps", "--format", "{{.Service}}|{{.State}}").stdout.count("discord-bridge|running") == 1


def test_restauracion_rechaza_respaldos_alterados_y_acepta_esquema_anterior(actual):
    origen = actual.local / "respaldos" / "r2"
    actual.ops("respaldo.sh", str(origen))

    def copia(nombre, alterar):
        d = actual.local / "respaldos" / nombre
        shutil.copytree(origen, d)
        alterar(d)
        return actual.ops("probar-restauracion.sh", str(d), check=False)

    def manifiesto(d, cambio):
        m = json.loads((d / "manifiesto.json").read_text()); cambio(m)
        (d / "manifiesto.json").write_text(json.dumps(m))

    assert copia("conteo", lambda d: manifiesto(d, lambda m: m["postgres"]["conteos"].update(
        trabajos_worker=m["postgres"]["conteos"]["trabajos_worker"] + 1))).returncode != 0
    assert copia("sqlite_corrupto", lambda d: next(d.rglob("discord.sqlite3")).write_bytes(b"no es sqlite")).returncode != 0
    assert copia("sqlite_faltante", lambda d: next(d.rglob("bot.sqlite3")).unlink()).returncode != 0
    assert copia("dump_truncado", lambda d: (d / "postgres.dump").write_bytes(
        (d / "postgres.dump").read_bytes()[:2000])).returncode != 0

    # Respaldo anterior a la migración: sin columna de idempotencia en dump y manifiesto -> válido.
    def sin_columna(d):
        pg = f"cl-esquema-{actual.id}"
        sh("docker", "run", "-d", "--name", pg, "--network", "none", "-e", "POSTGRES_PASSWORD=x", "postgres:16-alpine")
        try:
            for _ in range(60):
                if sh("docker", "exec", pg, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    break
                time.sleep(1)
            time.sleep(2)
            with open(d / "postgres.dump", "rb") as f:
                subprocess.run(["docker", "exec", "-i", pg, "pg_restore", "-U", "postgres", "-d", "postgres",
                                "--no-owner"], stdin=f, check=True, capture_output=True)
            sh("docker", "exec", pg, "psql", "-U", "postgres", "-c",
               "ALTER TABLE trabajos_worker DROP COLUMN clave_idempotencia")
            (d / "postgres.dump").write_bytes(subprocess.run(
                ["docker", "exec", pg, "pg_dump", "-U", "postgres", "-d", "postgres", "-Fc"],
                check=True, capture_output=True).stdout)
        finally:
            sh("docker", "rm", "-f", pg, check=False)
        manifiesto(d, lambda m: m["postgres"]["columnas"]["trabajos_worker"].remove("clave_idempotencia"))

    previo = actual.local / "respaldos" / "previo_migracion"
    shutil.copytree(origen, previo)
    sin_columna(previo)
    ok = actual.ops("probar-restauracion.sh", str(previo), check=False)
    assert ok.returncode == 0 and "anterior a la migración" in ok.stdout, ok.stdout + ok.stderr
    # Si el manifiesto dice que la columna existía pero el dump no la tiene -> falla.
    inconsistente = actual.local / "respaldos" / "columna_inconsistente"
    shutil.copytree(previo, inconsistente)
    manifiesto(inconsistente, lambda m: m["postgres"]["columnas"]["trabajos_worker"].append("clave_idempotencia"))
    assert actual.ops("probar-restauracion.sh", str(inconsistente), check=False).returncode != 0


REPRODUCIR = pytest.mark.skipif(os.environ.get("CL_OPS_REPRODUCIR") != "1",
                                reason="reproducción de hallazgos sobre 0831c75: CL_OPS_REPRODUCIR=1")


@REPRODUCIR
def test_reproduccion_0831c75_respaldo_sqlite_falla_con_destino_privado(actual):
    """Hallazgo 1: el script anterior monta el destino root 0700 en un contenedor uid 10002."""
    viejo = actual.local / "respaldo_0831c75.sh"
    viejo.write_text(sh("git", "-C", str(REPO), "show", "0831c75:ops/vm/respaldo.sh").stdout)
    destino = actual.local / "respaldos" / "viejo"
    p = sh("bash", str(viejo), check=False, env={**os.environ, **actual.env, "DESTINO": str(destino),
                                                 "DISCORD_IMAGE": f"{actual.prefijo}-discord:local"})
    assert p.returncode != 0 and "unable to open database file" in p.stderr, p.stderr[-2000:]


@REPRODUCIR
def test_reproduccion_0831c75_conteos_fuera_del_snapshot(actual):
    """Hallazgo 4: el anterior hace pg_dump y DESPUÉS cuenta en otra transacción."""
    dump = actual.local / "viejo.dump"
    with open(dump, "wb") as f:  # mismos comandos que respaldo.sh de 0831c75 (líneas 21 y 38)
        subprocess.run(["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
                        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], cwd=actual.app, stdout=f, check=True,
                       env={**os.environ, **actual.env})
    conteo_posterior = int(actual.psql("SELECT count(*) FROM trabajos_worker"))
    pg = f"cl-repro-{actual.id}"
    sh("docker", "run", "-d", "--name", pg, "--network", "none", "-e", "POSTGRES_PASSWORD=x", "postgres:16-alpine")
    try:
        for _ in range(60):
            if sh("docker", "exec", pg, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(1)
        time.sleep(2)
        with open(dump, "rb") as f:
            subprocess.run(["docker", "exec", "-i", pg, "pg_restore", "-U", "postgres", "-d", "postgres",
                            "--no-owner"], stdin=f, check=True, capture_output=True)
        en_dump = int(sh("docker", "exec", pg, "psql", "-At", "-U", "postgres", "-c",
                         "SELECT count(*) FROM trabajos_worker").stdout)
    finally:
        sh("docker", "rm", "-f", pg, check=False)
    assert conteo_posterior != en_dump, "con escrituras concurrentes, el conteo posterior no describe el dump"


@pytest.fixture
def anterior():
    """Versión anterior en ejecución (commit VIEJO, sin servicios Discord) con datos."""
    e = Entorno("ant", VIEJO)
    try:
        e.etiquetar(VIEJAS, repos=("api", "worker"))
        e.etiquetar(f"{ACTUALES}-web:local", repos=("web",))
        e.escribir_env(e.app / ".env", discord=False)
        e.dc("up", "-d")
        e.esperar()
        e.dc("exec", "-T", "api", "python", "-c", CARGA_API.replace("while True:", "for _ in range(5):"))
        yield e
    finally:
        e.cerrar()


def estado_ejecucion(e):
    return {l.split("|")[0]: l.split("|")[1] for l in
            e.dc("ps", "--format", "{{.Service}}|{{.Image}}").stdout.split()}


def test_despliegue_fallido_revierte_imagenes_y_configuracion(anterior):
    e = anterior
    antes_imagenes = {s: sh("docker", "inspect", "-f", "{{.Image}}", c).stdout.strip()
                      for s, c in (l.split("|") for l in e.dc("ps", "--format", "{{.Service}}|{{.ID}}").stdout.split())}
    antes_env = (e.app / ".env").read_text()
    antes_commit = sh("git", "-C", str(e.app), "rev-parse", "HEAD").stdout.strip()
    trabajos = int(e.psql("SELECT count(*) FROM trabajos_worker"))
    nuevo = e.base / "nuevo.env"
    e.escribir_env(nuevo, discord=True)  # tokens ficticios: lector y bot no quedan sanos
    objetivo = sh("git", "-C", str(REPO), "rev-parse", "HEAD").stdout.strip()
    p = e.ops("desplegar.sh", objetivo, str(nuevo), check=False, PERMITIR_SIN_HTTPS="1",
              REVERTIR_CONSERVAR_HTTPS="0", ESPERA_SALUD="120",
              PROBAR_IMAGENES="/bin/true")
    assert p.returncode != 0
    assert "6/6 salud" in p.stderr and "reversión completa" in p.stderr, p.stderr[-3000:]
    assert sh("git", "-C", str(e.app), "rev-parse", "HEAD").stdout.strip() == antes_commit
    assert (e.app / ".env").read_text() == antes_env
    despues = {s: sh("docker", "inspect", "-f", "{{.Image}}", c).stdout.strip()
               for s, c in (l.split("|") for l in e.dc("ps", "--format", "{{.Service}}|{{.ID}}").stdout.split())}
    assert not any(s.startswith("discord-") for s in despues)  # consumidores nuevos retirados
    for servicio in ("api", "worker", "web"):
        assert despues[servicio] == antes_imagenes[servicio]
    e.esperar()
    assert int(e.psql("SELECT count(*) FROM trabajos_worker")) >= trabajos
    # La migración aditiva quedó aplicada y la versión anterior sigue funcionando sobre ella.
    assert e.psql("SELECT count(*) FROM information_schema.columns WHERE column_name='clave_idempotencia'") == "1"


def test_despliegue_exitoso_y_reversion_manual(anterior):
    e = anterior
    antes_env = (e.app / ".env").read_text()
    antes_commit = sh("git", "-C", str(e.app), "rev-parse", "HEAD").stdout.strip()
    nuevo = e.base / "nuevo.env"
    e.escribir_env(nuevo, discord=False, extra="WORKER_TIMEOUT=120\n")
    objetivo = sh("git", "-C", str(REPO), "rev-parse", "HEAD").stdout.strip()
    probar = os.environ.get("CL_OPS_PROBAR_IMAGENES", "/bin/true")
    p = e.ops("desplegar.sh", objetivo, str(nuevo), PERMITIR_SIN_HTTPS="1", PROBAR_IMAGENES=probar)
    assert "6/6 desplegado" in p.stderr
    assert sh("git", "-C", str(e.app), "rev-parse", "HEAD").stdout.strip() == objetivo
    estado = next((e.local / "despliegues").iterdir())
    r = e.ops("revertir.sh", str(estado), REVERTIR_CONSERVAR_HTTPS="0")
    assert "reversión completa" in r.stderr
    assert sh("git", "-C", str(e.app), "rev-parse", "HEAD").stdout.strip() == antes_commit
    assert (e.app / ".env").read_text() == antes_env
    e.esperar()


def test_probar_imagenes_detecta_archivos_ilegibles_para_el_usuario_de_la_imagen(tmp_path):
    """Defecto hallado al probar desplegar.sh: con umask 077 el árbol de build generaba imágenes
    cuyo usuario no root no podía leer /app. Las pruebas de imagen deben detectarlo."""
    etiqueta = f"roto{uuid.uuid4().hex[:6]}"
    prefijo = f"cltest-{etiqueta}"
    (tmp_path / "Dockerfile").write_text(
        f"FROM {ACTUALES}-worker:local\nUSER root\nRUN chmod 600 /app/worker/__init__.py\nUSER worker\n")
    try:
        sh("docker", "build", "-q", "-t", f"{prefijo}-worker:{etiqueta}", str(tmp_path))
        for repo in ("api", "discord"):
            sh("docker", "tag", f"{ACTUALES}-{repo}:local", f"{prefijo}-{repo}:{etiqueta}")
        p = sh("bash", str(OPS / "probar-imagenes.sh"), etiqueta, str(REPO), check=False,
               env={**os.environ, "IMAGEN_PREFIJO": prefijo}, timeout=600)
        assert p.returncode != 0 and "el worker no importa desde /app" in p.stderr, p.stderr[-2000:]
    finally:
        for repo in ("api", "worker", "discord"):
            sh("docker", "rmi", f"{prefijo}-{repo}:{etiqueta}", check=False)
