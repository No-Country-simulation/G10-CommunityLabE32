"""Flujo híbrido, sentimiento y banners sobre PostgreSQL local aislado (127.0.0.1:15439/worker_local).

Sin red ni proveedores reales: Gemini con transporte falso, puente con urlopen redirigido al
TestClient, datos ficticios. Los tokens son valores de prueba generados aquí.
"""
import io
import json
import os
from pathlib import Path
from contextlib import closing
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlparse
import urllib.error

import pytest

from worker.core import Worker
from worker.processor import ejecutar_grafo

OPERADOR = "operador-local-" + os.urandom(6).hex()
PUENTE = "puente-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}


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
        c.execute("TRUNCATE trabajos_worker, activos, mensajes, solicitudes_procesamiento, estado_puente, banners")
    return q


@pytest.fixture
def cliente(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("OPERADOR_TOKEN", OPERADOR)
    monkeypatch.setenv("PUENTE_TOKEN", PUENTE)
    monkeypatch.setenv("PUENTE_ORIGEN", "discord")
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    with TestClient(app) as c:
        yield c


def lote(ids, cierre=False, periodo="2026-W42", origen="discord"):
    return {"origen_comunidad": origen, "periodo_referencia": periodo, "cierre_periodo": cierre,
            "interacciones": [{"id": i, "autor": f"a-{i}", "canal": "general", "fecha": "2026-10-13T10:00:00Z",
                               "texto": f"Mensaje ficticio {i}"} for i in ids]}


def procesar_gemini_falso(cola, sentimientos, relevancia=0.1):
    """Worker con los componentes Gemini reales y transporte falso: analizar devuelve sentimiento."""
    from pipelines.communitylab import ejecutar_lote
    from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
    from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, ok, tarea_de

    def responder(p):
        # analizar y puntuar reciben una lista de {"id", ...}; con relevancia baja no hay generación.
        items = json.loads(p["cuerpo"]["contents"][0]["parts"][0]["text"])
        if tarea_de(p) == "analizar":
            return ok({"resultados": [{"id": m["id"], "es_logro": False, "es_duda": False, "es_bloqueo": False,
                                       "tema": "general", **({"sentimiento": sentimientos[m["id"]]}
                                                             if m["id"] in sentimientos else {})}
                                      for m in items]})
        return ok({"resultados": [{"id": m["id"], "relevancia": relevancia} for m in items]})

    falso = GeminiFalso(responder=responder)
    worker = Worker(cola, lambda entrada, renovar: ejecutar_lote(
        entrada, crear_componentes_gemini(configuracion(), transporte=falso.transporte)))
    while worker.ejecutar_uno():
        pass
    return falso


def fila(cola, sql, *p):
    with cola.conectar() as c:
        return c.execute(sql, p).fetchone()


# --- Sentimiento ---------------------------------------------------------------------

def test_sentimiento_se_guarda_con_procedencia_y_no_se_pisa(cliente, cola):
    t1 = cola.encolar(lote(["s-1", "s-2", "s-3"]))
    procesar_gemini_falso(cola, {"s-1": "positivo", "s-2": "indeterminado"})  # s-3 sin sentimiento
    m1 = fila(cola, "SELECT * FROM mensajes WHERE id_mensaje='s-1'")
    assert (m1["sentimiento_ref"], m1["sentimiento_origen"], m1["sentimiento_version"],
            m1["sentimiento_trabajo"]) == ("positivo", "gemini", "gemini-analizar-v1", t1)
    assert fila(cola, "SELECT sentimiento_ref FROM mensajes WHERE id_mensaje='s-3'")["sentimiento_ref"] is None
    assert fila(cola, "SELECT resultado FROM trabajos_worker WHERE id=%s", t1)["resultado"][
        "persistencia"]["sentimientos"] == 2
    # Otro lote con los mismos mensajes y otro valor: nunca sobrescribe uno válido.
    cola.encolar(lote(["s-1", "s-3"], periodo="2026-W43"))
    procesar_gemini_falso(cola, {"s-1": "negativo", "s-3": "neutral"})
    assert fila(cola, "SELECT sentimiento_ref FROM mensajes WHERE id_mensaje='s-1'")["sentimiento_ref"] == "positivo"
    assert fila(cola, "SELECT sentimiento_ref FROM mensajes WHERE id_mensaje='s-3'")["sentimiento_ref"] == "neutral"


def test_guardar_sentimientos_valida_ids_valores_y_simulado(cola):
    from worker.store_postgres import guardar_sentimientos
    cola.encolar(lote(["v-1", "v-2"]))
    trabajo = SimpleNamespace(id="t-x", entrada=lote(["v-1", "v-2"]))
    with cola.conectar() as c:
        n = guardar_sentimientos(c, trabajo, {"simulado": False, "sentimientos": {
            "v-1": "feliz", "ajeno": "positivo", "v-2": "negativo"}})
        assert n == 1
        assert guardar_sentimientos(c, trabajo, {"simulado": True, "sentimientos": {"v-1": "positivo"}}) == 0
    assert fila(cola, "SELECT sentimiento_ref FROM mensajes WHERE id_mensaje='v-1'")["sentimiento_ref"] is None
    assert fila(cola, "SELECT count(*) n FROM mensajes WHERE id_mensaje='ajeno'")["n"] == 0


def test_modo_simulado_no_inventa_sentimiento(cola):
    cola.encolar(lote(["z-1"]))
    Worker(cola, lambda e, r: ejecutar_grafo(e, "simulado")).ejecutar_uno()
    assert fila(cola, "SELECT sentimiento_ref FROM mensajes WHERE id_mensaje='z-1'")["sentimiento_ref"] is None


def test_filtro_y_resumen_de_sentimiento_en_servidor(cliente, cola):
    cola.encolar(lote([f"f-{i}" for i in range(6)]))
    procesar_gemini_falso(cola, {"f-0": "positivo", "f-1": "positivo", "f-2": "negativo", "f-3": "indeterminado"})
    with cola.conectar() as c:
        c.execute("UPDATE mensajes SET canal='otro' WHERE id_mensaje='f-0'")
    r = cliente.get("/api/mensajes/sentimiento/resumen").json()
    assert (r["total"], r["analizados"], r["sin_analizar"], r["denominador"]) == (6, 4, 2, "analizados")
    assert r["por_valor"] == {"positivo": 2, "negativo": 1, "neutral": 0, "indeterminado": 1}
    assert r["porcentaje_sobre_analizados"]["positivo"] == 50.0 and r["estado"] == "parcial"
    canal = cliente.get("/api/mensajes/sentimiento/resumen", params={"canal": "general"}).json()
    assert (canal["total"], canal["por_valor"]["positivo"]) == (5, 1)
    sin = cliente.get("/api/mensajes", params={"sentimiento": "sin_analizar", "limit": 1}).json()
    assert sin["total"] == 2 and len(sin["items"]) == 1
    assert cliente.get("/api/mensajes", params={"sentimiento": "indeterminado"}).json()["total"] == 1
    assert cliente.get("/api/mensajes", params={"sentimiento": "feliz"}).status_code == 422
    kpis = cliente.get("/api/dashboard/kpis").json()
    assert kpis["sentimiento"]["clasificados"] == 4  # indeterminado cuenta como analizado


def test_reproceso_historico_previsualiza_limita_reanuda_y_es_idempotente(cola):
    from backend.scripts import reprocesar_sentimiento as rp
    cola.encolar(lote([f"h-{i:02d}" for i in range(10)]))
    with cola.conectar() as c:
        c.execute("UPDATE mensajes SET sentimiento_ref='neutral', sentimiento_origen='manual' "
                  "WHERE id_mensaje='h-00'")
        vista = rp.previsualizar(c, 4)
    assert (vista["sin_analizar_en_alcance"], vista["bloques"], vista["llamadas_maximas"]) == (9, 3, 6)
    llamadas = []

    def analizar(l, maximo):
        llamadas.append([m["id"] for m in l["interacciones"]])
        return {m["id"]: {"sentimiento": "positivo"} for m in l["interacciones"]} | {"ajeno": {"sentimiento": "x"}}, 1

    r1 = rp.ejecutar(cola.url, analizar, 4, limite=5, max_llamadas=10)
    assert (r1["procesados"], r1["guardados"], r1["detenido_por"]) == (5, 5, "limite")
    r2 = rp.ejecutar(cola.url, analizar, 4, limite=100, max_llamadas=1)
    assert (r2["procesados"], r2["detenido_por"]) == (4, "max_llamadas")
    r3 = rp.ejecutar(cola.url, analizar, 4, limite=100, max_llamadas=10)
    assert (r3["procesados"], r3["detenido_por"]) == (0, "completo")  # nada pendiente: cero llamadas
    assert sum(map(len, llamadas)) == 9
    m0 = fila(cola, "SELECT sentimiento_ref, sentimiento_origen FROM mensajes WHERE id_mensaje='h-00'")
    assert (m0["sentimiento_ref"], m0["sentimiento_origen"]) == ("neutral", "manual")

    def falla(l, maximo):
        raise RuntimeError("proveedor")
    cola.encolar(lote(["h-99"], periodo="2026-W44"))
    assert rp.ejecutar(cola.url, falla, 4, 10, 10)["detenido_por"] == "fallo_proveedor:RuntimeError"


# --- Acceso ---------------------------------------------------------------------------

def test_acciones_protegidas_rechazan_sin_token(cliente, monkeypatch):
    assert cliente.post("/api/v1/procesamiento-pendientes").status_code == 401
    assert cliente.post("/api/v1/procesamiento-pendientes", headers={"X-Operador-Token": "x"}).status_code == 401
    assert cliente.post("/api/v1/puente/solicitudes/tomar", json={"origen": "discord"},
                        headers={"Authorization": f"Bearer {OPERADOR}"}).status_code == 401
    monkeypatch.delenv("OPERADOR_TOKEN")
    r = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "acceso_no_configurado")
    assert OPERADOR not in r.text


