"""Carga explícita de la lógica de Fabián y exclusión de instancias locales."""
from contextlib import contextmanager
import importlib
import inspect
import os


def load_processor(spec):
    module, separator, name = spec.partition(":")
    if not separator or not module or not name.isidentifier():
        raise ValueError("Usar modulo:funcion")
    processor = getattr(importlib.import_module(module), name)
    if not inspect.iscoroutinefunction(processor):
        raise ValueError("El procesador debe ser async def")
    return processor


@contextmanager
def instance_lock(database):
    database.parent.mkdir(parents=True, exist_ok=True)
    # Archivo separado de SQLite. No borrar: el bloqueo depende del descriptor.
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
