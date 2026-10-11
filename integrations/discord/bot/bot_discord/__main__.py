import argparse
import asyncio
import os
from pathlib import Path

from .contracts import Config
from .runtime import instance_lock, load_processor
from .store import Store


async def listen(config, processor, token):
    from .discord_client import create_client
    client = create_client(config, processor)
    async with client:
        await client.start(token, reconnect=True)
    return 1 if client.failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Bot CommunityLab: transporte de Paulo")
    p.add_argument("--config", type=Path, default=Path("config.json"))
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config")
    commands.add_parser("status")
    retry = commands.add_parser("retry")
    retry.add_argument("--key", required=True, help="guild_id:message_id")
    live = commands.add_parser("listen")
    live.add_argument("--connect", action="store_true", required=True)
    live.add_argument("--processor", required=True, help="modulo_fabian:procesar")
    args = p.parse_args(argv)
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
            return asyncio.run(listen(config, processor, token))
    except KeyboardInterrupt:
        print("estado=detenido")
        return 0
    except Exception:
        print("error=configuracion_dependencias_o_ejecucion revisar_guia")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
