"""Discord FALSO para desarrollo y pruebas locales de la importación histórica. Solo GET y datos ficticios;
nunca contacta discord.com. No usar en producción.

    python -m uvicorn --app-dir tools discord_falso_historico:app --host 127.0.0.1 --port 15442

El backend solo acepta esta base con DISCORD_HISTORICO_BASE_PRUEBA=1 y host 127.0.0.1/localhost/discord-falso
(ver docs/contrato-frontend-discord-historico.md, sección «Ejecutar en local»). Canal 222222222222222222 del
servidor 111111111111111111: 240 mensajes ficticios cada 2 h desde 2026-09-01 (hora de Guatemala), 1 de bot y 1
anterior al rango. GET /_registro lista las peticiones recibidas (para comprobar que solo hubo GET).
"""
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

EPOCH = 1420070400000
GUILD, CANAL, BOT = "111111111111111111", "222222222222222222", "999999999999999999"
LECTURA = (1 << 10) | (1 << 16)
app = FastAPI()
registro = []


def _sf(dt, n):
    return str(((int(dt.timestamp() * 1000) - EPOCH) << 22) | n)


MENSAJES = []
inicio = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
for i in range(240):                     # 240 humanos ficticios cada 2 h desde 2026-09-01 Guatemala
    MENSAJES.append({"id": _sf(inicio + timedelta(hours=2 * i), i), "type": 0, "content": f"mensaje ficticio {i}",
                     "author": {"id": "700000000000000001"}, "attachments": [], "embeds": []})
MENSAJES.append({"id": _sf(inicio + timedelta(minutes=5), 900), "type": 0, "content": "soy un bot",
                 "author": {"id": "700000000000000002", "bot": True}})
MENSAJES.append({"id": _sf(inicio - timedelta(days=3), 901), "type": 0, "content": "anterior al rango",
                 "author": {"id": "700000000000000001"}})


@app.middleware("http")
async def registrar(request: Request, siguiente):
    registro.append([request.method, request.url.path])
    if request.url.path.startswith("/_registro"):
        return await siguiente(request)
    if request.method != "GET":
        return JSONResponse({"message": "solo GET"}, 405)
    if request.headers.get("authorization", "").split(" ")[0] != "Bot":
        return JSONResponse({"message": "401"}, 401)
    return await siguiente(request)


@app.get("/_registro")
def ver_registro():
    return registro


@app.get("/api/v10/users/@me")
def yo():
    return {"id": BOT, "bot": True}


@app.get("/api/v10/channels/{canal}")
def canal(canal: str):
    if canal != CANAL:
        return JSONResponse({"code": 10003}, 404)
    return {"id": CANAL, "guild_id": GUILD, "name": "general-ficticio", "type": 0, "permission_overwrites": []}


@app.get("/api/v10/guilds/{guild}")
def servidor(guild: str):
    return {"id": GUILD, "name": "Servidor ficticio", "owner_id": "1"}


@app.get("/api/v10/guilds/{guild}/roles")
def roles(guild: str):
    return [{"id": GUILD, "permissions": str(LECTURA)}]


@app.get("/api/v10/guilds/{guild}/members/{miembro}")
def miembro(guild: str, miembro: str):
    return {"roles": []}


@app.get("/api/v10/channels/{canal}/messages")
def mensajes(canal: str, before: str, limit: int = 50):
    lista = sorted((m for m in MENSAJES if int(m["id"]) < int(before)), key=lambda m: int(m["id"]), reverse=True)
    return lista[:limit]
