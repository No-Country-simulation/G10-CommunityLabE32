"""Importación histórica de Discord: unidades + API/runner sobre PostgreSQL aislado.

Discord es un transporte simulado (httpx.MockTransport) que solo acepta GET y registra cada
petición. No hay red, ni Gemini, ni bot. La base exige 127.0.0.1:15441/discord_historico_test.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from backend.app.discord_historico import fechas, permisos
from backend.app.discord_historico.cliente import (ClienteDiscord, LimiteDiscord, SinPermiso, Transitorio)
from backend.app.discord_historico.configuracion import Configuracion, ConfiguracionInvalida
from backend.app.discord_historico.fechas import RangoInvalido, normalizar_rango, snowflake_de

UTC = timezone.utc
AHORA = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
GUILD, CANAL, OTRO, HILO, FORO, BOT, ROL = ("111111111111111111", "222222222222222222", "333333333333333333",
                                             "555555555555555555", "666666666666666666", "999999999999999999",
                                             "444444444444444444")
LECTURA = permisos.VIEW_CHANNEL | permisos.READ_MESSAGE_HISTORY
TOKEN_FALSO = "token-discord-falso-de-prueba"


# ---------------------------------------------------------------- Discord simulado
class DiscordFalso:
    def __init__(self):
        self.canales = {c: {"id": c, "guild_id": GUILD, "name": f"canal-{c[:3]}", "type": t, "permission_overwrites": []}
                        for c, t in ((CANAL, 0), (OTRO, 0), (HILO, 11), (FORO, 15))}
        self.roles = [{"id": GUILD, "permissions": str(LECTURA)}, {"id": ROL, "permissions": "0"}]
        self.bot_en_servidor = True
        self.mensajes = {CANAL: []}
        self.peticiones, self.esperas, self.fallos = [], [], []
        self.al_pedir_mensajes = None   # gancho: (numero_de_pagina) -> None
        self._secuencia = 0
        self.transporte = httpx.MockTransport(self)

    def dormir(self, segundos):
        self.esperas.append(segundos)

    def msg(self, cuando, texto="hola", autor="700000000000000001", bot=False, tipo=0, webhook=False,
            editado=None, hilo=False, canal=CANAL):
        self._secuencia += 1
        ms = int(cuando.timestamp() * 1000) - fechas.EPOCH_DISCORD_MS
        m = {"id": str((ms << 22) | self._secuencia), "channel_id": canal, "type": tipo, "content": texto,
             "timestamp": cuando.isoformat(), "edited_timestamp": editado.isoformat() if editado else None,
             "author": {"id": autor, "bot": bot}, "attachments": [], "embeds": []}
        if webhook:
            m["webhook_id"] = "800000000000000001"
        if hilo:
            m["thread"] = {"id": "880000000000000001"}
        self.mensajes.setdefault(canal, []).append(m)
        return m

    def __call__(self, request):
        ruta = request.url.path.removeprefix("/api/v10")
        self.peticiones.append((request.method, ruta, dict(request.url.params)))
        assert request.headers["authorization"] == f"Bot {TOKEN_FALSO}"
        assert request.headers["user-agent"].startswith("DiscordBot (")
        if request.method != "GET":
            return httpx.Response(405, json={"message": "solo GET"})
        if self.fallos and self.fallos[0][0] in ruta:
            _, estado, cuerpo, cabeceras = self.fallos.pop(0)
            if estado == "timeout":
                raise httpx.ReadTimeout("timeout simulado", request=request)
            return httpx.Response(estado, json=cuerpo, headers=cabeceras or {})
        partes = ruta.strip("/").split("/")
        if ruta == "/users/@me":
            return httpx.Response(200, json={"id": BOT, "bot": True})
        if partes[0] == "channels" and len(partes) == 2:
            c = self.canales.get(partes[1])
            return httpx.Response(200, json=c) if c else httpx.Response(404, json={"code": 10003})
        if partes[0] == "guilds" and len(partes) == 2:
            return httpx.Response(200, json={"id": GUILD, "name": "Servidor de prueba", "owner_id": "1"})
        if partes[0] == "guilds" and partes[2] == "roles":
            return httpx.Response(200, json=self.roles)
        if partes[0] == "guilds" and partes[2] == "members":
            if not self.bot_en_servidor:
                return httpx.Response(404, json={"code": 10007})
            return httpx.Response(200, json={"roles": [ROL]})
        if partes[0] == "channels" and partes[2] == "messages":
            pagina_n = sum(1 for p in self.peticiones if p[1].endswith("/messages"))
            if self.al_pedir_mensajes:
                self.al_pedir_mensajes(pagina_n)
            antes = int(request.url.params["before"])
            limite = int(request.url.params["limit"])
            lista = sorted((m for m in self.mensajes.get(partes[1], []) if int(m["id"]) < antes),
                           key=lambda m: int(m["id"]), reverse=True)[:limite]
            return httpx.Response(200, json=lista, headers={"x-ratelimit-remaining": "5"})
        return httpx.Response(404, json={"code": 0})

    def cliente(self, **kw):
        return ClienteDiscord(TOKEN_FALSO, "https://discord.com/api/v10", transporte=self.transporte,
                              dormir=self.dormir, **kw)

    def pedidos_mensajes(self):
        return [p for p in self.peticiones if p[1].endswith("/messages")]


def config(**cambios):
    datos = {"token": TOKEN_FALSO, "autorizados": {GUILD: frozenset({CANAL, HILO, FORO})},
             "max_mensajes": 5000, "max_dias": 400, "confirmar_dias": 31, "confirmar_mensajes": 1000}
    datos.update(cambios)
    return Configuracion(**datos)


# ---------------------------------------------------------------- Fechas y zona horaria
def test_dias_completos_en_guatemala_y_recorte_al_presente():
    r = normalizar_rango("2026-01-01", "2026-10-18", "America/Guatemala", AHORA, 400)
    assert r.inicio_utc == datetime(2026, 1, 1, 6, tzinfo=UTC)
    assert r.fin_utc == AHORA  # el fin (19-10 06:00Z) superaría el presente: se congela en «ahora»
    assert "hasta_recortado_al_momento_de_la_solicitud" in r.advertencias
    r2 = normalizar_rango("2026-10-01", "2026-10-01", "America/Guatemala", AHORA, 400)
    assert (r2.inicio_utc, r2.fin_utc) == (datetime(2026, 10, 1, 6, tzinfo=UTC), datetime(2026, 10, 2, 6, tzinfo=UTC))


def test_cambios_de_horario_no_suman_24_horas():
    futuro = datetime(2030, 1, 1, tzinfo=UTC)
    primavera = normalizar_rango("2026-03-08", "2026-03-08", "America/New_York", futuro, 400)
    assert primavera.fin_utc - primavera.inicio_utc == timedelta(hours=23)
    otono = normalizar_rango("2026-11-01", "2026-11-01", "America/New_York", futuro, 400)
    assert otono.fin_utc - otono.inicio_utc == timedelta(hours=25)
    with pytest.raises(RangoInvalido) as e:
        normalizar_rango("2026-03-08T02:30", "2026-03-09", "America/New_York", futuro, 400)
    assert e.value.codigo == "hora_inexistente"
    ambigua = normalizar_rango("2026-11-01T01:30", "2026-11-02", "America/New_York", futuro, 400)
    assert any("ambigua" in a for a in ambigua.advertencias)


@pytest.mark.parametrize("desde, hasta, zona, codigo", [
    ("2026-10-01", "2026-10-02", "Marte/Olympus", "zona_invalida"),
    ("01/10/2026", "2026-10-02", "America/Guatemala", "fecha_invalida"),
    ("2026-02-30", "2026-03-02", "America/Guatemala", "fecha_invalida"),
    ("2026-10-05", "2026-10-01", "America/Guatemala", "rango_invertido"),
    ("2026-10-20", "2026-10-25", "America/Guatemala", "fecha_futura"),
    ("2020-01-01", "2026-10-01", "America/Guatemala", "rango_excesivo"),
])
def test_validaciones_de_rango(desde, hasta, zona, codigo):
    with pytest.raises(RangoInvalido) as e:
        normalizar_rango(desde, hasta, zona, AHORA, 400)
    assert e.value.codigo == codigo


def test_desplazamiento_explicito_y_fin_exclusivo_por_snowflake():
    r = normalizar_rango("2026-10-01T00:00:00Z", "2026-10-02T00:00:00-06:00", "America/Guatemala", AHORA, 400)
    assert (r.inicio_utc, r.fin_utc) == (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 2, 6, tzinfo=UTC))
    limite = int(snowflake_de(r.fin_utc))
    exacto = (int(r.fin_utc.timestamp() * 1000) - fechas.EPOCH_DISCORD_MS) << 22
    assert exacto >= limite and (exacto | 5) >= limite      # un mensaje en el instante «fin» queda fuera (before)
    assert fechas.fecha_de_snowflake(str(exacto)) == r.fin_utc


# ---------------------------------------------------------------- Permisos
def test_permisos_efectivos_segun_algoritmo_oficial():
    guild = {"id": GUILD, "owner_id": "1"}
    roles = [{"id": GUILD, "permissions": str(LECTURA)}, {"id": ROL, "permissions": "0"},
             {"id": "123456789012345678", "permissions": str(permisos.ADMINISTRATOR)}]
    base = permisos.permisos_base(guild, roles, BOT, [ROL])
    assert base & LECTURA == LECTURA
    niega = [{"id": GUILD, "type": 0, "allow": "0", "deny": str(permisos.READ_MESSAGE_HISTORY)}]
    assert not permisos.permisos_en_canal(base, GUILD, BOT, [ROL], niega) & permisos.READ_MESSAGE_HISTORY
    rol_permite = niega + [{"id": ROL, "type": 0, "allow": str(permisos.READ_MESSAGE_HISTORY), "deny": "0"}]
    assert permisos.permisos_en_canal(base, GUILD, BOT, [ROL], rol_permite) & permisos.READ_MESSAGE_HISTORY
    miembro_niega = rol_permite + [{"id": BOT, "type": 1, "allow": "0", "deny": str(permisos.VIEW_CHANNEL)}]
    assert not permisos.permisos_en_canal(base, GUILD, BOT, [ROL], miembro_niega) & permisos.VIEW_CHANNEL
    admin = permisos.permisos_base(guild, roles, BOT, ["123456789012345678"])
    assert permisos.permisos_en_canal(admin, GUILD, BOT, [], miembro_niega) & LECTURA == LECTURA
    assert permisos.permisos_base({"id": GUILD, "owner_id": BOT}, roles, BOT, []) == permisos.TODOS


def test_configuracion_lista_explicita_y_base_oficial():
    with pytest.raises(ConfiguracionInvalida):
        Configuracion.desde_entorno({"DISCORD_HISTORICO_AUTORIZADOS": '{"abc": ["1"]}'})
    with pytest.raises(ConfiguracionInvalida):
        Configuracion.desde_entorno({"DISCORD_API_BASE": "https://evil.example/api"})
    c = Configuracion.desde_entorno({"DISCORD_HISTORICO_AUTORIZADOS": json.dumps({GUILD: [CANAL]})})
    assert (c.servidor_de(CANAL), c.servidor_de(OTRO), c.api_base) == (GUILD, None, "https://discord.com/api/v10")
    assert not c.configurada and TOKEN_FALSO not in repr(config())


# ---------------------------------------------------------------- Cliente HTTP
def test_cliente_respeta_429_reintenta_transitorios_y_tipa_errores():
    d = DiscordFalso()
    d.fallos = [("/users/@me", 429, {"retry_after": 1.5, "global": False}, None),
                ("/users/@me", 503, {}, None), ("/users/@me", "timeout", None, None)]
    assert d.cliente().usuario_actual()["id"] == BOT
    assert 1.5 in d.esperas and len(d.peticiones) == 4
    d.fallos = [("/users/@me", 429, {"retry_after": 600}, None)]
    with pytest.raises(LimiteDiscord) as e:
        d.cliente().usuario_actual()
    assert e.value.reanudable and TOKEN_FALSO not in str(e.value.como_dict())
    d.fallos = [("/users/@me", 503, {}, None)] * 5
    with pytest.raises(Transitorio):
        d.cliente(max_reintentos=2).usuario_actual()
    d.fallos = [("/channels/", 403, {"code": 50001}, None)]
    with pytest.raises(SinPermiso):
        d.cliente().canal(CANAL)
    with pytest.raises(ValueError):
        d.cliente().canal("../../users/@me")      # el ID nunca se convierte en una ruta arbitraria
    assert all(p[0] == "GET" for p in d.peticiones)


# ---------------------------------------------------------------- API + runner (PostgreSQL)
@pytest.fixture
def entorno(monkeypatch):
    url = os.environ.get("DISCORD_HISTORICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL aislado de esta tarea")
    p = urlparse(url)
    assert (p.hostname, p.port, p.path) == ("127.0.0.1", 15441, "/discord_historico_test")
    asyncpg_url = url.replace("postgresql://", "postgresql+asyncpg://")
    monkeypatch.setenv("DATABASE_URL", asyncpg_url)
    monkeypatch.setenv("OPERADOR_TOKEN", "operador-de-prueba")
    monkeypatch.setenv("DISCORD_HISTORICO_TOKEN", TOKEN_FALSO)
    monkeypatch.setenv("DISCORD_HISTORICO_AUTORIZADOS", json.dumps({GUILD: [CANAL, HILO, FORO]}))
    from sqlalchemy import create_engine
    from backend.app.core.database import Base
    from backend.app.models.activo import Activo  # noqa: F401  (registra la tabla)
    from backend.app.models.mensaje import Mensaje  # noqa: F401
    from worker.store_postgres import ColaPostgres
    motor = create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
    Base.metadata.create_all(motor)
    motor.dispose()
    cola = ColaPostgres(url)
    cola.inicializar()
    with cola.conectar() as c:
        c.execute("TRUNCATE discord_importacion_mensajes, discord_mensajes_historicos, discord_importaciones, "
                  "mensajes, activos, trabajos_worker")
    d = DiscordFalso()
    from backend.app.api.routes import discord_historico as rutas
    monkeypatch.setattr(rutas, "_cliente", lambda cfg: d.cliente())
    # Si algo intentara usar Gemini, la prueba falla.
    from pipelines.communitylab import gemini as modulo_gemini
    monkeypatch.setattr(modulo_gemini.ClienteGemini, "__init__",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Gemini no debe usarse")))
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    from backend.app.discord_historico.store import Store
    with TestClient(app) as cliente:
        yield {"api": cliente, "d": d, "url": url, "cola": cola, "store": Store(url, lease=30)}


H = {"X-Operador-Token": "operador-de-prueba"}
BASE = "/api/v1/discord/historico"


def correr_runner(e, config_=None, fabrica=None):
    from backend.app.discord_historico.runner import un_ciclo
    return un_ciclo(e["store"], config_ or Configuracion.desde_entorno(), fabrica or (lambda cfg: e["d"].cliente()))


def sembrar(d, inicio, n, paso=timedelta(minutes=30), **kw):
    return [d.msg(inicio + i * paso, f"mensaje {i}", **kw) for i in range(n)]


def crear(e, **cambios):
    cuerpo = {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-20", "zona": "America/Guatemala", "max_mensajes": 1000}
    cuerpo.update(cambios)
    return e["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=H)


def fila(e, sql, *p):
    with e["cola"].conectar() as c:
        return c.execute(sql, p).fetchone()


def test_todas_las_rutas_exigen_operador(entorno, monkeypatch):
    api = entorno["api"]
    rutas = [("post", f"{BASE}/verificar", {"canal_id": CANAL}),
             ("post", f"{BASE}/previsualizar", {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-02", "zona": "UTC"}),
             ("post", f"{BASE}/importaciones", {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-02", "zona": "UTC"}),
             ("get", f"{BASE}/importaciones", None), ("get", f"{BASE}/importaciones/imp-x", None),
             ("post", f"{BASE}/importaciones/imp-x/cancelar", None), ("post", f"{BASE}/importaciones/imp-x/reanudar", None),
             ("get", f"{BASE}/importaciones/imp-x/mensajes", None)]
    for metodo, ruta, cuerpo in rutas:
        assert api.request(metodo.upper(), ruta, json=cuerpo).status_code == 401, ruta
        assert api.request(metodo.upper(), ruta, json=cuerpo, headers={"X-Operador-Token": "mal"}).status_code == 401, ruta
    monkeypatch.delenv("OPERADOR_TOKEN")
    assert api.post(f"{BASE}/verificar", json={"canal_id": CANAL}, headers=H).status_code == 503
    assert entorno["d"].peticiones == []      # ningún rechazo llegó a consultar Discord


def test_canal_no_autorizado_aunque_el_bot_lo_vea_no_consulta_discord(entorno):
    r = entorno["api"].post(f"{BASE}/verificar", json={"canal_id": OTRO}, headers=H)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "canal_no_autorizado")
    assert entorno["d"].peticiones == []
    assert entorno["api"].post(f"{BASE}/verificar", json={"canal_id": "abc"}, headers=H).status_code == 422


def test_permisos_insuficientes_bot_fuera_y_tipos_no_soportados(entorno):
    d, api = entorno["d"], entorno["api"]
    ok = api.post(f"{BASE}/verificar", json={"canal_id": CANAL}, headers=H).json()
    assert ok["permisos"] == {"ver_canal": True, "leer_historial": True} and ok["tipo_soportado"]
    assert TOKEN_FALSO not in json.dumps(ok)
    d.canales[CANAL]["permission_overwrites"] = [{"id": GUILD, "type": 0, "allow": "0",
                                                   "deny": str(permisos.READ_MESSAGE_HISTORY)}]
    r = api.post(f"{BASE}/verificar", json={"canal_id": CANAL}, headers=H)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "permisos_insuficientes")
    d.canales[CANAL]["permission_overwrites"] = []
    d.bot_en_servidor = False
    assert api.post(f"{BASE}/verificar", json={"canal_id": CANAL}, headers=H).json()["detail"]["codigo"] == "bot_fuera_del_servidor"
    d.bot_en_servidor = True
    for canal in (HILO, FORO):
        r = api.post(f"{BASE}/verificar", json={"canal_id": canal}, headers=H)
        assert (r.status_code, r.json()["detail"]["codigo"]) == (422, "tipo_no_soportado")


def test_previsualizar_conteo_exacto_desconocido_muestra_y_sin_guardar(entorno):
    d, api = entorno["d"], entorno["api"]
    sembrar(d, datetime(2026, 9, 5, tzinfo=UTC), 30)
    d.msg(datetime(2026, 9, 6, tzinfo=UTC), "", hilo=True)
    cuerpo = {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-20", "zona": "America/Guatemala",
              "incluir_muestra": True}
    r = api.post(f"{BASE}/previsualizar", json=cuerpo, headers=H).json()
    assert r["conteo"] == {"tipo": "exacto", "mensajes_en_rango": 31, "importables": 31}
    assert len(r["muestra"]) == 5 and all(len(m["texto"]) <= 200 for m in r["muestra"])
    assert any(a.startswith("hilos_detectados") for a in r["advertencias"])
    assert any(a.startswith("contenido_vacio") for a in r["advertencias"])
    assert r["rango"]["inicio_utc"] == "2026-09-01T06:00:00Z" and r["rango"]["fin_utc_exclusivo"] == "2026-09-21T06:00:00Z"
    assert len(d.pedidos_mensajes()) == 1
    assert fila(entorno, "SELECT count(*) n FROM discord_mensajes_historicos")["n"] == 0
    sembrar(d, datetime(2026, 9, 10, tzinfo=UTC), 150, paso=timedelta(minutes=1))
    r2 = api.post(f"{BASE}/previsualizar", json={**cuerpo, "incluir_muestra": False}, headers=H).json()
    assert r2["conteo"]["tipo"] == "desconocido" and r2["conteo"]["minimo"] == 100 and "muestra" not in r2


def test_importacion_varias_paginas_bordes_filtros_y_sin_historial_anterior(entorno):
    d, api = entorno["d"], entorno["api"]
    inicio = datetime(2026, 9, 1, 6, tzinfo=UTC)          # 2026-09-01 00:00 Guatemala
    fin = datetime(2026, 9, 21, 6, tzinfo=UTC)
    antiguos = sembrar(d, datetime(2026, 8, 1, tzinfo=UTC), 50)
    borde_inicio = d.msg(inicio, "justo al inicio")
    dentro = sembrar(d, inicio + timedelta(hours=1), 247, paso=timedelta(minutes=60))
    d.msg(inicio + timedelta(hours=2), "bot", bot=True)
    d.msg(inicio + timedelta(hours=3), "webhook", webhook=True)
    d.msg(inicio + timedelta(hours=4), "", tipo=7)        # USER_JOIN (sistema)
    borde_fin = d.msg(fin, "justo en el fin (excluido)")
    sembrar(d, fin + timedelta(hours=1), 20)
    r = crear(entorno)
    assert r.status_code == 202, r.text
    imp = r.json()["importacion"]
    assert correr_runner(entorno) == "completada"
    final = api.get(f"{BASE}/importaciones/{imp['id']}", headers=H).json()
    assert final["estado"] == "completada" and final["insertados"] == 248
    assert final["descartados"] == {"bot": 1, "webhook": 1, "sistema": 1}
    assert final["paginas"] >= 3 and not final["limite_alcanzado"] and final["alcance"] == "canal_sin_hilos"
    ids = {f["message_id"] for f in api.get(f"{BASE}/importaciones/{imp['id']}/mensajes?limite=200", headers=H).json()["items"]}
    todos = {r["message_id"] for r in _todas(entorno)}
    assert borde_inicio["id"] in todos and borde_fin["id"] not in todos
    assert not todos & {m["id"] for m in antiguos}
    assert len(ids) == 200 and len(todos) == 248
    # No recorrió el historial anterior al rango más allá de la página que cruzó el inicio.
    assert len(d.pedidos_mensajes()) <= 4
    # Ni POST a Discord, ni mensajes en la tabla pública `mensajes`.
    assert all(p[0] == "GET" for p in d.peticiones)
    assert fila(entorno, "SELECT count(*) n FROM mensajes")["n"] == 0
    assert api.get("/api/mensajes", headers=H).json()["total"] == 0


def _todas(e):
    with e["cola"].conectar() as c:
        return c.execute("SELECT message_id FROM discord_mensajes_historicos").fetchall()


def test_rango_vacio(entorno):
    sembrar(entorno["d"], datetime(2026, 8, 1, tzinfo=UTC), 5)
    imp = crear(entorno).json()["importacion"]
    assert correr_runner(entorno) == "completada"
    assert entorno["store"].obtener(imp["id"])["insertados"] == 0


def test_superposicion_mensajes_en_vivo_y_ediciones(entorno):
    d = entorno["d"]
    msgs = sembrar(d, datetime(2026, 9, 5, tzinfo=UTC), 10)
    with entorno["cola"].conectar() as c:  # llegó antes por el lector en vivo (misma identidad canónica)
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
            VALUES (%s,'a','2026-09-05T00:00:00Z','discord_x','sin_clasificar','hola')""", (f"discord-{msgs[0]['id']}",))
    a = crear(entorno, hasta="2026-09-10").json()["importacion"]
    correr_runner(entorno)
    pa = entorno["store"].obtener(a["id"])
    assert (pa["insertados"], pa["existentes_en_vivo"]) == (9, 1)
    # Contrato corregido (revisión Codex, hallazgo 2): existir en `mensajes` solo prueba que se GUARDÓ.
    # Sin un trabajo terminado que contenga ese id no hay evidencia de IA: en_ingesta_vivo=true, pero
    # procesado_ia=false y estado «sin_evidencia». La versión anterior afirmaba procesado_ia=true.
    vivo = fila(entorno, """SELECT en_ingesta_vivo, estado_ia_captura, procesado_ia FROM discord_mensajes_historicos
        WHERE message_id=%s""", msgs[0]["id"])
    assert (vivo["en_ingesta_vivo"], vivo["estado_ia_captura"], vivo["procesado_ia"]) == (True, "sin_evidencia", False)
    assert fila(entorno, "SELECT texto FROM mensajes WHERE id_mensaje=%s", f"discord-{msgs[0]['id']}")["texto"] == "hola"
    msgs[1]["content"] = "texto editado"
    msgs[1]["edited_timestamp"] = datetime(2026, 9, 15, tzinfo=UTC).isoformat()
    b = crear(entorno, desde="2026-09-04", hasta="2026-09-12").json()["importacion"]   # rango superpuesto
    correr_runner(entorno)
    pb = entorno["store"].obtener(b["id"])
    assert (pb["insertados"], pb["existentes"], pb["existentes_en_vivo"], pb["editados"]) == (0, 8, 1, 1)
    editado = fila(entorno, "SELECT texto, texto_ultima_version FROM discord_mensajes_historicos WHERE message_id=%s", msgs[1]["id"])
    assert (editado["texto"], editado["texto_ultima_version"]) == ("mensaje 1", "texto editado")
    assert fila(entorno, "SELECT count(*) n FROM discord_mensajes_historicos")["n"] == 10  # sin duplicados


