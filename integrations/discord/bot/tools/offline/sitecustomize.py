"""Solo para las pruebas: bloquea sockets de red, incluso en subprocesos Python."""
import socket
from contextvars import ContextVar

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_socketpair = socket.socketpair
_local_pair = ContextVar("asyncio_local_socketpair", default=False)


def no_network(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _local_pair.get():
        raise RuntimeError("Las pruebas locales no permiten conexiones de red")
    return _connect(self, address)


def no_network_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _local_pair.get():
        raise RuntimeError("Las pruebas locales no permiten conexiones de red")
    return _connect_ex(self, address)


socket.socket.connect = no_network
socket.socket.connect_ex = no_network_ex


def local_socketpair(*args, **kwargs):
    # Windows implementa socketpair mediante loopback. Solo se permite esa
    # operación síncrona de la biblioteca estándar para arrancar asyncio.
    token = _local_pair.set(True)
    try:
        return _socketpair(*args, **kwargs)
    finally:
        _local_pair.reset(token)


socket.socketpair = local_socketpair
