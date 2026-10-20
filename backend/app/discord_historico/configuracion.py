"""Configuración de la importación histórica (solo variables de entorno del backend).

- DISCORD_HISTORICO_TOKEN: token del bot. Solo en el backend; nunca viaja al frontend ni a respuestas.
- DISCORD_HISTORICO_AUTORIZADOS: JSON {"<id_servidor>": ["<id_canal>", ...]}. Lista explícita y
  propia de esta herramienta (no amplía ni lee la del lector en vivo). Sin ella, nada está autorizado.
- Límites: DISCORD_HISTORICO_MAX_MENSAJES (por importación), DISCORD_HISTORICO_MAX_DIAS,
  DISCORD_HISTORICO_CONFIRMAR_DIAS / _CONFIRMAR_MENSAJES (umbrales que exigen confirmar el alcance).
- DISCORD_API_BASE solo se puede cambiar para pruebas locales con DISCORD_HISTORICO_BASE_PRUEBA=1 y
  un host local; en cualquier otro caso se usa la API oficial v10.
"""
from dataclasses import dataclass, field
import json
import os
from urllib.parse import urlparse

from .fechas import es_snowflake

API_OFICIAL = "https://discord.com/api/v10"
HOSTS_PRUEBA = {"127.0.0.1", "localhost", "discord-falso"}
USER_AGENT = "DiscordBot (https://github.com/No-Country-simulation/G10-CommunityLabE32, 1.0)"


class ConfiguracionInvalida(ValueError):
    pass


def _entero(env, nombre, defecto, minimo, maximo):
    try:
        valor = int(env.get(nombre, defecto))
    except (TypeError, ValueError):
        raise ConfiguracionInvalida(f"{nombre} debe ser un entero") from None
    if not minimo <= valor <= maximo:
        raise ConfiguracionInvalida(f"{nombre} fuera de rango [{minimo}, {maximo}]")
    return valor


@dataclass(frozen=True)
class Configuracion:
    token: str = field(repr=False, default="")
    autorizados: dict = field(default_factory=dict)      # {guild_id: frozenset(canal_ids)}
    max_mensajes: int = 5000
    max_dias: int = 400
    confirmar_dias: int = 31
    confirmar_mensajes: int = 1000
    api_base: str = API_OFICIAL

    @property
    def configurada(self):
        return bool(self.token)

    def servidor_de(self, canal_id):
        """Servidor autorizado al que pertenece el canal, o None (sin consultar a Discord)."""
        for guild_id, canales in self.autorizados.items():
            if canal_id in canales:
                return guild_id
        return None

    @classmethod
    def desde_entorno(cls, env=None):
        env = os.environ if env is None else env
        crudo = env.get("DISCORD_HISTORICO_AUTORIZADOS", "").strip()
        autorizados = {}
        if crudo:
            try:
                datos = json.loads(crudo)
            except ValueError:
                raise ConfiguracionInvalida("DISCORD_HISTORICO_AUTORIZADOS no es JSON válido") from None
            if not isinstance(datos, dict):
                raise ConfiguracionInvalida("DISCORD_HISTORICO_AUTORIZADOS debe ser un objeto")
            for guild_id, canales in datos.items():
                if not es_snowflake(guild_id) or not isinstance(canales, list) \
                        or not all(es_snowflake(c) for c in canales):
                    raise ConfiguracionInvalida("DISCORD_HISTORICO_AUTORIZADOS: IDs deben ser snowflakes")
                autorizados[guild_id] = frozenset(canales)
        base = env.get("DISCORD_API_BASE", "").strip() or API_OFICIAL
        if base != API_OFICIAL:
            host = urlparse(base).hostname
            if env.get("DISCORD_HISTORICO_BASE_PRUEBA") != "1" or host not in HOSTS_PRUEBA:
                raise ConfiguracionInvalida("DISCORD_API_BASE solo puede cambiarse para pruebas locales")
        return cls(
            token=env.get("DISCORD_HISTORICO_TOKEN", "").strip(),
            autorizados=autorizados,
            max_mensajes=_entero(env, "DISCORD_HISTORICO_MAX_MENSAJES", 5000, 1, 50000),
            max_dias=_entero(env, "DISCORD_HISTORICO_MAX_DIAS", 400, 1, 4000),
            confirmar_dias=_entero(env, "DISCORD_HISTORICO_CONFIRMAR_DIAS", 31, 1, 4000),
            confirmar_mensajes=_entero(env, "DISCORD_HISTORICO_CONFIRMAR_MENSAJES", 1000, 1, 50000),
            api_base=base.rstrip("/"),
        )