# --- Solicitudes «Procesar pendientes» -------------------------------------------------

def test_doble_clic_reutiliza_la_solicitud_abierta(cliente, cola):
    a = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP)
    b = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP)
    assert a.status_code == 202 and a.json()["id"] == b.json()["id"]
    assert (a.json()["reutilizada"], b.json()["reutilizada"]) == (False, True)
    assert fila(cola, "SELECT count(*) n FROM solicitudes_procesamiento")["n"] == 1
    with pytest.raises(Exception):  # el índice único impide dos abiertas aun sin la API
        with cola.conectar() as c:
            c.execute("INSERT INTO solicitudes_procesamiento (id, origen) VALUES ('otra', 'discord')")


def test_toma_reserva_vencimiento_e_informe(cliente, cola):
    bearer = {"Authorization": f"Bearer {PUENTE}"}
    sid = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP).json()["id"]
    toma = cliente.post("/api/v1/puente/solicitudes/tomar", headers=bearer,
                        json={"origen": "discord", "pendientes": {"2026-W42": 3}})
    assert toma.json() == {"id": sid}
    assert cliente.post("/api/v1/puente/solicitudes/tomar", headers=bearer,
                        json={"origen": "discord"}).json() == {"id": None}
    with cola.conectar() as c:
        c.execute("UPDATE solicitudes_procesamiento SET vence=clock_timestamp() - interval '1 second'")
    # Reserva vencida (el puente cayó antes de planificar): se reofrece el MISMO id.
    assert cliente.post("/api/v1/puente/solicitudes/tomar", headers=bearer,
                        json={"origen": "discord"}).json() == {"id": sid}
    trabajo = cola.encolar(lote(["p-1", "p-2"]))
    lotes = [{"periodo": "2026-W42", "nuevos": 2, "contexto": 0, "trabajo": trabajo, "estado": "aceptado"}]
    cliente.post(f"/api/v1/puente/solicitudes/{sid}/informe", headers=bearer,
                 json={"origen": "discord", "estado": "en_curso", "lotes": lotes, "pendientes": {}})
    actual = cliente.get("/api/v1/procesamiento-pendientes/actual").json()
    assert actual["solicitud"]["estado"] == "en_curso"
    assert actual["solicitud"]["lotes"][0]["trabajo_estado"] == "recibido"
    assert actual["puente"]["activo"] is True
    Worker(cola, lambda e, r: ejecutar_grafo(e, "simulado")).ejecutar_uno()
    lotes[0]["estado"] = "terminado"
    fin = cliente.post(f"/api/v1/puente/solicitudes/{sid}/informe", headers=bearer,
                       json={"origen": "discord", "estado": "finalizada", "lotes": lotes, "pendientes": {}})
    assert fin.json()["estado"] == "completada"
    detalle = cliente.get(f"/api/v1/procesamiento-pendientes/{sid}").json()
    assert (detalle["trabajos_terminados"], detalle["mensajes_nuevos"]) == (1, 2)
    assert detalle["historial"] == ["pendiente", "tomada", "tomada", "en_curso", "completada"]
    # Cerrada: un informe tardío no la reabre y una nueva solicitud obtiene otro id.
    assert cliente.post(f"/api/v1/puente/solicitudes/{sid}/informe", headers=bearer,
                        json={"origen": "discord", "estado": "en_curso", "lotes": []}).json() == {"actualizada": False}
    assert cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP).json()["id"] != sid


