"""Contrato propuesto para Fabián; no contiene clasificación ni prompts."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


def snowflake(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdigit()
            or not 0 < int(value) < 2**64 or str(int(value)) != value):
        raise ValueError("ID inválido")
    return int(value)


def text(value, maximum):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Texto requerido")
    if len(value.encode("utf-16-le")) // 2 > maximum:
        raise ValueError("Texto demasiado largo")
    return value


@dataclass(frozen=True)
class Config:
    guild_id: int
    channel_ids: frozenset
    internal_channel_id: int
    internal_role_ids: frozenset
    internal_user_ids: frozenset
    database: Path
    max_records: int = 10000
    processor_timeout: int = 60

    @classmethod
    def load(cls, filename):
        path = Path(filename).resolve()
        d = json.loads(path.read_text(encoding="utf-8-sig"))
        required = {"guild_id", "channel_ids", "internal_channel_id", "internal_role_ids"}
        optional = {"internal_user_ids", "database", "max_records", "processor_timeout"}
        if not isinstance(d, dict) or not required <= d.keys() or d.keys() - required - optional:
            raise ValueError("Configuración inválida")
        def ids(name, required=True):
            values = d.get(name, [])
            if not isinstance(values, list) or (required and not values):
                raise ValueError("Lista de IDs requerida")
            return frozenset(snowflake(v) for v in values)
        guild = snowflake(d["guild_id"])
        channels = ids("channel_ids")
        internal = snowflake(d["internal_channel_id"])
        roles = ids("internal_role_ids")
        if internal in channels or guild in roles:
            raise ValueError("El destino interno debe estar separado; no autorizar @everyone")
        capacity, timeout = d.get("max_records", 10000), d.get("processor_timeout", 60)
        if type(capacity) is not int or not 1 <= capacity <= 1000000:
            raise ValueError("Capacidad inválida")
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError("Tiempo límite inválido")
        database = text(d.get("database", "data/bot.sqlite3"), 1024)
        return cls(guild, channels, internal, roles, ids("internal_user_ids", False),
                   (path.parent / database).resolve(), capacity, timeout)


SOURCE_KEYS = {"schema_version", "message_id", "guild_id", "channel_id", "author_id", "created_at", "content"}


def validate_source(event, config):
    if not isinstance(event, dict) or set(event) != SOURCE_KEYS:
        raise ValueError("Evento fuente inválido")
    if event["schema_version"] != "discord-source-v1":
        raise ValueError("Versión fuente inválida")
    for field in ("message_id", "guild_id", "channel_id", "author_id"):
        snowflake(event[field])
    if int(event["guild_id"]) != config.guild_id or int(event["channel_id"]) not in config.channel_ids:
        raise ValueError("Origen no autorizado")
    date = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("Fecha sin zona horaria")
    text(event["content"], 4000)
    return dict(event)


def capture(message, config):
    # Mismo evento fuente que el lector 07-10. Filtrar antes de leer contenido.
    if message.guild is None or message.guild.id != config.guild_id:
        return None
    if message.channel.id not in config.channel_ids:
        return None
    if message.author.bot or message.webhook_id is not None or message.is_system():
        return None
    if not message.content or not message.content.strip():
        return None
    return validate_source({
        "schema_version": "discord-source-v1", "message_id": str(message.id),
        "guild_id": str(message.guild.id), "channel_id": str(message.channel.id),
        "author_id": str(message.author.id),
        "created_at": message.created_at.astimezone(timezone.utc).isoformat(),
        "content": message.content,
    }, config)


DECISION_KEYS = {"schema_version", "message_id", "es_duda", "es_logro", "es_bloqueo",
                 "tema", "respuesta", "alerta"}


def validate_decision(value, event):
    if not isinstance(value, dict) or set(value) != DECISION_KEYS:
        raise ValueError("Decisión inválida")
    if value["schema_version"] != "discord-decision-v1" or value["message_id"] != event["message_id"]:
        raise ValueError("Decisión de otra fuente o versión")
    if any(type(value[k]) is not bool for k in ("es_duda", "es_logro", "es_bloqueo")):
        raise ValueError("Las señales deben ser booleanas")
    text(value["tema"], 100)
    if not isinstance(value["respuesta"], str) or not isinstance(value["alerta"], str):
        raise ValueError("Los textos deben ser cadenas")
    if value["es_bloqueo"]:
        text(value["alerta"], 1700)
        if value["respuesta"]:
            raise ValueError("Un bloqueo nunca admite respuesta pública")
    elif value["es_duda"]:
        text(value["respuesta"], 1900)
        if value["alerta"]:
            raise ValueError("Alerta sin bloqueo")
    elif value["respuesta"] or value["alerta"]:
        raise ValueError("No publicar automáticamente testimonios u otros mensajes")
    return dict(value)


def delivery(event, decision, config):
    validate_source(event, config)
    d = validate_decision(decision, event)
    if d["es_bloqueo"]:
        link = f"https://discord.com/channels/{event['guild_id']}/{event['channel_id']}/{event['message_id']}"
        return {"kind": "internal", "channel_id": config.internal_channel_id,
                "content": f"Alerta interna de bloqueo\n{d['alerta']}\nFuente: {link}"}
    if d["es_duda"]:
        return {"kind": "reply", "channel_id": int(event["channel_id"]), "content": d["respuesta"]}
    return None
