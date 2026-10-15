"""Puertas de desplegar.sh / revertir.sh con un `docker` falso (registra llamadas) y git real.

Requiere bash y git (Linux). No usa Docker ni red. Cada prueba verifica que un fallo en una
etapa impide las siguientes y que producción (commit, .env, etiquetas :local) no cambia.
"""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

OPS = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="requiere bash Linux")

DOCKER_FALSO = r"""#!/bin/bash
# docker falso: registra la llamada y responde según FALLA (lista separada por comas).
echo "docker $*" >> "$REGISTRO"
falla() { [[ ",$FALLA," == *",$1,"* ]]; }
case "$*" in
  "compose ps -q") printf 'c-api\nc-worker\nc-postgres\n' ;;
  "inspect -f {{index .Config.Labels \"com.docker.compose.service\"}} c-api") echo api ;;
  "inspect -f {{index .Config.Labels \"com.docker.compose.service\"}} c-worker") echo worker ;;
  "inspect -f {{index .Config.Labels \"com.docker.compose.service\"}} c-postgres") echo postgres ;;
  "inspect -f {{.Image}} c-api") echo sha256:api-en-ejecucion ;;
  "inspect -f {{.Image}} c-worker") echo sha256:worker-en-ejecucion ;;
  "inspect -f {{.Image}} c-postgres") echo sha256:postgres ;;
  *" build"*) falla build && exit 1 ;;
  *"run --rm --no-deps db-init"*) falla migracion && exit 1 ;;
  *"up -d"*) falla up && exit 1 ;;
  "compose ps -a --format"*) if falla salud; then echo "api|running|unhealthy|0"; else echo "api|running|healthy|0"; echo "db-init|exited||0"; fi ;;
esac
exit 0
"""


def ejecutable(ruta, contenido):
    ruta.write_text(contenido)
    ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def entorno(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(app)], check=True)
    (app / "docker-compose.yml").write_text("services: {}\n")
    (app / ".gitignore").write_text(".env\n")
    subprocess.run(git + ["-C", str(app), "add", "."], check=True)
    subprocess.run(git + ["-C", str(app), "commit", "-qm", "anterior"], check=True)
    anterior = subprocess.check_output(["git", "-C", str(app), "rev-parse", "HEAD"], text=True).strip()
    (app / "nuevo.txt").write_text("v2")
    subprocess.run(git + ["-C", str(app), "add", "."], check=True)
    subprocess.run(git + ["-C", str(app), "commit", "-qm", "nuevo"], check=True)
    nuevo = subprocess.check_output(["git", "-C", str(app), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(app), "checkout", "-q", anterior], check=True)
    (app / ".env").write_text("WORKER_MODE=simulado\n")
    env_nuevo = tmp_path / "nuevo.env"
    env_nuevo.write_text("WORKER_MODE=gemini\nCOMPOSE_PATH_SEPARATOR=:\nCOMPOSE_FILE=docker-compose.yml:compose.https.yml\n")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    ejecutable(bin_ / "docker", DOCKER_FALSO)
    registro = tmp_path / "registro.log"
    pasos = {}
    for nombre in ("probar", "respaldo", "restaurar", "revertir", "verificar"):
        ejecutable(bin_ / f"falso-{nombre}",
                   f'#!/bin/bash\necho "{nombre} $*" >> "$REGISTRO"\n'
                   f'[[ ",$FALLA," == *",{nombre},"* ]] && exit 1\n'
                   + ('echo "$DESPLIEGUES/respaldo-falso"\n' if nombre == "respaldo" else "") + "exit 0\n")
    base = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "APP": str(app), "REGISTRO": str(registro),
            "DESPLIEGUES": str(tmp_path / "despliegues"), "PROBAR_IMAGENES": str(bin_ / "falso-probar"),
            "RESPALDO_CMD": str(bin_ / "falso-respaldo"), "RESTAURAR_CMD": str(bin_ / "falso-restaurar"),
            "REVERTIR_CMD": str(bin_ / "falso-revertir"), "VERIFICAR": str(bin_ / "falso-verificar"),
            "ESPERA_SALUD": "1", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
            "GIT_CONFIG_VALUE_0": "*"}

    def desplegar(falla=""):
        p = subprocess.run(["bash", str(OPS / "desplegar.sh"), nuevo, str(env_nuevo)], capture_output=True,
                           text=True, env={**base, "FALLA": falla}, timeout=120)
        llamadas = registro.read_text().splitlines() if registro.exists() else []
        head = subprocess.check_output(["git", "-C", str(app), "rev-parse", "HEAD"], text=True).strip()
        return p, llamadas, head

    return {"desplegar": desplegar, "app": app, "anterior": anterior, "nuevo": nuevo,
            "despliegues": tmp_path / "despliegues"}