def test_doble_solicitud_idempotencia_y_confirmacion(entorno):
    api = entorno["api"]
    cuerpo = {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-20", "zona": "America/Guatemala", "max_mensajes": 1000}
    a = api.post(f"{BASE}/importaciones", json=cuerpo, headers={**H, "Idempotency-Key": "k1"})
    b = api.post(f"{BASE}/importaciones", json=cuerpo, headers={**H, "Idempotency-Key": "k1"})
    assert a.json()["importacion"]["id"] == b.json()["importacion"]["id"] and b.json()["reutilizada"]
    c = api.post(f"{BASE}/importaciones", json=cuerpo, headers=H)
    assert (c.status_code, c.json()["detail"]["codigo"]) == (409, "importacion_activa_en_el_canal")
    d = api.post(f"{BASE}/importaciones", json={**cuerpo, "desde": "2026-09-02"}, headers={**H, "Idempotency-Key": "k1"})
    assert d.json()["detail"]["codigo"] == "clave_idempotencia_reutilizada"
    api.post(f"{BASE}/importaciones/{a.json()['importacion']['id']}/cancelar", headers=H)
    grande = api.post(f"{BASE}/importaciones", json={**cuerpo, "desde": "2026-01-01", "hasta": "2026-10-17"}, headers=H)
    assert (grande.status_code, grande.json()["detail"]["codigo"]) == (409, "confirmacion_requerida")
    ok = api.post(f"{BASE}/importaciones", json={**cuerpo, "desde": "2026-01-01", "hasta": "2026-10-17",
                                                  "confirmar_alcance": True}, headers=H)
    assert ok.status_code == 202


def test_cancelacion_pendiente_y_entre_paginas(entorno):
    d, api, store = entorno["d"], entorno["api"], entorno["store"]
    imp = crear(entorno).json()["importacion"]
    assert api.post(f"{BASE}/importaciones/{imp['id']}/cancelar", headers=H).json()["estado"] == "cancelada"
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 300, paso=timedelta(minutes=30))
    imp2 = crear(entorno).json()["importacion"]
    d.al_pedir_mensajes = lambda n: store.solicitar_cancelacion(imp2["id"]) if n == 2 else None
    assert correr_runner(entorno) == "cancelada"
    final = store.obtener(imp2["id"])
    assert final["estado"] == "cancelada" and 0 < final["insertados"] < 300


