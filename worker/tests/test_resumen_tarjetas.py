"""Resumen: listados de las cuatro tarjetas con los mismos conjuntos que sus contadores.

PostgreSQL local aislado (127.0.0.1:15439/worker_local); datos ficticios sembrados aquí.
"""
import json
import os
from urllib.parse import urlparse

import pytest

OPERADOR = "operador-local-" + os.urandom(6).hex()
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


def sembrar(cola):
    """6 mensajes en dos lotes; alertas repetidas entre trabajos; borradores en varios estados."""
    with cola.conectar() as c:
        for i in range(1, 7):
            c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                VALUES (%s, %s, %s, 'general', 'sin_clasificar', %s)""",
                      (f"m-{i}", f"Persona {i}", f"2026-10-1{i}T10:00:00+00:00", f"Mensaje ficticio {i}"))
        alerta = lambda f: {"id_alerta": f"al-{f}", "nivel": "revision", "fuente": f,
                            "mensaje": "Bloqueo detectado; requiere revisión interna.", "visibilidad": "interna"}
        trabajos = [
            ("t-1", "Demo", "2026-W41", "terminado", ["m-1", "m-2", "m-3"], [alerta("m-1"), alerta("m-2")]),
            ("t-2", "Demo", "2026-W42", "terminado", ["m-4", "m-5", "m-6", "m-1"], [alerta("m-1"), alerta("m-4")]),
            ("t-3", "Demo", "2026-W42", "error", ["m-6"], [alerta("m-6")]),    # no terminado: no cuenta
        ]
        for ident, origen, periodo, estado, ids, alertas in trabajos:
            c.execute("""INSERT INTO trabajos_worker (id, entrada, estado, resultado) VALUES (%s, %s, %s, %s)""",
                      (ident, json.dumps({"origen_comunidad": origen, "periodo_referencia": periodo,
                                          "interacciones": [{"id": i} for i in ids]}),
                       estado, json.dumps({"alertas_internas": alertas, "activos_distribucion_generados": []})))
        for ident, estado, fuentes in [("a-1", "aprobado", ["m-2"]), ("a-2", "generado", ["m-2", "m-3"]),
                                       ("a-3", "revisado", ["m-5"]), ("a-4", "rechazado", ["m-6"]),
                                       ("a-5", "generado", ["m-6"])]:
            c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
                fecha_creacion, fecha_actualizacion) VALUES (%s, 'linkedin', 'Logro', 'Texto ficticio', %s, %s, 1, now(), now())""",
                      (ident, estado, json.dumps(fuentes)))


def test_detalle_de_alertas_coincide_con_el_contador(cliente, cola):
    sembrar(cola)
    assert cliente.get("/api/dashboard/alertas").status_code == 401
    kpi = cliente.get("/api/dashboard/kpis", headers=H_OP).json()["alertas_internas"]
    r = cliente.get("/api/dashboard/alertas", headers=H_OP).json()
    assert r["total"] == kpi == 3                       # m-1 (dos veces), m-2, m-4; t-3 no terminó
    assert [a["id_mensaje"] for a in r["items"]] == ["m-4", "m-2", "m-1"]   # más reciente primero
    m1 = next(a for a in r["items"] if a["id_mensaje"] == "m-1")
    assert (m1["veces"], m1["trabajo"], m1["texto"], m1["autor"]) == (2, "t-1", "Mensaje ficticio 1", "Persona 1")
    assert m1["motivo"] == "Bloqueo detectado; requiere revisión interna."
    # Paginación y ámbito: el filtro usa el mismo criterio que los KPI.
    pagina = cliente.get("/api/dashboard/alertas?skip=1&limit=1", headers=H_OP).json()
    assert (pagina["total"], [a["id_mensaje"] for a in pagina["items"]]) == (3, ["m-2"])
    w42 = cliente.get("/api/dashboard/alertas?origen=Demo&periodo=2026-W42", headers=H_OP).json()
    assert w42["total"] == cliente.get("/api/dashboard/kpis?origen=Demo&periodo=2026-W42", headers=H_OP).json()["alertas_internas"] == 2


def test_cada_mensaje_trae_su_categoria(cliente, cola):
    sembrar(cola)
    items = {m["id_mensaje"]: m for m in cliente.get("/api/mensajes?limit=10", headers=H_OP).json()["items"]}
    assert {i: (m["alerta_interna"], m["estado_borrador"]) for i, m in items.items()} == {
        "m-1": (True, None), "m-2": (True, "aprobado"),      # aprobado gana sobre pendiente
        "m-3": (False, "pendiente"), "m-4": (True, None),
        "m-5": (False, "pendiente"),                         # revisado también es pendiente
        "m-6": (False, "pendiente"),                         # pendiente gana sobre rechazado; t-3 no terminó
    }


def test_pendientes_en_un_solo_listado(cliente, cola):
    sembrar(cola)
    kpi = cliente.get("/api/dashboard/kpis", headers=H_OP).json()["borradores_pendientes"]
    r = cliente.get("/api/curaduria/activos?estados=generado,revisado&limit=2", headers=H_OP).json()
    assert (r["total"], r["total_pages"], len(r["items"])) == (kpi, 2, 2) and kpi == 3
    assert {a["estado"] for a in r["items"]} <= {"generado", "revisado"}
    assert cliente.get("/api/curaduria/activos?estados=generado,borrado", headers=H_OP).status_code == 422
    assert cliente.get("/api/curaduria/activos?estado=aprobado&estados=generado", headers=H_OP).status_code == 422
    assert cliente.get("/api/curaduria/activos?estado=aprobado", headers=H_OP).json()["total"] == 1