def indice(llamadas, fragmento):
    return next((i for i, l in enumerate(llamadas) if fragmento in l), None)


def sin_corte(e, llamadas, head):
    assert head == e["anterior"]
    assert (e["app"] / ".env").read_text() == "WORKER_MODE=simulado\n"
    assert indice(llamadas, "up -d") is None
    assert not any(l.startswith("docker tag") and l.endswith(":local") for l in llamadas)


def test_exito_sigue_el_orden_y_conserva_las_imagenes_en_ejecucion(entorno):
    p, llamadas, head = entorno["desplegar"]()
    assert p.returncode == 0, p.stderr
    assert head == entorno["nuevo"]
    # Se etiquetan los ids EN EJECUCIÓN, antes del build que reemplaza etiquetas.
    prev = indice(llamadas, "tag sha256:api-en-ejecucion communitylab-api:prev-")
    assert prev is not None and prev < indice(llamadas, " build")
    orden = [indice(llamadas, x) for x in (" build", "probar ", "respaldo", "restaurar ", "db-init", "up -d", "verificar")]
    assert None not in orden and orden == sorted(orden)
    estado = next(entorno["despliegues"].iterdir())
    assert (estado / "env.anterior").read_text() == "WORKER_MODE=simulado\n"
    assert "api api sha256:api-en-ejecucion" in (estado / "imagenes.anteriores").read_text()
    assert (estado / "env.anterior").stat().st_mode & 0o077 == 0  # privado


@pytest.mark.parametrize("falla, ultima", [("build", " build"), ("probar", "probar "),
                                           ("respaldo", "respaldo"), ("restaurar", "restaurar "),
                                           ("migracion", "db-init")])
def test_fallo_antes_del_corte_bloquea_y_no_toca_produccion(entorno, falla, ultima):
    p, llamadas, head = entorno["desplegar"](falla)
    assert p.returncode != 0
    sin_corte(entorno, llamadas, head)
    assert indice(llamadas, ultima) is not None
    siguientes = {"build": "probar ", "probar": "respaldo", "respaldo": "restaurar ",
                  "restaurar": "db-init", "migracion": "up -d"}
    assert indice(llamadas, siguientes[falla]) is None
    assert indice(llamadas, "revertir") is None


@pytest.mark.parametrize("falla", ["up", "salud", "verificar"])
def test_fallo_despues_del_corte_revierte_automaticamente(entorno, falla):
    p, llamadas, _ = entorno["desplegar"](falla)
    assert p.returncode != 0
    estado = next(entorno["despliegues"].iterdir())
    assert f"revertir {estado}" in llamadas


def test_rechaza_env_nuevo_sin_https(entorno, tmp_path):
    env = tmp_path / "sin-https.env"
    env.write_text("WORKER_MODE=gemini\n")
    p = subprocess.run(["bash", str(OPS / "desplegar.sh"), entorno["nuevo"], str(env)], capture_output=True,
                       text=True, env={**os.environ, "APP": str(entorno["app"])}, timeout=60)
    assert p.returncode != 0 and "compose.https.yml" in p.stderr