class Caida(Exception):
    pass


def test_caida_y_reanudacion_sin_perdida_ni_duplicados(entorno):
    d, store = entorno["d"], entorno["store"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 260, paso=timedelta(minutes=60))
    imp = crear(entorno).json()["importacion"]

    def caer(n):
        if n == 3:
            raise Caida()
    d.al_pedir_mensajes = caer
    with pytest.raises(Caida):
        correr_runner(entorno)
    a_medias = store.obtener(imp["id"])
    assert a_medias["estado"] == "ejecutando" and a_medias["insertados"] == 200
    with entorno["cola"].conectar() as c:   # la reserva vence (el runner murió)
        c.execute("UPDATE discord_importaciones SET vence=clock_timestamp() - interval '1 second' WHERE id=%s", (imp["id"],))
    d.al_pedir_mensajes = None
    assert correr_runner(entorno) == "completada"
    final = store.obtener(imp["id"])
    assert final["insertados"] == 260 and final["intentos"] == 2
    assert fila(entorno, "SELECT count(*) n FROM discord_importacion_mensajes WHERE importacion_id=%s", imp["id"])["n"] == 260


def test_429_durante_la_importacion_y_limite_largo_reanudable(entorno):
    d, api, store = entorno["d"], entorno["api"], entorno["store"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 150, paso=timedelta(hours=1))
    imp = crear(entorno).json()["importacion"]
    d.fallos = [("/messages", 429, {"retry_after": 2.0}, {"retry-after": "2"})]
    assert correr_runner(entorno) == "completada" and 2.0 in d.esperas
    imp2 = crear(entorno, desde="2026-09-02", hasta="2026-09-05").json()["importacion"]
    d.fallos = [("/messages", 429, {"retry_after": 999}, None)]
    assert correr_runner(entorno) == "error"
    err = store.obtener(imp2["id"])
    assert err["error"]["codigo"] == "limite_discord" and err["error"]["reanudable"]
    assert api.post(f"{BASE}/importaciones/{imp2['id']}/reanudar", headers=H).json()["estado"] == "pendiente"
    assert correr_runner(entorno) == "completada"


