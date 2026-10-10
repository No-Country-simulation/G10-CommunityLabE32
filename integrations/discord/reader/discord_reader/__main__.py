"""CLI. Importar el paquete o pedir ayuda no establece conexión."""

import argparse
import asyncio
from collections import Counter
import logging
import os
from pathlib import Path
import sys

from .core import Config, capture
from .store import Inbox, export_jsonl, CapacityError


def create_client(config):
    """Construye el adaptador sin iniciar sesión ni realizar solicitudes."""
    import discord

    # No se habilitan logs de la librería: podrían contener datos de eventos.
    logging.getLogger("discord").addHandler(logging.NullHandler())
    logging.getLogger("discord").propagate = False
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    inbox = Inbox(config.database, config.max_messages)
    counters = Counter()

    class Reader(discord.Client):
        failed = False
        channels_verified = False

        async def on_ready(self):
            self.channels_verified = False
            if self.failed:
                return
            # Solo consultas a IDs explícitamente configurados.
            verified = set()
            for channel_id in config.channel_ids:
                try:
                    channel = await self.fetch_channel(channel_id)
                    if not isinstance(channel, discord.TextChannel):
                        raise ValueError("Esta entrega solo admite canales de texto.")
                    if channel.guild.id != config.guild_id or channel.guild.me is None:
                        raise ValueError("Servidor incorrecto o bot no disponible.")
                    if not channel.permissions_for(channel.guild.me).view_channel:
                        raise ValueError("Falta permiso para ver el canal.")
                    verified.add(channel_id)
                except Exception:
                    print("error=configuracion_o_acceso_al_canal", file=sys.stderr)
                    self.failed = True
                    await self.close()
                    return
            self.channels_verified = True
            print(f"estado=listo canales_verificados={len(verified)}", flush=True)

        async def on_message(self, message):
            if self.failed:
                return
            if not self.channels_verified:
                counters["antes_de_verificacion"] += 1
                return
            # Verificar también permisos actuales de la caché en cada evento.
            if (message.guild is not None and message.guild.id == config.guild_id
                    and message.channel.id in config.channel_ids):
                if not isinstance(message.channel, discord.TextChannel):
                    counters["tipo_de_canal_no_admitido"] += 1
                    return
                if (message.guild.me is None or not
                        message.channel.permissions_for(message.guild.me).view_channel):
                    counters["sin_permiso_de_lectura"] += 1
                    return
            event, reason = capture(message, config)
            if event is None:
                counters[reason] += 1
                return
            # Canales de texto normales únicamente: no hilos, foros ni DMs.
            if not isinstance(message.channel, discord.TextChannel):
                counters["tipo_de_canal_no_admitido"] += 1
                return
            try:
                saved = await asyncio.to_thread(inbox.save, event)
                counters["guardado" if saved else "duplicado"] += 1
                print("estado=recepcion " + " ".join(
                    f"{key}={value}" for key, value in sorted(counters.items())
                ), flush=True)
            except CapacityError:
                self.failed = True
                print("error=bandeja_llena captura_detenida", file=sys.stderr)
                await self.close()
            except Exception:
                self.failed = True
                print("error=guardado_local captura_detenida", file=sys.stderr)
                await self.close()

        async def on_error(self, event_method, *args, **kwargs):
            # No imprime excepciones, objetos Message ni contenido de usuarios.
            self.failed = True
            print("error=evento_interno captura_detenida", file=sys.stderr)
            await self.close()

        async def on_disconnect(self):
            self.channels_verified = False
            print("estado=desconectado", flush=True)

        async def on_resumed(self):
            await self.on_ready()
            if not self.failed:
                print("estado=sesion_reanudada", flush=True)

    client = Reader(intents=intents, max_messages=None)
    client.counters = counters
    return client


async def listen(config, token):
    client = create_client(config)
    async with client:
        await client.start(token, reconnect=True)
    return 1 if client.failed else 0


def main():
    parser = argparse.ArgumentParser(description="CommunityLab: lector local de Discord")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="Valida configuración sin conectar")
    connect = commands.add_parser("listen", help="Conecta y guarda mensajes nuevos")
    connect.add_argument("--connect", action="store_true", required=True)
    export = commands.add_parser("export", help="Exporta la bandeja a JSONL local")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = Config.load(args.config)
        if args.command == "check-config":
            print(f"configuracion=valida canales={len(config.channel_ids)} sin_conexion=true")
            return 0
        if args.command == "export":
            print(f"exportados={export_jsonl(config.database, args.output)}")
            return 0
        # No se buscan ni se abren archivos .env ni otros almacenes de claves.
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        if not token:
            print("error=falta_DISCORD_BOT_TOKEN", file=sys.stderr)
            return 2
        return asyncio.run(listen(config, token))
    except KeyboardInterrupt:
        print("estado=detenido_por_usuario")
        return 0
    except Exception as exc:
        # Solo el tipo: los mensajes de excepción pueden incorporar secretos.
        print(f"error={type(exc).__name__} revisar_configuracion_dependencias_y_acceso", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
