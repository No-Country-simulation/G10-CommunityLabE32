"""Punto de entrada del worker. Ctrl+C/SIGTERM deja recuperar la reserva."""
import logging
import os
from pathlib import Path
import signal
import threading
import time

from worker.core import Worker
from worker.processor import ProcesadorAislado
from worker.store_postgres import ColaPostgres

HEARTBEAT = Path("/tmp/communitylab-worker-heartbeat")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    detenido = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: detenido.set())
    modo = os.environ["WORKER_MODE"]
    if modo == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("Falta configurar OpenRouter")
    cola = ColaPostgres(os.environ["DATABASE_URL"])
    procesador = ProcesadorAislado(modo, timeout=float(os.getenv("WORKER_TIMEOUT", "120")),
                                  detenido=detenido.is_set)
    def latido():
        HEARTBEAT.write_text(str(time.time()))
    worker = Worker(cola, procesador, latido)
    logging.info("Worker iniciado; modo=%s", modo)
    try:
        while not detenido.is_set():
            try:
                if not worker.ejecutar_uno():
                    detenido.wait(1)
            except Exception as exc:
                # No volcar excepciones externas que contengan lotes/credenciales.
                logging.error("Persistencia temporalmente no disponible (%s)", type(exc).__name__)
                detenido.wait(2)
    except KeyboardInterrupt:
        pass
    finally:
        HEARTBEAT.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
