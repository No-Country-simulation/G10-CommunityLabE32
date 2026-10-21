"""Curaduría: aprobar desde pendiente, versiones LinkedIn/X, «Generar post» e historial.

PostgreSQL local aislado (127.0.0.1:15439/worker_local). Gemini con transporte falso: sin red ni claves
reales. Los tokens son valores de prueba generados aquí.
"""
import json
import os
from urllib.parse import urlparse

import pytest

from worker.processor import ejecutar_grafo
from worker.tests.test_worker import lote

OPERADOR = "operador-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}
COPY = "Ana López completó la certificación OCI Foundations.\nCompartió sus apuntes con el canal.\n#OCI #Cloud"


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
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CURADURIA_MAX_GENERACIONES", raising=False)
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    with TestClient(app) as c:
        yield c


def crear_activo(cola, id_activo="act-cur-1", estado="generado", formato="linkedin", fuente="m-cur-1"):
    with cola.conectar() as c:
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
            VALUES (%s, 'Ana López', '2026-10-15T14:00:00+00:00', 'logros', 'sin_clasificar',
                    'Hoy aprobé la certificación OCI Foundations, ¡gracias por los apuntes!')
            ON CONFLICT DO NOTHING""", (fuente,))
        c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
            fecha_creacion, fecha_actualizacion) VALUES (%s, %s, 'Logro', %s, %s, %s, 1, now(), now())""",
                  (id_activo, formato, COPY, estado, json.dumps([fuente])))
    return id_activo


def detalle(cliente, a):
    r = cliente.get(f"/api/curaduria/activos/{a}", headers=H_OP)
    assert r.status_code == 200, r.text
    return r.json()


def test_aprobar_desde_pendiente_registra_historial_y_editar_invalida(cliente, cola):
    a = crear_activo(cola)
    r = cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado", "comentario_curador": "Fiel a la fuente."},
                      headers=H_OP)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    d = detalle(cliente, a)
    assert [(e["evento"], e["estado"], e["actor"], e["comentario"]) for e in d["historial"]] == [
        ("estado", "aprobado", "Token de operador", "Fiel a la fuente.")]
    # Editar un texto aprobado lo devuelve a revisado y deja constancia de la versión nueva.
    r = cliente.patch(f"/api/curaduria/activos/{a}", json={"copy": COPY + " #Comunidad"}, headers=H_OP)
    assert (r.json()["estado"], r.json()["version"]) == ("revisado", 2)
    eventos = detalle(cliente, a)["historial"]
    assert [(e["evento"], e["estado"], e["version"]) for e in eventos] == [("estado", "aprobado", 1), ("edicion", "revisado", 2)]
    # Las transiciones inválidas siguen rechazadas.
    rechazado = crear_activo(cola, "act-cur-2", estado="rechazado", fuente="m-cur-2")
    assert cliente.patch(f"/api/curaduria/activos/{rechazado}", json={"estado": "aprobado"}, headers=H_OP).status_code == 422


def test_guardar_versiones_linkedin_y_x(cliente, cola):
    a = crear_activo(cola)
    redes = {"linkedin": COPY, "x": "Ana completó OCI Foundations 🏆 #OCI"}
    r = cliente.patch(f"/api/curaduria/activos/{a}", json={"posts_redes": redes}, headers=H_OP)
    assert r.status_code == 200
    assert (r.json()["posts_redes"], r.json()["copy"], r.json()["version"]) == (redes, COPY, 2)   # X nueva = versión nueva
    # Cambiar solo X también versiona; repetir lo mismo no.
    redes2 = {**redes, "x": "Ana completó OCI Foundations. #OCI #Cloud"}
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"posts_redes": redes2}, headers=H_OP).json()["version"] == 3
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"posts_redes": redes2}, headers=H_OP).json()["version"] == 3
    assert detalle(cliente, a)["posts_redes"] == redes2
    # copy distinto de la versión LinkedIn, o X demasiado larga: rechazados sin cambios.
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"copy": "Otro texto distinto", "posts_redes": redes2},
                         headers=H_OP).status_code == 422
    assert cliente.patch(f"/api/curaduria/activos/{a}", json={"posts_redes": {**redes2, "x": "x" * 281}},
                         headers=H_OP).status_code == 422
    assert detalle(cliente, a)["version"] == 3


def _ia_falsa(monkeypatch, respuesta):
    from backend.app.routers import curaduria
    from pipelines.communitylab.gemini import ClienteGemini
    from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, ok
    falso = GeminiFalso(responder=lambda p: ok(respuesta(p)))
    monkeypatch.setattr(curaduria, "_cliente_ia", lambda: ClienteGemini(configuracion(), transporte=falso.transporte))
    return falso


