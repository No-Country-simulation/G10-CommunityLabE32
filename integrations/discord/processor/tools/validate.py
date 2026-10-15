"""Pruebas sin credenciales ni red externa, sobre el contrato publicado del bot."""
import os
from pathlib import Path
import subprocess
import sys
import argparse
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
BOT = ROOT.parent / "bot"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependencies", type=Path, help="Directorio local opcional de dependencias aisladas")
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--postgres", action="store_true", help="Usar exclusivamente la BD local de pruebas worker_local")
    args = parser.parse_args()
    allowed = {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    paths = [BOT / "tools/offline", REPO, ROOT, BOT, ROOT.parent / "reader", ROOT.parent / "reader/tests"]
    if args.postgres:
        url = os.environ.get("WORKER_TEST_DATABASE_URL", "")
        parsed = urlparse(url)
        if (parsed.hostname, parsed.port, parsed.path) != ("127.0.0.1", 15439, "/worker_local"):
            parser.error("La BD debe ser 127.0.0.1:15439/worker_local, aislada de datos reales")
        paths[0] = ROOT / "tools/offline"
        env["WORKER_TEST_DATABASE_URL"] = url
        env["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if args.dependencies:
        paths.append(args.dependencies.resolve())
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false",
               PYTHONPATH=os.pathsep.join(map(str, paths)))
    extra = ["--junitxml", str(args.junit.resolve())] if args.junit else []
    if args.postgres:
        subprocess.run([sys.executable, "-B", "-m", "worker.init_db"], cwd=REPO, env=env, check=True)
    return subprocess.call([sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--import-mode=importlib", "-q",
                            *extra, str(ROOT / "tests"), str(BOT / "tests"),
                            str(BOT / "bot_discord/clasificador/test_contrato_io.py"),
                            "integrations/discord/reader/tests", "pipelines/communitylab/tests",
                            "worker/tests/test_worker.py", "worker/tests/test_ia_contract.py"], cwd=REPO, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
