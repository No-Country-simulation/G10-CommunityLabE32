"""Límite de intentos fallidos de login, en memoria del proceso de la API.

Claves: (IP, email) y (IP). Nunca solo el email: así un tercero no puede bloquear la cuenta de
otra persona desde su propia IP. Ventana deslizante y temporal (no hay bloqueos permanentes).
Topología prevista: un único proceso uvicorn detrás de nginx (el contenedor api no publica
puertos); la IP real llega en X-Real-IP y solo se acepta si la conexión viene de una red privada.
Con varias réplicas el contador debería compartirse (p. ej. en PostgreSQL); hoy no aplica.
Configuración: LOGIN_MAX_INTENTOS (5 por IP y email), LOGIN_MAX_INTENTOS_IP (30) y
LOGIN_VENTANA_SEGUNDOS (900). No guarda contraseñas; el email se guarda como huella.
"""
import hashlib
import ipaddress
import os
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


def ip_cliente(request) -> str:
    """IP del cliente. X-Real-IP (lo fija nginx) solo se acepta de una conexión desde red privada."""
    directa = request.client.host if request.client else "desconocida"
    real = request.headers.get("x-real-ip", "").strip()
    try:
        if real and ipaddress.ip_address(directa).is_private:
            return str(ipaddress.ip_address(real))
    except ValueError:
        pass
    return directa
