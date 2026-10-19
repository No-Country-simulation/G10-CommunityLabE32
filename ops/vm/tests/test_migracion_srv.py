"""migrar-a-srv.sh con un `docker` falso y rutas temporales (sin root, sin Docker ni red).

Verifica que `comprobar` no cambia nada, que `ejecutar` mueve la aplicación sin `down -v` e instala
los cl-* con la ruta nueva, y que un fallo durante el corte deshace la mudanza por completo.
"""
import getpass
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
echo "docker $* @ $PWD" >> "$REGISTRO"
case "$*" in
  *"up -d"*) [ -n "$FALLA_UP_EN" ] && [ "$PWD" = "$FALLA_UP_EN" ] && exit 1 ;;
  "compose ps -a --format"*) echo "api|running|healthy|0" ;;
esac
exit 0
"""


def ejecutable(ruta, contenido):
    ruta.write_text(contenido)
    ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def entorno(tmp_path):
    origen = tmp_path / "home" / "tareck" / "G10-CommunityLabE32"
    shutil.copytree(OPS, origen / "ops" / "vm", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (origen / "docker-compose.yml").write_text("services: {}\n")
    (origen / ".gitignore").write_text(".env\n")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(origen)]
    subprocess.run(["git", "init", "-q", str(origen)], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "base"], check=True)
    (origen / ".env").write_text("COMPOSE_PROJECT_NAME=g10-communitylabe32\n"
                                 "COMPOSE_FILE=docker-compose.yml:compose.https.yml\n")
    (origen / ".env").chmod(0o600)
    destino = tmp_path / "srv" / "communitylab"
    destino.parent.mkdir()
    sbin = tmp_path / "sbin"
    sbin.mkdir()
    (sbin / "cl-estado").write_text("#!/bin/bash\n# version anterior\n")
    sudoers = tmp_path / "sudoers.d" / "50-operadores"
    sudoers.parent.mkdir()
    sudoers.write_text("# regla anterior\n")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    ejecutable(bin_ / "docker", DOCKER_FALSO)
    ejecutable(bin_ / "falso-respaldo", '#!/bin/bash\necho "$RESPALDOS/falso"\n')
    ejecutable(bin_ / "falso-restaurar", "#!/bin/bash\nexit 0\n")
    ejecutable(bin_ / "visudo-falso", '#!/bin/bash\necho "visudo $*" >> "$REGISTRO"\nexit 0\n')
    registro = tmp_path / "registro.log"
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "REGISTRO": str(registro),
           "ORIGEN": str(origen), "DESTINO": str(destino), "BIN": str(sbin), "USUARIO_APP": getpass.getuser(),
           "ESTADO_MIGRACION": str(tmp_path / "estado"), "RESPALDOS": str(tmp_path / "respaldos"),
           "RESPALDO_CMD": str(bin_ / "falso-respaldo"), "RESTAURAR_CMD": str(bin_ / "falso-restaurar"),
           "PERMITIR_NO_ROOT": "1", "VERIFICAR_URLS": "", "ESPERA_SALUD": "1",
           "SUDOERS_DESTINO": str(sudoers), "VISUDO": str(bin_ / "visudo-falso"),
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"}

    def correr(modo, **extra):
        p = subprocess.run(["bash", str(OPS / "migrar-a-srv.sh"), modo], capture_output=True, text=True,
                           env={**env, **extra}, timeout=120)
        return p, (registro.read_text().splitlines() if registro.exists() else [])

    return {"correr": correr, "origen": origen, "destino": destino, "sbin": sbin, "sudoers": sudoers}


def test_comprobar_no_cambia_nada(entorno):
    p, llamadas = entorno["correr"]("comprobar")
    assert p.returncode == 0, p.stderr
    assert entorno["origen"].is_dir() and not entorno["destino"].exists()
    assert not any("down" in l or "up -d" in l for l in llamadas)


def test_sin_nombre_de_proyecto_fijo_se_detiene_antes_de_tocar_nada(entorno):
    env = entorno["origen"] / ".env"
    env.write_text("COMPOSE_FILE=docker-compose.yml:compose.https.yml\n")
    p, llamadas = entorno["correr"]("ejecutar")
    assert p.returncode == 1 and "volúmenes vacíos" in p.stderr
    assert entorno["origen"].is_dir() and not entorno["destino"].exists() and llamadas == []


def test_ejecutar_mueve_sin_borrar_volumenes_e_instala_la_ruta_nueva(entorno):
    p, llamadas = entorno["correr"]("ejecutar")
    assert p.returncode == 0, p.stderr
    destino = entorno["destino"]
    assert not entorno["origen"].exists() and (destino / ".git").is_dir()
    assert stat.S_IMODE((destino / ".env").stat().st_mode) == 0o600
    assert stat.S_IMODE(destino.stat().st_mode) == 0o750
    abajo = next(i for i, l in enumerate(llamadas) if "compose down" in l)
    arriba = next(i for i, l in enumerate(llamadas) if "up -d" in l)
    assert abajo < arriba and str(destino) in llamadas[arriba]
    assert not any(" -v" in l or "prune" in l for l in llamadas)
    assert "/srv/communitylab" in (entorno["sbin"] / "cl-actualizar").read_text()
    assert (entorno["sbin"] / "communitylab-certbot-post").exists()
    assert (entorno["sbin"] / "cl-token-operador").exists()
    assert "/usr/local/sbin/cl-token-operador" in entorno["sudoers"].read_text()
    assert stat.S_IMODE(entorno["sudoers"].stat().st_mode) == 0o440
    assert any(l.startswith("visudo -cf") for l in llamadas) and any(l.strip() == "visudo -c" for l in llamadas)


def test_cl_token_operador_solo_imprime_el_token(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / ".env").write_text("POSTGRES_PASSWORD=secreto-db\nOPERADOR_TOKEN=token-de-prueba\nPUENTE_TOKEN=otro\n")
    p = subprocess.run(["bash", str(OPS / "cl-token-operador")], capture_output=True, text=True,
                       env={**os.environ, "CL_APP": str(app)}, timeout=30)
    assert (p.returncode, p.stdout) == (0, "token-de-prueba\n")
    assert "secreto-db" not in p.stdout + p.stderr and "otro" not in p.stdout + p.stderr
    (app / ".env").write_text("POSTGRES_PASSWORD=x\n")
    p = subprocess.run(["bash", str(OPS / "cl-token-operador")], capture_output=True, text=True,
                       env={**os.environ, "CL_APP": str(app)}, timeout=30)
    assert p.returncode == 1 and p.stdout == ""


def test_fallo_en_el_corte_deshace_la_mudanza(entorno):
    p, llamadas = entorno["correr"]("ejecutar", FALLA_UP_EN=str(entorno["destino"]))
    assert p.returncode == 1
    assert entorno["origen"].is_dir() and not entorno["destino"].exists()
    assert (entorno["sbin"] / "cl-estado").read_text() == "#!/bin/bash\n# version anterior\n"
    assert not (entorno["sbin"] / "cl-token-operador").exists()       # comando nuevo retirado
    assert entorno["sudoers"].read_text() == "# regla anterior\n"       # regla sudo restaurada
    assert any("up -d" in l and str(entorno["origen"]) in l for l in llamadas)  # vuelve a levantar en el origen
