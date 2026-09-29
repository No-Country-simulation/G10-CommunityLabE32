"""Sonda temporal de infraestructura; no ingiere ni procesa mensajes con IA."""
import os
from pathlib import Path
import subprocess
import time

HEARTBEAT = Path('/tmp/communitylab-worker-heartbeat')

def database_ready():
    try:
        result = subprocess.run(['psql', '-X', '-tAc', 'SELECT 1'],
                                capture_output=True, timeout=3)
        return result.returncode == 0 and result.stdout.strip() == b'1'
    except (OSError, subprocess.TimeoutExpired):
        return False

if __name__ == '__main__':
    print('Worker SONDA iniciado: conexión SQL, sin procesamiento IA.', flush=True)
    while True:
        # Gancho local de prueba: simula una falla del proceso, no una parada Docker.
        fail = Path('/tmp/communitylab-worker-fail-once')
        if fail.exists():
            fail.unlink()
            os._exit(17)
        if database_ready():
            HEARTBEAT.write_text(str(time.time()))
        else:
            HEARTBEAT.unlink(missing_ok=True)
        time.sleep(2)