def test_timeouts_y_perdida_de_permisos_a_mitad(entorno):
    d, api, store = entorno["d"], entorno["api"], entorno["store"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 250, paso=timedelta(hours=1))
    imp = crear(entorno).json()["importacion"]
    d.fallos = [("/messages", "timeout", None, None)]
    d.al_pedir_mensajes = lambda n: d.fallos.append(("/messages", 403, {"code": 50013}, None)) if n == 2 else None
    assert correr_runner(entorno) == "error"
    err = store.obtener(imp["id"])
    assert err["error"]["codigo"] == "sin_permiso_discord" and not err["error"]["reanudable"]
    r = api.post(f"{BASE}/importaciones/{imp['id']}/reanudar", headers=H)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "no_reanudable")


def test_limite_de_mensajes_es_resultado_parcial(entorno):
    sembrar(entorno["d"], datetime(2026, 9, 2, tzinfo=UTC), 120, paso=timedelta(hours=1))
    imp = crear(entorno, max_mensajes=50).json()["importacion"]
    assert correr_runner(entorno) == "completada_con_limite"
    final = entorno["store"].obtener(imp["id"])
    assert (final["estado"], final["insertados"], final["limite_alcanzado"]) == ("completada_con_limite", 50, True)
    assert final["motivos_parcial"] == ["max_mensajes"]


