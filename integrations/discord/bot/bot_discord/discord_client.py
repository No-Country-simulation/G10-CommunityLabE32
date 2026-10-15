"""Adaptador discord.py. Crear el cliente no inicia sesión ni envía mensajes."""
import asyncio
from collections import Counter
import logging

import discord

from .contracts import capture
from .engine import Engine
from .store import Store


def check_channel(channel, config, internal=False):
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("Solo canales de texto normales")
    guild = channel.guild
    if guild.id != config.guild_id or guild.me is None:
        raise ValueError("Servidor no autorizado")
    allowed = {config.internal_channel_id} if internal else config.channel_ids
    if channel.id not in allowed:
        raise ValueError("Canal no autorizado")
    permissions = channel.permissions_for(guild.me)
    if not permissions.view_channel or not permissions.send_messages:
        raise ValueError("Permisos insuficientes")
    if not internal:
        if not permissions.read_message_history:
            raise ValueError("Las respuestas requieren historial de mensajes")
        return
    if channel.permissions_for(guild.default_role).view_channel:
        raise ValueError("El canal interno permite acceso general")
    known_roles = {r.id for r in guild.roles}
    if not config.internal_role_ids <= known_roles:
        raise ValueError("Rol interno desconocido")
    # Administradores/propietario tienen acceso inherente en Discord.
    for role in guild.roles:
        perms = channel.permissions_for(role)
        bot_role = role.tags is not None and role.tags.bot_id == guild.me.id
        if perms.view_channel and not perms.administrator and not bot_role and role.id not in config.internal_role_ids:
            raise ValueError("Rol ajeno al equipo con acceso interno")
    for target, overwrite in channel.overwrites.items():
        if overwrite.view_channel is not True:
            continue
        # Sin members intent, discord.py representa usuarios fuera de caché
        # mediante Object(type=User). También deben pasar la lista autorizada.
        is_user = isinstance(target, (discord.Member, discord.User)) or (
            isinstance(target, discord.Object) and target.type in (discord.User, discord.Member))
        if is_user:
            if target.id != guild.me.id and target.id not in config.internal_user_ids:
                raise ValueError("Acceso individual no autorizado al canal interno")
        elif isinstance(target, discord.Object):
            raise ValueError("Permiso de rol fuera de caché; no se puede verificar")


class DiscordTransport:
    def __init__(self, client, config):
        self.client, self.config = client, config

    async def prepare(self, plan):
        if not self.client.channels_verified:
            raise ValueError("Sesión no verificada")
        channel = await self.client.fetch_channel(plan["channel_id"])
        check_channel(channel, self.config, internal=plan["kind"] == "internal")
        return channel

    async def send(self, channel, plan, source):
        if not self.client.channels_verified:
            raise ValueError("Sesión desconectada")
        # Comprobar de nuevo los permisos de la caché inmediatamente antes de enviar.
        check_channel(channel, self.config, internal=plan["kind"] == "internal")
        kwargs = {"allowed_mentions": discord.AllowedMentions.none(), "suppress_embeds": True}
        if plan["kind"] == "reply":
            kwargs["reference"] = discord.MessageReference(
                message_id=int(source["message_id"]), channel_id=int(source["channel_id"]),
                guild_id=int(source["guild_id"]), fail_if_not_exists=True,
            )
            kwargs["mention_author"] = False
        result = await channel.send(plan["content"], **kwargs)
        return str(result.id)


def create_client(config, processor):
    logging.getLogger("discord").addHandler(logging.NullHandler())
    logging.getLogger("discord").propagate = False
    intents = discord.Intents.none()
    intents.guilds = intents.guild_messages = intents.message_content = True

    class Bot(discord.Client):
        def __init__(self):
            super().__init__(intents=intents, max_messages=None,
                             allowed_mentions=discord.AllowedMentions.none())
            self.failed = False
            self.channels_verified = False
            self.runner = None
            self.counters = Counter()
            self.store = Store(config.database, config.max_records)
            self.engine = Engine(config, self.store, processor, DiscordTransport(self, config))

        async def on_ready(self):
            self.channels_verified = False
            if self.failed:
                return
            try:
                for cid in sorted(config.channel_ids | {config.internal_channel_id}):
                    channel = await self.fetch_channel(cid)
                    check_channel(channel, config, internal=cid == config.internal_channel_id)
            except Exception:
                self.failed = True
                print("error=configuracion_o_permisos")
                await self.close()
                return
            self.channels_verified = True
            if self.runner is None or self.runner.done():
                self.runner = asyncio.create_task(self.consume())
            print("estado=listo")

        async def consume(self):
            try:
                while not self.is_closed():
                    if self.channels_verified and await self.engine.step():
                        print("estado=procesamiento " + str(await asyncio.to_thread(self.store.summary)))
                        continue
                    await asyncio.sleep(0.25)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.failed = True
                print("error=almacenamiento_o_consumidor")
                await self.close()

        async def on_message(self, message):
            if self.failed or not self.channels_verified:
                return
            if not isinstance(message.channel, discord.TextChannel):
                self.counters["filtrado"] += 1
                return
            try:
                event = capture(message, config)
                if event is None:
                    self.counters["filtrado"] += 1
                    return
                check_channel(message.channel, config)
            except (ValueError, TypeError):
                self.counters["filtrado"] += 1
                return
            try:
                saved = await self.engine.submit(event)
                self.counters["encolado" if saved else "duplicado"] += 1
            except ValueError:
                self.counters["conflicto_id"] += 1
            except Exception:
                self.failed = True
                print("error=cola_local captura_detenida")
                await self.close()

        async def on_disconnect(self):
            self.channels_verified = False

        async def on_resumed(self):
            await self.on_ready()

        async def on_error(self, event_method, *args, **kwargs):
            self.failed = True
            print("error=evento_interno")
            await self.close()

        async def close(self):
            self.channels_verified = False
            if self.runner and self.runner is not asyncio.current_task():
                self.runner.cancel()
                await asyncio.gather(self.runner, return_exceptions=True)
            await super().close()

    return Bot()
