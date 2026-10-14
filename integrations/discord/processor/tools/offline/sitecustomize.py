"""Pruebas con PostgreSQL: bloquear sockets externos y permitir solo loopback."""
import socket

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def check(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("Red externa bloqueada durante pruebas")


def connect(self, address):
    check(self, address)
    return _connect(self, address)


def connect_ex(self, address):
    check(self, address)
    return _connect_ex(self, address)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
