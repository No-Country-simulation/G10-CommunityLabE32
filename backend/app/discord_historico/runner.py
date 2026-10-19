"""Proceso que ejecuta las importaciones pendientes (python -m backend.app.discord_historico.runner).

Corre aparte de la API, para no mantener peticiones HTTP abiertas. Un runner caído no pierde nada:
la reserva vence y la importación se retoma desde su cursor. No envía nada a Discord ni llama a la IA.
"""
import logging
import os
import signal
import time

from .cliente import ClienteDiscord, ErrorDiscord
from .configuracion import Configuracion
from .importador import ejecutar
from .store import Store

LOG = logging.getLogger("communitylab.discord_historico")


def un_ciclo(store, config, fabrica_cliente):
    trabajo = store.reservar()
    if trabajo is None:
        return None
    try:
        cliente = fabrica_cliente(config)
    except ErrorDiscord as e:
        store.finalizar(trabajo, "error", e.como_dict())
        return "error"
    try:
        estado = ejecutar(trabajo, cliente, store, config)
    finally:
        cliente.cerrar()
    # Solo contadores y estado: nunca contenido ni el token.
    LOG.info("importacion=%s estado=%s peticiones=%d", trabajo["id"], estado, cliente.peticiones)
    return estado


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # no registrar cada URL consultada
    config = Configuracion.desde_entorno()
    store = Store(os.environ["DATABASE_URL"])
    intervalo = float(os.environ.get("DISCORD_HISTORICO_INTERVALO", "5"))
    detenido = {"v": False}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: detenido.update(v=True))
    LOG.info("runner de importacion historica iniciado (canales autorizados=%d)",
             sum(len(c) for c in config.autorizados.values()))
    while not detenido["v"]:
        try:
            if un_ciclo(store, config, lambda cfg: ClienteDiscord(cfg.token, cfg.api_base)) is None:
                time.sleep(intervalo)
        except Exception as exc:  # sin detalle: podría incluir datos
            LOG.error("ciclo_fallido tipo=%s", type(exc).__name__)
            time.sleep(intervalo)
    LOG.info("runner detenido")


if __name__ == "__main__":
    main()