# --- Extremo a extremo: puente real + API real + worker -------------------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _urlopen_hacia(cliente):
    def urlopen(peticion, timeout=None):
        ruta = urlparse(peticion.full_url).path
        cabeceras = {k: v for k, v in peticion.header_items()}
        r = cliente.request(peticion.get_method(), ruta, content=peticion.data, headers=cabeceras)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(peticion.full_url, r.status_code, "x", {}, io.BytesIO(r.content))
        return _Resp(r.content)
    return urlopen


def test_extremo_a_extremo_parcial_sin_pendientes_y_cierre(cliente, cola, tmp_path, monkeypatch):
    from pipelines.communitylab import prueba_integracion_discord as cli
    from pipelines.communitylab.puente_discord import Puente
    from datetime import datetime, timezone
    monkeypatch.setattr(cli.urllib.request, "urlopen", _urlopen_hacia(cliente))
    bandeja = tmp_path / "bandeja.sqlite3"
    with closing(sqlite3.connect(bandeja)) as c, c:
        c.execute("CREATE TABLE messages (sequence INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, "
                  "message_id TEXT, payload TEXT, UNIQUE(guild_id, message_id))")

    def agregar(*mids):
        with closing(sqlite3.connect(bandeja)) as c, c:
            for mid in mids:
                e = {"schema_version": "discord-source-v1", "message_id": str(mid), "guild_id": "1",
                     "channel_id": "2", "author_id": f"9{mid}", "created_at": "2026-10-13T10:00:00Z",
                     "content": f"Mensaje ficticio {mid}"}
                c.execute("INSERT INTO messages(guild_id,message_id,payload) VALUES (?,?,?)",
                          ("1", str(mid), json.dumps(e)))

    reloj = {"t": datetime(2026, 10, 14, tzinfo=timezone.utc).timestamp()}
    puente = Puente(tmp_path / "estado.sqlite3", bandeja, "http://api/api/v1/trabajos",
                    reloj=lambda: reloj["t"], token=PUENTE)
    worker = Worker(cola, lambda e, r: ejecutar_grafo(e, "simulado"))
    agregar(101, 102)
    puente.ciclo()                                   # informa 2 pendientes, sin solicitud
    assert cliente.get("/api/v1/procesamiento-pendientes/actual").json()["puente"]["pendientes"] == 2
    sid = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP).json()["id"]
    puente.ciclo()                                   # toma, planifica y envía el parcial
    assert fila(cola, "SELECT count(*) n FROM trabajos_worker")["n"] == 1
    entrada = fila(cola, "SELECT entrada FROM trabajos_worker")["entrada"]
    assert entrada["cierre_periodo"] is False and len(entrada["interacciones"]) == 2
    while worker.ejecutar_uno():
        pass
    puente.ciclo()                                   # ve terminado e informa
    actual = cliente.get("/api/v1/procesamiento-pendientes/actual").json()
    assert (actual["solicitud"]["id"], actual["solicitud"]["estado"]) == (sid, "completada")
    assert actual["puente"]["pendientes"] == 0
    # Sin pendientes: la siguiente solicitud termina sin trabajos (cero llamadas a Gemini).
    sid2 = cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP).json()["id"]
    puente.ciclo()
    assert cliente.get(f"/api/v1/procesamiento-pendientes/{sid2}").json()["estado"] == "sin_pendientes"
    assert fila(cola, "SELECT count(*) n FROM trabajos_worker")["n"] == 1
    # Llega uno nuevo: el siguiente parcial lleva 1 nuevo + 2 de contexto previo.
    agregar(103)
    cliente.post("/api/v1/procesamiento-pendientes", headers=H_OP)
    puente.ciclo()
    with cola.conectar() as c:
        ultima = c.execute("SELECT entrada FROM trabajos_worker ORDER BY creado DESC LIMIT 1").fetchone()["entrada"]
    previos = sorted(m["id"] for m in ultima["interacciones"] if m.get("previo"))
    assert previos == ["discord-101", "discord-102"]
    while worker.ejecutar_uno():
        pass
    puente.ciclo()
    # Cierre semanal: un solo envío con todo como previo; ningún activo de contenido duplicado.
    reloj["t"] = datetime(2026, 10, 21, tzinfo=timezone.utc).timestamp()
    puente.ciclo()
    while worker.ejecutar_uno():
        pass
    with cola.conectar() as c:
        cierre = c.execute("SELECT entrada FROM trabajos_worker WHERE (entrada->>'cierre_periodo')::boolean"
                           ).fetchone()["entrada"]
    assert all(m.get("previo") for m in cierre["interacciones"])
    assert fila(cola, "SELECT count(*) n FROM mensajes")["n"] == 3


