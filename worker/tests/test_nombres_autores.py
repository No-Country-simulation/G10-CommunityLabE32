"""Nombre visible del autor: nunca un ID de Discord como si fuera una persona.

PostgreSQL local aislado (127.0.0.1:15439/worker_local). Gemini y Discord con transportes falsos.
"""
import json
import os
import sys
from urllib.parse import urlparse

import httpx
import pytest

from worker.core import Worker

OPERADOR = "operador-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}
ID_ANA, ID_SIN_NOMBRE = "700000000000000001", "700000000000000002"


@pytest.fixture
def cola():
    from worker.store_postgres import ColaPostgres
    url = os.environ.get("WORKER_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL local de pruebas")
    parsed = urlparse(url)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/worker_local"
    q = ColaPostgres(url, lease=2, max_intentos=2)
    q.inicializar()
    with q.conectar() as c:
        c.execute("TRUNCATE trabajos_worker, activos, activos_historial, mensajes, banners")
    return q


@pytest.fixture
def cliente(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("OPERADOR_TOKEN", OPERADOR)
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    with TestClient(app) as c:
        yield c


def evento(message_id, autor, texto, nombre=None):
    e = {"schema_version": "discord-source-v1", "message_id": message_id, "guild_id": "100", "channel_id": "200",
         "author_id": autor, "created_at": "2026-10-20T10:00:00+00:00", "content": texto}
    if nombre is not None:
        e["author_name"] = nombre
    return e


def test_normalizador_lleva_el_nombre_aparte_del_id():
    from pipelines.communitylab.normalizador_discord import normalizar_evento
    con = normalizar_evento(evento("1", ID_ANA, "hola", "  Ana   López "))
    assert (con["autor"], con["autor_nombre"]) == (ID_ANA, "Ana López")
    assert "autor_nombre" not in normalizar_evento(evento("2", ID_ANA, "hola"))
    assert len(normalizar_evento(evento("3", ID_ANA, "hola", "x" * 300))["autor_nombre"]) == 150


def procesar_logros(cola, entrada):
    """Worker con Gemini falso: todo es logro relevante, así que se genera un post por mensaje."""
    from pipelines.communitylab import ejecutar_lote
    from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
    from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, ok, tarea_de

    def responder(p):
        tarea = tarea_de(p)
        if tarea == "generar":
            return ok({"copy": "Felicitamos a la persona por su logro.\n#Comunidad"})
        items = json.loads(p["cuerpo"]["contents"][0]["parts"][0]["text"])
        if tarea == "analizar":
            return ok({"resultados": [{"id": m["id"], "es_logro": True, "es_duda": False, "es_bloqueo": False,
                                       "tema": "certificación", "sentimiento": "positivo"} for m in items]})
        return ok({"resultados": [{"id": m["id"], "relevancia": 0.9} for m in items]})

    cola.encolar(entrada)
    falso = GeminiFalso(responder=responder)
    worker = Worker(cola, lambda e, renovar: ejecutar_lote(e, crear_componentes_gemini(configuracion(), transporte=falso.transporte)))
    while worker.ejecutar_uno():
        pass
    return [p for p in falso.peticiones if tarea_de(p) == "generar"]


def lote(interacciones, cierre=False):
    return {"origen_comunidad": "discord", "periodo_referencia": "2026-W43", "cierre_periodo": cierre,
            "interacciones": interacciones}


def test_el_prompt_redacta_con_el_nombre_y_nunca_con_el_id(cola):
    from pipelines.communitylab.normalizador_discord import normalizar_evento
    interacciones = [normalizar_evento(evento("11", ID_ANA, "Completé la certificación OCI", "Ana López")),
                     normalizar_evento(evento("12", ID_SIN_NOMBRE, "Terminé mi primer despliegue"))]
    generaciones = procesar_logros(cola, lote(interacciones))
    prompts = " ".join(p["cuerpo"]["contents"][0]["parts"][0]["text"] for p in generaciones)
    assert generaciones and "Ana López" in prompts and "Miembro de la comunidad" in prompts
    assert ID_ANA not in prompts and ID_SIN_NOMBRE not in prompts
    with cola.conectar() as c:
        filas = {f["id_mensaje"]: (f["autor"], f["autor_nombre"]) for f in c.execute("SELECT id_mensaje, autor, autor_nombre FROM mensajes")}
    assert filas == {"discord-11": (ID_ANA, "Ana López"), "discord-12": (ID_SIN_NOMBRE, None)}


def test_reenvio_sin_nombre_o_con_nombre_nuevo_no_es_conflicto(cola):
    from pipelines.communitylab.normalizador_discord import normalizar_evento
    cola.encolar(lote([normalizar_evento(evento("21", ID_ANA, "Hola", "Ana"))]))
    cola.encolar(lote([normalizar_evento(evento("21", ID_ANA, "Hola"))], cierre=True))           # sin nombre: se conserva
    with cola.conectar() as c:
        assert c.execute("SELECT autor_nombre FROM mensajes").fetchone()["autor_nombre"] == "Ana"
    cola.encolar(lote([normalizar_evento(evento("21", ID_ANA, "Hola", "Ana López"))], cierre=True))  # cambió el apodo
    with cola.conectar() as c:
        assert c.execute("SELECT autor, autor_nombre FROM mensajes").fetchone() == {"autor": ID_ANA, "autor_nombre": "Ana López"}


def test_api_entrega_el_nombre_visible_y_conserva_el_id(cliente, cola):
    with cola.conectar() as c:
        for ident, autor, nombre in [("discord-31", ID_ANA, "Ana López"), ("discord-32", ID_SIN_NOMBRE, None),
                                     ("manual-1", "Carlos Ruiz", None)]:
            c.execute("""INSERT INTO mensajes (id_mensaje, autor, autor_nombre, fecha, canal, tipo, texto)
                VALUES (%s, %s, %s, '2026-10-20T10:00:00Z', 'general', 'sin_clasificar', 'Mensaje ficticio')""",
                      (ident, autor, nombre))
        c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version, fecha_creacion,
            fecha_actualizacion) VALUES ('act-n', 'linkedin', 'Logro', 'Texto ficticio', 'generado', %s, 1, now(), now())""",
                  (json.dumps(["discord-31", "discord-32"]),))
    items = {m["id_mensaje"]: (m["autor"], m["autor_id"]) for m in cliente.get("/api/mensajes?limit=10", headers=H_OP).json()["items"]}
    assert items == {"discord-31": ("Ana López", ID_ANA), "discord-32": ("Miembro de la comunidad", ID_SIN_NOMBRE),
                     "manual-1": ("Carlos Ruiz", "Carlos Ruiz")}
    assert cliente.get("/api/mensajes", params={"q": "lopez"}, headers=H_OP).json()["total"] == 1   # busca por nombre
    fuentes = {f["id_mensaje"]: f["autor"] for f in cliente.get("/api/curaduria/activos/act-n", headers=H_OP).json()["fuentes_detalle"]}
    assert fuentes == {"discord-31": "Ana López", "discord-32": "Miembro de la comunidad"}


def test_importador_historico_guarda_el_nombre():
    from backend.app.discord_historico.analisis import interaccion
    from backend.app.discord_historico.importador import _normalizar
    from datetime import datetime, timezone
    base = {"id": "1234567890123456789", "content": "hola", "type": 0}
    assert _normalizar({**base, "author": {"id": ID_ANA, "global_name": "Ana López", "username": "ana"}})["autor_nombre"] == "Ana López"
    assert _normalizar({**base, "author": {"id": ID_ANA, "username": "ana_l"}})["autor_nombre"] == "ana_l"
    assert _normalizar({**base, "author": {"id": ID_ANA}})["autor_nombre"] is None
    fila = {"id_mensaje": "discord-1", "autor_id": ID_ANA, "autor_nombre": "Ana López", "canal_id": "200",
            "fecha": datetime(2026, 10, 20, tzinfo=timezone.utc), "texto": "hola"}
    assert interaccion(fila)["autor_nombre"] == "Ana López" and interaccion({**fila, "autor_nombre": None}).get("autor_nombre") is None


def test_script_resuelve_nombres_solo_al_aplicar(cola, monkeypatch, capsys):
    with cola.conectar() as c:
        for ident, autor in [("discord-41", ID_ANA), ("discord-42", ID_ANA), ("discord-43", ID_SIN_NOMBRE), ("manual-2", "Carlos")]:
            c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                VALUES (%s, %s, '2026-10-20T10:00:00Z', 'general', 'sin_clasificar', 'Mensaje ficticio')""", (ident, autor))
    llamadas = []

    def discord(request):
        llamadas.append(request.url.path)
        assert request.method == "GET" and request.headers["authorization"] == "Bot token-falso"
        if request.url.path.endswith(f"/members/{ID_ANA}"):
            return httpx.Response(200, json={"nick": "Ana (mentora)", "user": {"id": ID_ANA, "username": "ana"}})
        if request.url.path.endswith(f"/members/{ID_SIN_NOMBRE}"):
            return httpx.Response(404, json={"message": "Unknown Member"})
        if request.url.path.endswith(f"/users/{ID_SIN_NOMBRE}"):
            return httpx.Response(200, json={"id": ID_SIN_NOMBRE, "username": "exmiembro"})
        return httpx.Response(404, json={})

    from backend.scripts import resolver_nombres_discord as r
    monkeypatch.setenv("DATABASE_URL", cola.url)
    monkeypatch.setenv("DISCORD_HISTORICO_TOKEN", "token-falso")
    monkeypatch.setenv("DISCORD_HISTORICO_AUTORIZADOS", json.dumps({"111111111111111111": ["222222222222222222"]}))
    monkeypatch.setattr(sys, "argv", ["resolver_nombres_discord"])
    r.main(transporte=httpx.MockTransport(discord))
    assert "mensajes_sin_nombre=3 autores_distintos=2 aplicado=False" in capsys.readouterr().out and llamadas == []
    monkeypatch.setattr(sys, "argv", ["resolver_nombres_discord", "--aplicar"])
    r.main(transporte=httpx.MockTransport(discord))
    assert "autores_resueltos=2 mensajes_actualizados=3" in capsys.readouterr().out
    with cola.conectar() as c:
        nombres = {f["id_mensaje"]: f["autor_nombre"] for f in c.execute("SELECT id_mensaje, autor_nombre FROM mensajes")}
    assert nombres == {"discord-41": "Ana (mentora)", "discord-42": "Ana (mentora)", "discord-43": "exmiembro", "manual-2": None}
