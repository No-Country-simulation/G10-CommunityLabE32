"""Comprueba el bucle del worker y PostgreSQL; no certifica una llamada LLM."""
import os
import time
from pathlib import Path
import psycopg
HEARTBEAT = Path('/tmp/communitylab-worker-heartbeat')
try:
    recent = time.time() - float(HEARTBEAT.read_text()) < 15
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=3) as c:
        ready = c.execute('SELECT 1').fetchone()[0] == 1
except (OSError, ValueError, psycopg.Error):
    recent = False
    ready = False
raise SystemExit(0 if recent and ready else 1)