def test_mensajes_nuevos_durante_la_importacion_no_entran(entorno):
    d = entorno["d"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 150, paso=timedelta(hours=1))
    imp = crear(entorno).json()["importacion"]
    d.al_pedir_mensajes = lambda n: d.msg(datetime(2026, 10, 1, tzinfo=UTC), "llegó durante la importación") if n == 1 else None
    correr_runner(entorno)
    assert entorno["store"].obtener(imp["id"])["insertados"] == 150


def test_cursor_sin_avance_se_detiene(entorno):
    d = entorno["d"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 120, paso=timedelta(hours=1))
    imp = crear(entorno).json()["importacion"]
    original = d.__call__

    def repetir(request):  # Discord que devuelve siempre la misma página
        if request.url.path.endswith("/messages"):
            d.peticiones.append((request.method, request.url.path, dict(request.url.params)))
            lista = sorted(d.mensajes[CANAL], key=lambda m: int(m["id"]), reverse=True)[:100]
            return httpx.Response(200, json=lista)
        return original(request)
    fabrica = lambda cfg: ClienteDiscord(TOKEN_FALSO, "https://discord.com/api/v10",
                                         transporte=httpx.MockTransport(repetir), dormir=d.dormir)
    assert correr_runner(entorno, fabrica=fabrica) == "error"
    assert entorno["store"].obtener(imp["id"])["error"]["codigo"] == "cursor_sin_avance"


