"""Ejecuta pruebas sin claves, red, bytecode ni cachés dentro del repositorio."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
READER = ROOT.parent / "reader"



def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def fingerprint():
    files = git("ls-files", "-z").decode().split("\0")
    return {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in files if name}


def main():
    evidence = ROOT / "evidencias"
    evidence.mkdir(exist_ok=True)
    sha = git("rev-parse", "HEAD").decode().strip()
    status_before = git("status", "--porcelain")
    before = fingerprint()
    # No se heredan tokens ni variables de proveedores, DB o trazas del host.
    allowed = {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false",
               PYTHONPATH=os.pathsep.join(map(str, (ROOT / "tools/offline", ROOT, REPO, READER))))
    suites = {
        "bot_y_compatibilidad": ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
        "grafo_repositorio": ["-m", "unittest", "discover", "-s", str(REPO / "pipelines/communitylab/tests"), "-v"],
        "worker_repositorio": ["-m", "pytest", "-p", "no:cacheprovider", "-v", "-ra", str(REPO / "worker/tests/test_worker.py"), str(REPO / "worker/tests/test_ia_contract.py")],
        "lector_anterior": ["-m", "unittest", "discover", "-s", str(READER / "tests"), "-v"],
        "configuracion": ["-m", "bot_discord", "--config", "config.example.json", "check-config"],
        "dependencias": ["-m", "pip", "check"],
    }
    results = {}
    for name, args in suites.items():
        run = subprocess.run([sys.executable, "-B", *args], cwd=ROOT, env=env,
                             capture_output=True, text=True, encoding="utf-8", timeout=180)
        (evidence / (name + ".txt")).write_text(run.stdout + run.stderr, encoding="utf-8")
        results[name] = {"returncode": run.returncode}
        print(name, "OK" if run.returncode == 0 else "FALLO", flush=True)
    unchanged = before == fingerprint() and status_before == git("status", "--porcelain")
    report = {"ejecutado_utc": datetime.now(timezone.utc).isoformat(), "repo_sha": sha,
              "fuentes_repositorio_sin_cambios": unchanged, "resultados": results,
              "alcance": "Discord e IA simulados; sin VM ni PostgreSQL"}
    (evidence / "resumen.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("fuentes_repositorio_sin_cambios=" + str(unchanged))
    return int(not unchanged or any(r["returncode"] for r in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
