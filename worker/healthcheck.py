"""Comprueba el bucle de la sonda y una consulta real a PostgreSQL."""
import time
from probe import HEARTBEAT, database_ready
try:
    recent = time.time() - float(HEARTBEAT.read_text()) < 15
except (OSError, ValueError):
    recent = False
raise SystemExit(0 if recent and database_ready() else 1)
