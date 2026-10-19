"""Cliente HTTP mínimo de la API oficial de Discord (solo lecturas GET).

- Las rutas se construyen con IDs validados como snowflakes: el ID del operador nunca es una URL.
- Cabeceras: Authorization «Bot <token>» y un User-Agent «DiscordBot (url, versión)».
- 429: espera `retry_after` (cuerpo) o `Retry-After` (cabecera) si no supera `espera_maxima`; si no,
  se detiene con un error reanudable. Con X-RateLimit-Remaining=0 espera X-RateLimit-Reset-After.
  No se codifican límites fijos (lo pide la documentación) ni se usan varios tokens.
- 5xx, timeouts y errores de red: reintentos acotados con espera creciente.
- 401/403/404 se traducen a errores tipados; ningún error incluye el token ni el contenido.
"""
import time

import httpx

from .configuracion import USER_AGENT
from .fechas import es_snowflake


class ErrorDiscord(Exception):
    codigo = "error_discord"
    reanudable = False

    def __init__(self, http=None, codigo_discord=None, detalle=None):
        super().__init__(self.codigo)
        self.http, self.codigo_discord, self.detalle = http, codigo_discord, detalle

    def como_dict(self):
        return {"codigo": self.codigo, "http": self.http, "codigo_discord": self.codigo_discord,
                "reanudable": self.reanudable, **({"detalle": self.detalle} if self.detalle else {})}


class CredencialInvalida(ErrorDiscord):
    codigo = "credencial_discord_invalida"


class SinPermiso(ErrorDiscord):
    codigo = "sin_permiso_discord"


class NoEncontrado(ErrorDiscord):
    codigo = "no_encontrado_discord"


class LimiteDiscord(ErrorDiscord):
    codigo = "limite_discord"
    reanudable = True


class Transitorio(ErrorDiscord):
    codigo = "error_transitorio_discord"
    reanudable = True


class ClienteDiscord:
    def __init__(self, token, api_base, *, transporte=None, dormir=time.sleep, timeout=15.0,
                 max_reintentos=3, espera_maxima=60.0):
        if not token:
            raise CredencialInvalida(detalle="token_no_configurado")
        self._http = httpx.Client(base_url=api_base, transport=transporte, timeout=timeout,
                                  follow_redirects=False, trust_env=False,
                                  headers={"Authorization": f"Bot {token}", "User-Agent": USER_AGENT})
        self.dormir, self.max_reintentos, self.espera_maxima = dormir, max_reintentos, espera_maxima
        self.peticiones = 0

    def cerrar(self):
        self._http.close()

    def _get(self, ruta, params=None):
        intento = 0
        while True:
            intento += 1
            self.peticiones += 1
            try:
                r = self._http.get(ruta, params=params)
            except (httpx.TimeoutException, httpx.TransportError):
                if intento > self.max_reintentos:
                    raise Transitorio(detalle="red_o_timeout") from None
                self.dormir(min(2 ** intento, 10))
                continue
            if r.status_code == 429:
                espera = self._espera_429(r)
                if espera > self.espera_maxima or intento > self.max_reintentos + 2:
                    raise LimiteDiscord(429, detalle=f"retry_after={espera:.2f}s")
                self.dormir(espera)
                continue
            if 500 <= r.status_code < 600:
                if intento > self.max_reintentos:
                    raise Transitorio(r.status_code)
                self.dormir(min(2 ** intento, 10))
                continue
            codigo = self._codigo(r)
            if r.status_code == 401:
                raise CredencialInvalida(401, codigo)
            if r.status_code == 403:
                raise SinPermiso(403, codigo)
            if r.status_code == 404:
                raise NoEncontrado(404, codigo)
            if r.status_code >= 400:
                raise ErrorDiscord(r.status_code, codigo)
            if r.headers.get("x-ratelimit-remaining") == "0":
                try:
                    self.dormir(min(float(r.headers.get("x-ratelimit-reset-after", "0")), self.espera_maxima))
                except ValueError:
                    pass
            try:
                return r.json()
            except ValueError:
                raise Transitorio(r.status_code, detalle="json_invalido") from None

    @staticmethod
    def _codigo(r):
        try:
            datos = r.json()
            return datos.get("code") if isinstance(datos, dict) else None
        except ValueError:
            return None

    @staticmethod
    def _espera_429(r):
        try:
            datos = r.json()
            if isinstance(datos, dict) and datos.get("retry_after") is not None:
                return max(0.0, float(datos["retry_after"]))
        except ValueError:
            pass
        try:
            return max(0.0, float(r.headers.get("retry-after", "1")))
        except ValueError:
            return 1.0

    @staticmethod
    def _id(valor):
        if not es_snowflake(str(valor)):
            raise ValueError("ID de Discord inválido")
        return str(valor)

    # --- Endpoints (solo GET) ---
    def usuario_actual(self):
        return self._get("/users/@me")

    def canal(self, canal_id):
        return self._get(f"/channels/{self._id(canal_id)}")

    def servidor(self, guild_id):
        return self._get(f"/guilds/{self._id(guild_id)}")

    def roles(self, guild_id):
        return self._get(f"/guilds/{self._id(guild_id)}/roles")

    def miembro(self, guild_id, user_id):
        return self._get(f"/guilds/{self._id(guild_id)}/members/{self._id(user_id)}")

    def mensajes(self, canal_id, before, limite=100):
        if not 1 <= limite <= 100:
            raise ValueError("limit debe estar entre 1 y 100")
        # El cursor puede ser un snowflake «sintético» de un instante (más corto en fechas de 2015).
        if not str(before).isdigit() or len(str(before)) > 20:
            raise ValueError("cursor inválido")
        return self._get(f"/channels/{self._id(canal_id)}/messages",
                         params={"before": str(before), "limit": limite})