# --- Banners --------------------------------------------------------------------------

def crear_activo(cola, id_activo="act-banner-1", estado="generado", copy=None):
    copy = copy or "Ana López completó su primer despliegue en la nube.\nCompartió la guía con el canal.\n#Comunidad #Cloud"
    with cola.conectar() as c:
        c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
            fecha_creacion, fecha_actualizacion) VALUES (%s,'linkedin','Logro',%s,%s,'[]',1,now(),now())""",
            (id_activo, copy, estado))
    return id_activo


def test_banner_solo_desde_texto_aprobado_y_aprobacion_protegida(cliente, cola):
    a = crear_activo(cola, estado="revisado")
    assert cliente.post(f"/api/curaduria/activos/{a}/banners", headers=H_OP).status_code == 409
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado"}).status_code == 401
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado"}, headers=H_OP).status_code == 200
    assert cliente.post(f"/api/curaduria/activos/{a}/banners").status_code == 401


def test_banner_generado_versionado_invalidado_y_revisado(cliente, cola):
    a = crear_activo(cola, estado="revisado")
    cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado"}, headers=H_OP)
    g = cliente.post(f"/api/curaduria/activos/{a}/banners", headers=H_OP)
    assert g.status_code == 201, g.text
    b = g.json()
    assert (b["estado"], b["revision"], b["version_texto"], b["desactualizado"], b["reutilizado"]) == \
        ("generado", "pendiente", 1, False, False)
    svg = cliente.get(b["url"])
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.headers["x-content-type-options"] == "nosniff" and "default-src 'none'" in \
        svg.headers["content-security-policy"]
    assert "Ana López completó su primer despliegue en la nube" in svg.text and "#Comunidad #Cloud" in svg.text
    otra = cliente.post(f"/api/curaduria/activos/{a}/banners", headers=H_OP)
    assert (otra.status_code, otra.json()["id"], otra.json()["reutilizado"]) == (200, b["id"], True)
    assert fila(cola, "SELECT count(*) n FROM banners")["n"] == 1
    # Editar el texto aprobado invalida la aprobación y deja el banner desactualizado.
    e = cliente.patch(f"/api/curaduria/activos/{a}", json={"copy": "Ana López terminó su despliegue.\n#Cloud"})
    assert (e.json()["estado"], e.json()["version"]) == ("revisado", 2)
    lista = cliente.get(f"/api/curaduria/activos/{a}/banners").json()
    assert lista["banners"][0]["desactualizado"] is True and lista["vigente"] is None
    assert lista["puede_generar"] is False and lista["generacion_ia"] is False
    r = cliente.post(f"/api/banners/{b['id']}/revision", json={"decision": "aprobado"}, headers=H_OP)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "banner_desactualizado")
    cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado"}, headers=H_OP)
    nuevo = cliente.post(f"/api/curaduria/activos/{a}/banners", headers=H_OP).json()
    assert nuevo["version_texto"] == 2 and nuevo["id"] != b["id"]
    ok = cliente.post(f"/api/banners/{nuevo['id']}/revision", json={"decision": "aprobado"}, headers=H_OP)
    assert (ok.json()["revision"], ok.json()["publicado"]) == ("aprobado", False)
    assert cliente.post(f"/api/banners/{nuevo['id']}/revision", json={"decision": "aprobado"}).status_code == 401


def test_banner_escapa_contenido_error_y_recuperacion(cliente, cola):
    hostil = crear_activo(cola, "act-hostil", "aprobado",
                          '<script>alert(1)</script> "Logro" & <img src=x onerror=1>\n#Seguridad')
    b = cliente.post(f"/api/curaduria/activos/{hostil}/banners", headers=H_OP).json()
    svg = cliente.get(b["url"]).text
    assert "<script" not in svg and "<img" not in svg and "&lt;script&gt;" in svg
    vacio = crear_activo(cola, "act-vacio", "aprobado", "#SoloHashtags #Nada")
    e = cliente.post(f"/api/curaduria/activos/{vacio}/banners", headers=H_OP).json()
    assert (e["estado"], e["error_codigo"], e["url"]) == ("error", "texto_insuficiente", None)
    assert cliente.get(f"/api/banners/{e['id']}.svg").status_code == 404
    # Un banner que quedó en «generando» por un reinicio se recupera pasado el umbral.
    a = crear_activo(cola, "act-colgado", "aprobado")
    from backend.app.api.routes.banners import id_banner
    with cola.conectar() as c:
        c.execute("""INSERT INTO banners (id,id_activo,version_texto,huella_texto,estado,proveedor,plantilla,actualizado)
            VALUES (%s,%s,1,'x','generando','plantilla-svg-v1','p', now() - interval '1 hour')""",
                  (id_banner(a, 1), a))
    rec = cliente.post(f"/api/curaduria/activos/{a}/banners", headers=H_OP).json()
    assert (rec["estado"], rec["intentos"]) == ("generado", 1)


# --- Render del banner (sin base de datos) ---------------------------------------------

def test_render_banner_determinista_ajustado_y_sin_hechos_inventados():
    import re
    from backend.app.services import banners as b
    copy = ("🏆 Mariana López obtiene la certificación oficial AWS Cloud Practitioner con una preparación "
            "de seis semanas y muchísimas horas de estudio constante\nFelicitamos a Mariana.\n#AWS #Cloud")
    svg = b.renderizar("linkedin", copy)
    assert svg == b.renderizar("linkedin", copy)                      # determinista
    textos = re.findall(r'<text[^>]*font-size="54"[^>]*>(.*?)</text>', svg)
    assert 1 <= len(textos) <= 3 and textos[-1].endswith("…")          # se trunca, no desborda
    assert all(b._ancho_px(t, 54, True) <= 1072 for t in textos)
    palabras_copy = set(re.findall(r"\w+", copy.lower()))
    fijas = set(re.findall(r"\w+", " ".join([*b.ETIQUETAS.values(), "CommunityLab G10 EQUIPO 32 Felicitaciones",
                                              "FAQ de la comunidad Respuesta completa en la publicación",
                                              "Lo mejor de la semana"]).lower()))
    visibles = set(re.findall(r"\w+", " ".join(re.findall(r">([^<]+)<", svg)).lower()))
    assert visibles <= palabras_copy | fijas                            # solo texto del copy o de la plantilla
    assert "🏆" not in svg
    with pytest.raises(b.BannerNoGenerable):
        b.renderizar("faq", "#solo #hashtags")
    assert "MUY_LARGA" in b.renderizar("faq", "¿" + "MUY_LARGA" * 30 + "?")  # palabra sin espacios: se corta
