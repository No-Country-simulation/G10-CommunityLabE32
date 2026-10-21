"""Completa el nombre visible de autores de Discord ya guardados solo con su ID.

Sin --aplicar NO llama a Discord: informa cuántos mensajes y autores distintos faltan. Con --aplicar
consulta Discord (GET, una vez por autor) con el token del bot: apodo en el servidor, nombre global o
usuario, y lo guarda en mensajes.autor_nombre y discord_mensajes_historicos.autor_nombre. El ID sigue
siendo la identidad. Servidor: el primero de DISCORD_HISTORICO_AUTORIZADOS (o --servidor).
Token: DISCORD_HISTORICO_TOKEN o DISCORD_BOT_TOKEN. Imprime conteos, nunca nombres ni tokens.

Uso (contenedor de la API): python -m backend.scripts.resolver_nombres_discord [--aplicar] [--servidor ID]
"""
import argparse
import json
import os
import time

import httpx
import psycopg
from psycopg.rows import dict_row

API = "https://discord.com/api/v10"
PENDIENTES = """SELECT autor, count(*) n FROM mensajes
    WHERE id_mensaje LIKE 'discord-%%' AND autor ~ '^[0-9]{15,21}$' AND autor_nombre IS NULL GROUP BY autor"""


def nombre_de(cliente, servidor, autor):
    """Apodo en el servidor > nombre global > usuario; None si Discord no lo devuelve."""
    for ruta in (f"/guilds/{servidor}/members/{autor}", f"/users/{autor}"):
        for _ in range(3):
            r = cliente.get(API + ruta)
            if r.status_code == 429:
                time.sleep(min(float((r.json() or {}).get("retry_after", 1)), 10))
                continue
            break
        if r.status_code == 200:
            datos = r.json()
            usuario = datos.get("user", datos)
            nombre = datos.get("nick") or usuario.get("global_name") or usuario.get("username")
            if nombre:
                return " ".join(str(nombre).split())[:150]
    return None


def main(transporte=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true", help="consultar Discord y guardar (por defecto, solo contar)")
    p.add_argument("--servidor", help="ID del servidor (por defecto, el autorizado del histórico)")
    args = p.parse_args()
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    with psycopg.connect(url, row_factory=dict_row) as c:
        pendientes = c.execute(PENDIENTES).fetchall()
        print(f"mensajes_sin_nombre={sum(f['n'] for f in pendientes)} autores_distintos={len(pendientes)} aplicado={args.aplicar}")
        if not args.aplicar or not pendientes:
            return
        servidor = args.servidor or next(iter(json.loads(os.environ.get("DISCORD_HISTORICO_AUTORIZADOS") or "{}")), None)
        token = os.environ.get("DISCORD_HISTORICO_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
        if not servidor or not token:
            raise SystemExit("Falta el servidor (DISCORD_HISTORICO_AUTORIZADOS o --servidor) o el token del bot.")
        resueltos = actualizados = 0
        with httpx.Client(headers={"Authorization": f"Bot {token}", "User-Agent": "DiscordBot (communitylab, 1.0)"},
                          timeout=10, transport=transporte) as cliente:
            for fila in pendientes:
                nombre = nombre_de(cliente, servidor, fila["autor"])
                if nombre is None:
                    continue
                resueltos += 1
                actualizados += c.execute("""UPDATE mensajes SET autor_nombre=%s
                    WHERE autor=%s AND autor_nombre IS NULL""", (nombre, fila["autor"])).rowcount
                c.execute("""UPDATE discord_mensajes_historicos SET autor_nombre=%s
                    WHERE autor_id=%s AND autor_nombre IS NULL""", (nombre, fila["autor"]))
        print(f"autores_resueltos={resueltos} mensajes_actualizados={actualizados}")


if __name__ == "__main__":
    main()
