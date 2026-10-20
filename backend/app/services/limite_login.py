"""Límite de intentos fallidos de login, en memoria del proceso de la API.

Claves: (IP, email) y (IP). Nunca solo el email: así un tercero no puede bloquear la cuenta de
otra persona desde su propia IP. Ventana deslizante y temporal (no hay bloqueos permanentes).
Topología prevista: un único proceso uvicorn detrás de nginx (el contenedor api no publica
puertos). nginx SOBRESCRIBE X-Real-IP con $remote_addr; la API solo la acepta si la conexión llega
desde un proxy declarado en LOGIN_PROXY_CONFIABLE (nombres DNS o IP/CIDR, separados por comas; en
Compose: «proxy», que se resuelve con caché de 30 s). Sin esa variable nunca se confía en la
cabecera: cualquier otro contenedor de la red (web, puente) o un cliente directo que la falsifique
se identifica por su IP real.
Con varias réplicas el contador debería compartirse (p. ej. en PostgreSQL); hoy no aplica.
Configuración: LOGIN_MAX_INTENTOS (5 por IP y email), LOGIN_MAX_INTENTOS_IP (30) y
LOGIN_VENTANA_SEGUNDOS (900). No guarda contraseñas; el email se guarda como huella.
"""
import hashlib
import ipaddress
import os
import socket
import threading
import time
from collections import deque


def _entero(nombre, defecto, minimo, maximo):
    try:
        return min(max(int(os.environ.get(nombre, defecto)), minimo), maximo)
    except ValueError:
        return defecto


class LimiteLogin:
    def __init__(self, reloj=time.monotonic):
        self.reloj = reloj
        self.fallos: dict[tuple, deque] = {}
        self.cerrojo = threading.Lock()

    @staticmethod
    def _limites():
        return (_entero("LOGIN_MAX_INTENTOS", 5, 1, 100), _entero("LOGIN_MAX_INTENTOS_IP", 30, 1, 1000),
                _entero("LOGIN_VENTANA_SEGUNDOS", 900, 10, 86400))

    @staticmethod
    def _claves(ip, email):
        huella = hashlib.sha256(email.encode()).hexdigest()[:24]
        return ("ip-email", ip, huella), ("ip", ip)

    def _vigentes(self, clave, ventana, ahora):
        cola = self.fallos.get(clave)
        if cola is None:
            return 0
        while cola and cola[0] <= ahora - ventana:
            cola.popleft()
        if not cola:
            del self.fallos[clave]
            return 0
        return len(cola)

    def bloqueado(self, ip, email) -> bool:
        maximo, maximo_ip, ventana = self._limites()
        ahora = self.reloj()
        par, solo_ip = self._claves(ip, email)
        with self.cerrojo:
            return self._vigentes(par, ventana, ahora) >= maximo or self._vigentes(solo_ip, ventana, ahora) >= maximo_ip

    def fallo(self, ip, email) -> None:
        ahora = self.reloj()
        with self.cerrojo:
            for clave in self._claves(ip, email):
                self.fallos.setdefault(clave, deque()).append(ahora)

    def exito(self, ip, email) -> None:
        with self.cerrojo:
            self.fallos.pop(self._claves(ip, email)[0], None)

    def reiniciar(self) -> None:
        with self.cerrojo:
            self.fallos.clear()


LIMITE = LimiteLogin()


_CACHE_DNS: dict[str, tuple[float, frozenset]] = {}


def _resolver(nombre, reloj=time.monotonic):
    vigente = _CACHE_DNS.get(nombre)
    if vigente and reloj() - vigente[0] < 30:
        return vigente[1]
    try:
        ips = frozenset(i[4][0] for i in socket.getaddrinfo(nombre, None))
    except OSError:
        ips = frozenset()
    _CACHE_DNS[nombre] = (reloj(), ips)
    return ips


def proxy_confiable(directa: str, configuracion: str | None = None, resolver=_resolver) -> bool:
    """¿La conexión directa viene de un proxy declarado en LOGIN_PROXY_CONFIABLE?"""
    configuracion = os.environ.get("LOGIN_PROXY_CONFIABLE", "") if configuracion is None else configuracion
    try:
        ip = ipaddress.ip_address(directa)
    except ValueError:
        return False
    for entrada in (e.strip() for e in configuracion.split(",")):
        if not entrada:
            continue
        try:
            if ip in ipaddress.ip_network(entrada, strict=False):
                return True
            continue
        except ValueError:
            pass
        if directa in resolver(entrada):
            return True
    return False


def ip_cliente(request, configuracion: str | None = None, resolver=_resolver) -> str:
    """IP del cliente: X-Real-IP solo si la conexión viene de un proxy declarado; si no, la directa."""
    directa = request.client.host if request.client else "desconocida"
    real = request.headers.get("x-real-ip", "").strip()
    if real and proxy_confiable(directa, configuracion, resolver):
        try:
            return str(ipaddress.ip_address(real))
        except ValueError:
            pass
    return directa
