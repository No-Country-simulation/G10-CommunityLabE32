"""Operación como servicio: instancia única por bandeja y latido con estado de conexión."""
from contextlib import contextmanager
import asyncio
import json
import os
from pathlib import Path
import time

INTERVALO_LATIDO = 15


@contextmanager
def instance_lock(database):
    """Impide dos lectores sobre la misma bandeja (mismo patrón que el bot)."""
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with open(str(database) + ".lock", "a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def escribir_latido(ruta, conectado, desconectado_desde, reloj=time.time):
    ruta = Path(ruta)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps({"ts": reloj(), "conectado": conectado,
                                    "desconectado_desde": desconectado_desde}))
    os.replace(temporal, ruta)


def latido_sano(ruta, maximo_latido=60, maximo_desconexion=600, reloj=time.time):
    """Sano si el proceso late y no lleva demasiado tiempo sin sesión verificada.

    Un canal sin mensajes es normal: la salud no depende de recibir eventos.
    """
    try:
        datos = json.loads(Path(ruta).read_text())
        ahora = reloj()
        if ahora - datos["ts"] > maximo_latido:
            return False
        return datos["conectado"] or ahora - datos["desconectado_desde"] <= maximo_desconexion
    except (OSError, ValueError, KeyError, TypeError):
        return False


async def latir(cliente, ruta, reloj=time.time, intervalo=INTERVALO_LATIDO):
    desde = reloj()
    while True:
        conectado = bool(getattr(cliente, "channels_verified", False))
        if conectado:
            desde = None
        elif desde is None:
            desde = reloj()
        await asyncio.to_thread(escribir_latido, ruta, conectado, desde, reloj)
        await asyncio.sleep(intervalo)
