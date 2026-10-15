"""Configuración y captura independiente de la conexión de Discord."""

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
import json


def snowflake(value):
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("Los identificadores deben ser cadenas de dígitos ASCII.")
    if not 0 < int(value) < 2**64:
        raise ValueError("Identificador fuera de rango.")
    return int(value)


@dataclass(frozen=True)
class Config:
    guild_id: int
    channel_ids: frozenset[int]
    database: Path
    max_messages: int

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("La configuración debe ser un objeto JSON.")
        guild = snowflake(data.get("guild_id"))
        channels = data.get("channel_ids")
        if not isinstance(channels, list) or not channels:
            raise ValueError("Se necesita una lista explícita de canales autorizados.")
        channels = frozenset(snowflake(value) for value in channels)
        maximum = data.get("max_messages", 10000)
        if type(maximum) is not int or not 1 <= maximum <= 1000000:
            raise ValueError("max_messages debe estar entre 1 y 1000000.")
        database = data.get("database", "data/discord.sqlite3")
        if not isinstance(database, str) or not database.strip():
            raise ValueError("Se necesita una ruta local para la base de datos.")
        return cls(guild, channels, (path.parent / database).resolve(), maximum)


def capture(message, config):
    """Devuelve (evento fuente, motivo). Filtra antes de leer el contenido.

    La autorización no se hereda del canal padre. El adaptador de conexión
    excluye los hilos. La transformación a Interaccion es tarea de Santiago.
    """
    if message.guild is None or message.guild.id != config.guild_id:
        return None, "servidor_no_autorizado"
    if message.channel.id not in config.channel_ids:
        return None, "canal_no_autorizado"
    if message.author.bot or message.webhook_id is not None:
        return None, "bot_o_webhook"
    if message.is_system():
        return None, "mensaje_de_sistema"
    if not message.content or not message.content.strip():
        return None, "sin_texto"
    return {
        "schema_version": "discord-source-v1",
        "message_id": str(message.id),
        "guild_id": str(message.guild.id),
        "channel_id": str(message.channel.id),
        "author_id": str(message.author.id),
        "created_at": message.created_at.astimezone(timezone.utc).isoformat(),
        "content": message.content,
    }, "aceptado"