def test_migracion_aditiva_sobre_datos_existentes(entorno):
    with entorno["cola"].conectar() as c:
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
            VALUES ('m-existente','a','2026-01-01T00:00:00Z','c','t','dato previo')""")
    entorno["cola"].inicializar()      # reaplicar el esquema completo no borra ni altera datos
    assert fila(entorno, "SELECT texto FROM mensajes WHERE id_mensaje='m-existente'")["texto"] == "dato previo"
    assert fila(entorno, "SELECT count(*) n FROM information_schema.tables WHERE table_name LIKE 'discord_%%'")["n"] == 3


def test_concurrencia_creacion_simultanea_y_dos_runners(entorno):
    from concurrent.futures import ThreadPoolExecutor
    store = entorno["store"]
    rango = normalizar_rango("2026-09-01", "2026-09-05", "UTC", AHORA, 400)

    def crear_directo(i):
        try:
            return store.crear(guild_id=GUILD, canal_id=CANAL, canal_nombre="c", canal_tipo=0, rango=rango,
                               max_mensajes=100, solicitante="prueba", clave_idempotencia=f"c{i}")[0]["id"]
        except Exception as exc:
            return getattr(exc, "codigo", type(exc).__name__)
    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(crear_directo, range(8)))
    creadas = [r for r in resultados if r.startswith("imp-")]
    assert len(creadas) == 1 and resultados.count("importacion_activa_en_el_canal") == 7
    with ThreadPoolExecutor(4) as ex:
        reservas = list(ex.map(lambda _: store.reservar(), range(4)))
    assert sum(1 for r in reservas if r) == 1          # SKIP LOCKED + reserva: un único runner
    assert store.reservar() is None                    # con la reserva vigente nadie más la toma


def test_hilos_excluidos_no_se_declara_completa(entorno):
    d = entorno["d"]
    sembrar(d, datetime(2026, 9, 2, tzinfo=UTC), 10)
    d.msg(datetime(2026, 9, 3, tzinfo=UTC), "abre un hilo", hilo=True)
    imp = crear(entorno).json()["importacion"]
    assert correr_runner(entorno) == "completada_con_limite"
    final = entorno["store"].obtener(imp["id"])
    assert (final["estado"], final["hilos_detectados"], final["insertados"]) == ("completada_con_limite", 1, 11)
    assert final["motivos_parcial"] == ["hilos_excluidos"] and not final["limite_alcanzado"]
    sin_hilos = crear(entorno, desde="2026-09-01", hasta="2026-09-01").json()["importacion"]
    assert correr_runner(entorno) == "completada"
    assert entorno["store"].obtener(sin_hilos["id"])["motivos_parcial"] == []


# ---------------------------------------------------------------- Correcciones de la revisión independiente
def test_inicio_de_dia_con_medianoche_inexistente_sao_paulo():
    futuro = datetime(2030, 1, 1, tzinfo=UTC)
    r = normalizar_rango("2018-11-04", "2018-11-04", "America/Sao_Paulo", futuro, 6000)
    assert r.inicio_utc == datetime(2018, 11, 4, 3, tzinfo=UTC)               # 01:00-02:00, no 23:00 del día 3
    assert r.inicio_local == "2018-11-04T01:00:00-02:00"
    assert r.fin_utc - r.inicio_utc == timedelta(hours=23)
    assert "desde_inicio_del_dia_ajustado_por_cambio_de_horario" in r.advertencias
    # Límite final que cae en esa medianoche inexistente: el día 3 completo termina a las 01:00-02:00 del 4.
    r3 = normalizar_rango("2018-11-03", "2018-11-03", "America/Sao_Paulo", futuro, 6000)
    assert (r3.inicio_local, r3.fin_local) == ("2018-11-03T00:00:00-03:00", "2018-11-04T01:00:00-02:00")
    assert r3.fin_utc - r3.inicio_utc == timedelta(hours=24)
    # Día de 25 h (fin del horario de verano a medianoche).
    r25 = normalizar_rango("2019-02-16", "2019-02-16", "America/Sao_Paulo", futuro, 6000)
    assert r25.fin_utc - r25.inicio_utc == timedelta(hours=25) and r25.fin_local == "2019-02-17T00:00:00-03:00"


def test_fecha_local_inexistente_y_anterior_a_discord():
    futuro = datetime(2030, 1, 1, tzinfo=UTC)
    for desde, hasta in (("2011-12-30", "2011-12-30"), ("2011-12-28", "2011-12-30")):   # Samoa saltó el 30-12-2011
        with pytest.raises(RangoInvalido) as e:
            normalizar_rango(desde, hasta, "Pacific/Apia", futuro, 6000)
        assert e.value.codigo == "fecha_local_inexistente"
    with pytest.raises(RangoInvalido) as e:
        normalizar_rango("2011-12-29", "2011-12-31", "Pacific/Apia", futuro, 6000)
    assert e.value.codigo == "rango_anterior_a_discord"     # antes se invertía al recortar a 2015


@pytest.mark.parametrize("zona, dia", [
    ("America/Sao_Paulo", "2018-11-04"), ("America/Sao_Paulo", "2018-11-03"), ("America/Sao_Paulo", "2019-02-16"),
    ("America/New_York", "2026-03-08"), ("America/New_York", "2026-11-01"), ("America/Guatemala", "2026-10-01"),
    ("America/Havana", "2026-03-08"), ("Asia/Gaza", "2026-03-28"), ("Europe/Madrid", "2026-10-25"),
    ("Australia/Lord_Howe", "2026-04-05"), ("Pacific/Chatham", "2026-09-27"), ("UTC", "2026-06-30"),
])
def test_ida_y_vuelta_a_la_zona(zona, dia):
    from zoneinfo import ZoneInfo
    tz, d = ZoneInfo(zona), datetime.fromisoformat(dia).date()
    r = normalizar_rango(dia, dia, zona, datetime(2030, 1, 1, tzinfo=UTC), 6000)
    un_segundo = timedelta(seconds=1)
    assert r.inicio_utc.astimezone(tz).date() == d and (r.inicio_utc - un_segundo).astimezone(tz).date() < d
    assert r.fin_utc.astimezone(tz).date() > d and (r.fin_utc - un_segundo).astimezone(tz).date() == d
    assert timedelta(hours=22) <= r.fin_utc - r.inicio_utc <= timedelta(hours=26)


def test_guatemala_sin_cambio_de_horario_todo_el_anio():
    for mes in range(1, 13):
        r = normalizar_rango(f"2025-{mes:02d}-15", f"2025-{mes:02d}-15", "America/Guatemala", AHORA, 400)
        assert r.fin_utc - r.inicio_utc == timedelta(hours=24) and r.inicio_utc.hour == 6 and not r.advertencias


class _Reloj(datetime):
    instante = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.instante


def test_idempotencia_rango_hasta_hoy_congela_el_corte(entorno, monkeypatch):
    from backend.app.api.routes import discord_historico as rutas
    monkeypatch.setattr(rutas, "datetime", _Reloj)
    _Reloj.instante = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
    cuerpo = {"canal_id": CANAL, "desde": "2026-10-17", "hasta": "2026-10-18", "zona": "UTC", "max_mensajes": 20}
    cab = {**H, "Idempotency-Key": "hoy-1"}
    a = entorno["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=cab)
    assert a.status_code == 202 and a.json()["importacion"]["hasta_utc"] == "2026-10-18T12:00:00+00:00"
    _Reloj.instante += timedelta(minutes=10)
    b = entorno["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=cab)
    assert b.status_code == 202, b.text
    assert b.json()["importacion"]["id"] == a.json()["importacion"]["id"] and b.json()["reutilizada"]
    assert b.json()["importacion"]["hasta_utc"] == "2026-10-18T12:00:00+00:00"       # el corte original
    assert b.json()["importacion"]["solicitud"] == cuerpo
    # Mismo JSON salvo un parámetro real → 409, también cuando el rango termina hoy.
    for cambio in ({"max_mensajes": 21}, {"desde": "2026-10-16"}, {"zona": "America/Guatemala"}):
        r = entorno["api"].post(f"{BASE}/importaciones", json={**cuerpo, **cambio}, headers=cab)
        assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "clave_idempotencia_reutilizada"), cambio
    # Reintento después de completarse: misma importación, sin crear otra.
    assert correr_runner(entorno) == "completada"
    _Reloj.instante += timedelta(hours=1)
    c = entorno["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=cab)
    assert c.status_code == 202 and c.json()["importacion"]["id"] == a.json()["importacion"]["id"]
    assert c.json()["importacion"]["estado"] == "completada" and c.json()["reutilizada"]
    assert fila(entorno, "SELECT count(*) n FROM discord_importaciones")["n"] == 1


def test_idempotencia_recuperar_clave_no_salta_autorizacion(entorno, monkeypatch):
    cuerpo = {"canal_id": CANAL, "desde": "2026-09-01", "hasta": "2026-09-02", "zona": "UTC", "max_mensajes": 20}
    cab = {**H, "Idempotency-Key": "auth-1"}
    assert entorno["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=cab).status_code == 202
    assert entorno["api"].post(f"{BASE}/importaciones", json=cuerpo,
                               headers={"Idempotency-Key": "auth-1"}).status_code == 401      # sin operador
    monkeypatch.setenv("DISCORD_HISTORICO_AUTORIZADOS", json.dumps({GUILD: [HILO]}))         # canal retirado
    r = entorno["api"].post(f"{BASE}/importaciones", json=cuerpo, headers=cab)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "canal_no_autorizado")


def test_idempotencia_concurrente_misma_clave_converge(entorno):
    from concurrent.futures import ThreadPoolExecutor
    from backend.app.discord_historico.store import huella_solicitud
    store = entorno["store"]
    rango = normalizar_rango("2026-09-01", "2026-09-05", "UTC", AHORA, 400)
    solicitud, huella = huella_solicitud(CANAL, "2026-09-01", "2026-09-05", "UTC", 100)

    def crear_directo(clave):
        try:
            imp, _ = store.crear(guild_id=GUILD, canal_id=CANAL, canal_nombre="c", canal_tipo=0, rango=rango,
                                 max_mensajes=100, solicitante="prueba", clave_idempotencia=clave,
                                 solicitud=solicitud, huella=huella)
            return imp["id"]
        except Exception as exc:
            return getattr(exc, "codigo", type(exc).__name__)
    with ThreadPoolExecutor(10) as ex:
        resultados = list(ex.map(crear_directo, ["misma"] * 8 + ["otra-a", "otra-b"]))
    misma = resultados[:8]
    assert len(set(misma)) == 1 and misma[0].startswith("imp-")                 # todas convergen
    assert set(resultados[8:]) == {"importacion_activa_en_el_canal"}           # otra clave sí choca con la activa
    assert fila(entorno, "SELECT count(*) n FROM discord_importaciones")["n"] == 1


def test_previsualizar_y_crear_con_alcance_congelado(entorno, monkeypatch):
    from backend.app.api.routes import discord_historico as rutas
    monkeypatch.setattr(rutas, "datetime", _Reloj)
    _Reloj.instante = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
    entorno["d"].msg(datetime(2026, 10, 18, 11, 0, tzinfo=UTC), "dentro")
    cuerpo = {"canal_id": CANAL, "desde": "2026-10-18", "hasta": "2026-10-18", "zona": "America/Guatemala", "max_mensajes": 20}
    p = entorno["api"].post(f"{BASE}/previsualizar", json=cuerpo, headers=H).json()
    congelado = p["alcance_congelado"]
    _Reloj.instante += timedelta(minutes=30)          # el operador confirma media hora después
    imp = entorno["api"].post(f"{BASE}/importaciones", json={"canal_id": CANAL, **congelado, "max_mensajes": 20},
                              headers=H).json()["importacion"]
    assert imp["desde_utc"].replace("+00:00", "Z") == p["rango"]["inicio_utc"]
    assert imp["hasta_utc"].replace("+00:00", "Z") == p["rango"]["fin_utc_exclusivo"]    # mismo corte previsualizado


def _trabajo(entorno, id_trabajo, estado, *ids):
    with entorno["cola"].conectar() as c:
        c.execute("INSERT INTO trabajos_worker (id, entrada, estado) VALUES (%s, %s::jsonb, %s)",
                  (id_trabajo, json.dumps({"interacciones": [{"id": i} for i in ids]}), estado))


def test_estado_ia_solo_con_evidencia_de_trabajo(entorno):
    d, api = entorno["d"], entorno["api"]
    m = sembrar(d, datetime(2026, 9, 5, tzinfo=UTC), 6)
    ids = [f"discord-{x['id']}" for x in m]
    with entorno["cola"].conectar() as c:     # los cinco primeros «llegaron en vivo» (guardados en `mensajes`)
        for i in ids[:5]:
            c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                VALUES (%s,'a','2026-09-05T00:00:00Z','discord_x','sin_clasificar','vivo')""", (i,))
        activos_antes = c.execute("SELECT count(*) n FROM activos").fetchone()["n"]
    _trabajo(entorno, "t-pendiente", "recibido", ids[1])
    _trabajo(entorno, "t-procesando", "procesando", ids[2])
    _trabajo(entorno, "t-fallido", "error", ids[3])
    _trabajo(entorno, "t-ok", "terminado", ids[4], "discord-otro")
    imp = crear(entorno, hasta="2026-09-10").json()["importacion"]
    assert correr_runner(entorno) == "completada"
    esperado = {ids[0]: ("sin_evidencia", None, True), ids[1]: ("pendiente", "t-pendiente", True),
                ids[2]: ("pendiente", "t-procesando", True), ids[3]: ("fallido", "t-fallido", True),
                ids[4]: ("procesado", "t-ok", True), ids[5]: ("sin_evidencia", None, False)}
    with entorno["cola"].conectar() as c:
        for i, (estado, trabajo, vivo) in esperado.items():
            f = c.execute("""SELECT estado_ia_captura, estado_ia_trabajo, en_ingesta_vivo, procesado_ia
                FROM discord_mensajes_historicos WHERE id_mensaje=%s""", (i,)).fetchone()
            obtenido = (f["estado_ia_captura"], f["estado_ia_trabajo"], f["en_ingesta_vivo"], f["procesado_ia"])
            assert obtenido == (estado, trabajo, vivo, estado == "procesado"), i
    # Caso inverso: importado sin evidencia y procesado DESPUÉS por otra vía → la API no queda obsoleta.
    _trabajo(entorno, "t-despues", "terminado", ids[5])
    respuesta = api.get(f"{BASE}/importaciones/{imp['id']}/mensajes", headers=H).json()["items"]
    items = {x["id_mensaje"]: x for x in respuesta}
    assert (items[ids[5]]["estado_ia_captura"], items[ids[5]]["estado_ia"], items[ids[5]]["procesado_ia"]) == \
        ("sin_evidencia", "procesado", True)
    assert items[ids[5]]["estado_ia_trabajo"] == "t-despues" and items[ids[3]]["estado_ia"] == "fallido"
    # Ni duplicados ni cambios en la tabla pública ni en activos.
    assert fila(entorno, "SELECT count(*) n FROM discord_mensajes_historicos")["n"] == 6
    with entorno["cola"].conectar() as c:
        assert c.execute("SELECT count(*) n FROM mensajes").fetchone()["n"] == 5
        assert c.execute("SELECT count(*) n FROM mensajes WHERE texto <> 'vivo'").fetchone()["n"] == 0
        assert c.execute("SELECT count(*) n FROM activos").fetchone()["n"] == activos_antes


