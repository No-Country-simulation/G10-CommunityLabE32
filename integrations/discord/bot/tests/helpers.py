from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock
import discord
from bot_discord.contracts import Config


def config(path):
    return Config(100, frozenset({200}), 300, frozenset({400}), frozenset(), path, 100, 1)


def source(mid="600"):
    return {"schema_version": "discord-source-v1", "message_id": mid,
            "guild_id": "100", "channel_id": "200", "author_id": "700",
            "created_at": "2026-10-08T12:00:00+00:00", "content": "Mensaje ficticio"}


def decision(mid="600", kind="duda"):
    return {"schema_version": "discord-decision-v1", "message_id": mid,
            "es_duda": kind == "duda", "es_logro": kind == "logro", "es_bloqueo": kind == "bloqueo",
            "tema": "python", "respuesta": "Respuesta ficticia" if kind == "duda" else "",
            "alerta": "Solicitud ficticia de apoyo" if kind == "bloqueo" else ""}


def channels():
    everyone = NS(id=100, tags=None)
    staff = NS(id=400, tags=None)
    bot_role = NS(id=500, tags=NS(bot_id=900))
    guild = NS(id=100, me=NS(id=900), default_role=everyone, roles=[everyone, staff, bot_role])
    result = {}
    for cid in (200, 300):
        c = Mock(spec=discord.TextChannel)
        c.id, c.guild, c.overwrites = cid, guild, {}
        c.permissions_for.side_effect = lambda target, internal=cid == 300: NS(
            view_channel=not internal or target.id in {400, 500, 900},
            send_messages=True, read_message_history=True, administrator=False)
        c.send = AsyncMock(return_value=NS(id=800))
        result[cid] = c
    return result


def message(origin, **changes):
    values = dict(id=600, guild=origin.guild, channel=origin, author=NS(id=700, bot=False),
                  webhook_id=None, content="Mensaje ficticio", is_system=lambda: False,
                  created_at=datetime(2026, 10, 8, 12, tzinfo=timezone.utc))
    values.update(changes)
    return NS(**values)