def test_generar_post_linkedin_y_x_sin_guardar_ni_aprobar(cliente, cola, monkeypatch):
    a = crear_activo(cola)
    with cola.conectar() as c:   # el lote de origen aporta comunidad y período a la petición
        c.execute("""INSERT INTO trabajos_worker (id, entrada, estado) VALUES ('t-cur-1', %s, 'terminado')""",
                  (json.dumps({"origen_comunidad": "Demo call center", "periodo_referencia": "2026-W42",
                               "interacciones": [{"id": "m-cur-1"}]}),))
    textos = {"linkedin": "Ana López: certificación OCI Foundations 🏆\nAna aprobó la certificación.\n#OCI #Cloud",
              "x": "Ana aprobó OCI Foundations 🏆 #OCI"}
    falso = _ia_falsa(monkeypatch, lambda p: textos)
    assert cliente.post(f"/api/curaduria/activos/{a}/posts/generar", json={"redes": ["linkedin", "x"]}).status_code == 401
    r = cliente.post(f"/api/curaduria/activos/{a}/posts/generar", json={"redes": ["linkedin", "x"]}, headers=H_OP)
    assert r.status_code == 200, r.text
    assert r.json() == {**textos, "generaciones_restantes": 2}
    usuario = falso.peticiones[0]["cuerpo"]["contents"][0]["parts"][0]["text"]
    assert "Demo call center" in usuario and "certificación OCI Foundations" in usuario and len(falso.peticiones) == 1
    d = detalle(cliente, a)
    assert (d["copy"], d["estado"], d["version"], d["posts_redes"]) == (COPY, "generado", 1, None)   # nada guardado
    assert d["historial"][-1]["evento"] == "posts_generados" and d["generaciones_restantes"] == 2
    # Redes desconocidas o campos extra: 422 sin gastar IA.
    assert cliente.post(f"/api/curaduria/activos/{a}/posts/generar", json={"redes": ["instagram"]}, headers=H_OP).status_code == 422
    assert len(falso.peticiones) == 1


def test_generar_post_tope_fallos_y_sin_configuracion_devuelven_el_intento(cliente, cola, monkeypatch):
    a = crear_activo(cola)
    ruta = f"/api/curaduria/activos/{a}/posts/generar"
    # Sin GEMINI_API_KEY: 503 y el intento no se consume.
    assert cliente.post(ruta, headers=H_OP).json()["detail"]["codigo"] == "ia_no_configurada"
    # Respuesta inválida (X de más de 280 caracteres en ambos modelos): 502 y tampoco se consume.
    _ia_falsa(monkeypatch, lambda p: {"linkedin": COPY, "x": "x" * 300})
    r = cliente.post(ruta, headers=H_OP)
    assert r.status_code == 502 and r.json()["detail"]["codigo"] == "ia_fallo"
    assert detalle(cliente, a)["generaciones_restantes"] == 3
    # Tope por borrador.
    monkeypatch.setenv("CURADURIA_MAX_GENERACIONES", "1")
    falso = _ia_falsa(monkeypatch, lambda p: {"linkedin": COPY, "x": "Ana aprobó OCI. #OCI"})
    assert cliente.post(ruta, headers=H_OP).status_code == 200
    r = cliente.post(ruta, headers=H_OP)
    assert r.status_code == 429 and r.json()["detail"]["codigo"] == "limite_generaciones" and len(falso.peticiones) == 1
    # Solo logros: un FAQ no admite «Generar post».
    faq = crear_activo(cola, "act-cur-faq", formato="faq", fuente="m-cur-3")
    assert cliente.post(f"/api/curaduria/activos/{faq}/posts/generar", headers=H_OP).json()["detail"]["codigo"] == "formato_sin_posts"
    assert cliente.post("/api/curaduria/activos/no-existe/posts/generar", headers=H_OP).status_code == 404


def test_worker_registra_el_evento_generado_una_sola_vez(cola):
    cola.encolar(lote())
    t = cola.reservar()
    salida = ejecutar_grafo(t.entrada, "simulado")
    assert cola.terminar(t, salida) is True
    with cola.conectar() as c:
        activos = c.execute("SELECT count(*) n FROM activos").fetchone()["n"]
        eventos = c.execute("""SELECT count(*) n FROM activos_historial
            WHERE evento='generado' AND estado='generado' AND version=1 AND actor='ia'""").fetchone()["n"]
    assert activos > 0 and eventos == activos
    assert cola.terminar(t, salida) is False   # un reintento con la misma reserva no duplica nada
    with cola.conectar() as c:
        assert c.execute("SELECT count(*) n FROM activos_historial").fetchone()["n"] == activos
