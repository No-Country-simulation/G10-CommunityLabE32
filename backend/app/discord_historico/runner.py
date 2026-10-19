"""Proceso que ejecuta las importaciones pendientes (python -m backend.app.discord_historico.runner).

Corre aparte de la API, para no mantener peticiones HTTP abiertas. Un runner caído no pierde nada:
la reserva vence y la importación se retoma desde su cursor. No envía nada a Discord ni llama a la IA.

Sin DISCORD_HISTORICO_TOKEN (o con configuración inválida) queda en espera sin reservar nada y sin
reiniciarse en bucle: el resto de la aplicación no depende de él. Escribe un latido en
DISCORD_HISTORICO_LATIDO para la comprobación de salud (`... runner salud`).
Una sola instancia efectiva: la reserva usa FOR UPDATE SKIP LOCKED y un plazo (lease).
"""
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from .cliente import ClienteDiscord, ErrorDiscord
from .configuracion import Configuracion, ConfiguracionInvalida
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


def _latido(ruta, estado):
    if ruta:
        try:
            Path(ruta).write_text(json.dumps({"momento": time.time(), "estado": estado}), encoding="utf-8")
        except OSError:
            LOG.error("latido_no_escrito")


def salud(ruta, intervalo, ahora=None):
    """0 si el latido es reciente (también en espera por falta de configuración); 1 si no.
    Margen amplio: durante una importación larga el latido se renueva solo entre importaciones."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    return 0 if (ahora or time.time()) - float(datos.get("momento", 0)) <= max(600.0, 3 * intervalo + 30) else 1


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # no registrar cada URL consultada
    intervalo = float(os.environ.get("DISCORD_HISTORICO_INTERVALO", "5"))
    latido = os.environ.get("DISCORD_HISTORICO_LATIDO", "")
    detenido = {"v": False}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: detenido.update(v=True))
    try:
        config = Configuracion.desde_entorno()
    except ConfiguracionInvalida as exc:
        LOG.error("configuracion_invalida: %s; runner en espera", exc)
        config = None
    if config is not None and not config.configurada:
        LOG.info("DISCORD_HISTORICO_TOKEN no configurado; runner en espera (la API responde 503)")
        config = None
    if config is None:
        while not detenido["v"]:
            _latido(latido, "sin_configurar")
            time.sleep(intervalo)
        return
    store = Store(os.environ["DATABASE_URL"])
    LOG.info("runner de importacion historica iniciado (canales autorizados=%d)",
             sum(len(c) for c in config.autorizados.values()))
    while not detenido["v"]:
        _latido(latido, "en_espera")
        try:
            if un_ciclo(store, config, lambda cfg: ClienteDiscord(cfg.token, cfg.api_base)) is None:
                time.sleep(intervalo)
        except Exception as exc:  # sin detalle: podría incluir datos
            LOG.error("ciclo_fallido tipo=%s", type(exc).__name__)
            time.sleep(intervalo)
    LOG.info("runner detenido")


if __name__ == "__main__":
    if sys.argv[1:] == ["salud"]:
        sys.exit(salud(os.environ.get("DISCORD_HISTORICO_LATIDO", ""),
                       float(os.environ.get("DISCORD_HISTORICO_INTERVALO", "5"))))
    main()
