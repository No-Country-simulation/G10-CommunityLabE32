import argparse
import asyncio
import os
from pathlib import Path

from .contracts import Config
from .runtime import instance_lock, load_processor
from .store import Store


async def listen(config, processor, token, latido=None):
    from .discord_client import create_client
    from .servicio import latir
    client = create_client(config, processor)
    async with client:
        tarea = asyncio.create_task(latir(client, latido)) if latido else None
        try:
            await client.start(token, reconnect=True)
        finally:
            if tarea:
                tarea.cancel()
    return 1 if client.failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Bot CommunityLab: transporte de Paulo")
    p.add_argument("--config", type=Path, default=Path("config.json"))
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config")
    salud = commands.add_parser("salud")
    salud.add_argument("--latido", type=Path, default=Path(os.environ.get("BOT_LATIDO", "/tmp/communitylab-bot-latido.json")))
    commands.add_parser("status")
    retry = commands.add_parser("retry")
    retry.add_argument("--key", required=True, help="guild_id:message_id")
    live = commands.add_parser("listen")
    live.add_argument("--connect", action="store_true", required=True)
    live.add_argument("--processor", required=True, help="modulo_fabian:procesar")
    args = p.parse_args(argv)
    if args.command == "salud":
        from .servicio import latido_sano
        return 0 if latido_sano(args.latido) else 1
    try:
        config = Config.load(args.config)
        if args.command == "check-config":
            print("configuracion=valida sin_conexion=true permisos_reales=pendientes")
            return 0
        with instance_lock(config.database):
            store = Store(config.database, config.max_records)
            if args.command == "status":
                print(store.summary())
                return 0
            if args.command == "retry":
                store.retry(args.key)
                print("estado=reencolado sin_conexion=true")
                return 0
            token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
            if not token:
                print("error=falta_DISCORD_BOT_TOKEN")
                return 2
            processor = load_processor(args.processor)
            store.recover_interrupted()
            return asyncio.run(listen(config, processor, token,
                                      os.environ.get("BOT_LATIDO", "").strip() or None))
    except KeyboardInterrupt:
        print("estado=detenido")
        return 0
    except Exception:
        print("error=configuracion_dependencias_o_ejecucion revisar_guia")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