def test_migracion_desde_version_anterior_del_esquema(entorno):
    """Simula una base creada antes de estas correcciones (sin huella ni estado de IA) con datos ficticios."""
    with entorno["cola"].conectar() as c:
        for col in ("solicitud", "huella_solicitud"):
            c.execute(f"ALTER TABLE discord_importaciones DROP COLUMN IF EXISTS {col}")
        for col in ("en_ingesta_vivo", "estado_ia_captura", "estado_ia_trabajo"):
            c.execute(f"ALTER TABLE discord_mensajes_historicos DROP COLUMN IF EXISTS {col}")
        c.execute("""INSERT INTO discord_importaciones (id, guild_id, canal_id, canal_nombre, canal_tipo, desde_utc,
            hasta_utc, zona, desde_local, hasta_local, max_mensajes, solicitante, estado, clave_idempotencia)
            VALUES ('imp-antigua', %s, %s, 'c', 0, '2026-09-01Z', '2026-09-02Z', 'UTC', 'a', 'b', 10, 'x',
            'completada', 'clave-antigua')""", (GUILD, CANAL))
        c.execute("""INSERT INTO discord_mensajes_historicos (id_mensaje, message_id, guild_id, canal_id, autor_id,
            fecha, texto, contenido_disponible, tipo_discord, importacion_inicial, procesado_ia)
            VALUES ('discord-1', '1', %s, %s, 'a', '2026-09-01T01:00Z', 'previo', true, 0, 'imp-antigua', true)""",
            (GUILD, CANAL))
    entorno["cola"].inicializar()
    f = fila(entorno, "SELECT texto, en_ingesta_vivo, estado_ia_captura FROM discord_mensajes_historicos")
    assert (f["texto"], f["en_ingesta_vivo"], f["estado_ia_captura"]) == ("previo", False, "sin_evidencia")
    assert fila(entorno, "SELECT huella_solicitud FROM discord_importaciones WHERE id='imp-antigua'")["huella_solicitud"] is None
    # Una clave antigua sin huella no se puede «adivinar»: se trata como solicitud distinta (409).
    r = entorno["api"].post(f"{BASE}/importaciones", json={"canal_id": CANAL, "desde": "2026-09-01",
                            "hasta": "2026-09-01", "zona": "UTC"}, headers={**H, "Idempotency-Key": "clave-antigua"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "clave_idempotencia_reutilizada")
    entorno["cola"].inicializar()        # reaplicar es idempotente
    assert fila(entorno, "SELECT count(*) n FROM discord_mensajes_historicos")["n"] == 1
