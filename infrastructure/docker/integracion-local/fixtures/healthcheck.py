"""Comprobar actividad reciente del bucle y conexión real a PostgreSQL."""
from pathlib import Path
import time
from fixture import database_ready

try:
    recent = time.time() - float(Path("/tmp/p03-heartbeat").read_text()) < 15
except (OSError, ValueError):
    recent = False
raise SystemExit(0 if recent and database_ready() else 1)
