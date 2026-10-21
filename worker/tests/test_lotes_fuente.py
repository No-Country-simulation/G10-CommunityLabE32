"""Analítica: vía de entrada de cada lote, selección de varios lotes y «ningún lote».

PostgreSQL local aislado (127.0.0.1:15439/worker_local); datos y tokens ficticios generados aquí.
"""
import io
import json
import os
from urllib.parse import urlparse

import pytest

OPERADOR = "operador-local-" + os.urandom(6).hex()
PUENTE = "puente-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}
H_PUENTE = {"Authorization": f"Bearer {PUENTE}"}


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
    monkeypatch.setenv("PUENTE_TOKEN", PUENTE)
    monkeypatch.setenv("PUENTE_ORIGEN", "discord")
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    with TestClient(app) as c:
        yield c


def lote(prefijo, n, origen, periodo):
    return {"origen_comunidad": origen, "periodo_referencia": periodo, "cierre_periodo": False,
            "interacciones": [{"id": f"{prefijo}-{i}", "autor": f"Persona {i}", "canal": "general",
                               "fecha": f"2026-10-1{i}T10:00:00Z", "texto": f"Mensaje ficticio {prefijo} {i}"}
                              for i in range(n)]}


def sembrar(cliente, cola):
    """Discord por el puente (3 + 2), carga manual por archivo (4) y un trabajo antiguo sin fuente (1)."""
    assert cliente.post("/api/v1/trabajos", json=lote("d43", 3, "discord", "2026-W43"), headers=H_PUENTE).status_code == 202
    assert cliente.post("/api/v1/trabajos", json=lote("d42", 2, "discord", "2026-W42"), headers=H_PUENTE).status_code == 202
    archivo = json.dumps(lote("cc", 4, "x", "x")["interacciones"]).encode()
    r = cliente.post("/api/mensajes/procesamientos", headers=H_OP,
                     files={"file": ("demo.json", io.BytesIO(archivo), "application/json")},
                     data={"origen_comunidad": "Demo call center", "periodo_referencia": "2026-W42"})
    assert r.status_code == 202, r.text
    with cola.conectar() as c:   # trabajo anterior a la columna `fuente`: se deduce por el origen
        c.execute("""INSERT INTO trabajos_worker (id, entrada, estado) VALUES ('viejo', %s, 'recibido')""",
                  (json.dumps(lote("v", 1, "discord", "2026-W41")),))
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
            VALUES ('v-0', 'Persona 0', '2026-10-10T10:00:00Z', 'general', 'sin_clasificar', 'Mensaje ficticio v 0')""")


def test_cada_lote_dice_por_donde_entro(cliente, cola):
    sembrar(cliente, cola)
    with cola.conectar() as c:
        fuentes = {f["periodo"]: f["fuente"] for f in c.execute(
            "SELECT entrada->>'periodo_referencia' periodo, entrada->>'origen_comunidad' origen, fuente "
            "FROM trabajos_worker WHERE entrada->>'origen_comunidad' <> 'Demo call center'")}
    assert fuentes == {"2026-W43": "discord", "2026-W42": "discord", "2026-W41": None}
    ambitos = {(a["origen"], a["periodo"]): a["fuente_ingesta"]
               for a in cliente.get("/api/dashboard/ambitos", headers=H_OP).json()["items"]}
    assert ambitos == {("discord", "2026-W43"): "discord", ("discord", "2026-W42"): "discord",
                       ("Demo call center", "2026-W42"): "manual", ("discord", "2026-W41"): "discord"}


def test_varios_lotes_ninguno_y_fuente(cliente, cola):
    sembrar(cliente, cola)
    kpi = lambda q: cliente.get(f"/api/dashboard/kpis{q}", headers=H_OP).json()["total_mensajes"]
    lotes = lambda l: "?lotes=" + json.dumps(l)
    assert kpi("") == 10
    # Unión de dos lotes; repetir un lote no duplica.
    seleccion = [{"origen": "discord", "periodo": "2026-W43", "fuente_ingesta": "discord"},
                 {"origen": "Demo call center", "periodo": "2026-W42", "fuente_ingesta": "manual"}]
    assert kpi(lotes(seleccion)) == 7 and kpi(lotes(seleccion + seleccion[:1])) == 7
    # Ningún lote seleccionado: todo en cero (no el total global).
    assert kpi(lotes([])) == 0
    vacio = cliente.get("/api/mensajes/sentimiento/resumen" + lotes([]), headers=H_OP).json()
    assert (vacio["total"], vacio["analizados"], vacio["estado"]) == (0, 0, "sin_datos")
    assert cliente.get("/api/mensajes" + lotes([]), headers=H_OP).json() == {"items": [], "total": 0}
    assert cliente.get("/api/dashboard/alertas" + lotes([]), headers=H_OP).json()["total"] == 0
    # La fuente separa lotes de igual origen y período; fuente null en un lote = cualquier vía.
    assert kpi("?fuente_ingesta=manual") == 4 and kpi("?fuente_ingesta=discord") == 6
    assert kpi(lotes([{"origen": "discord", "periodo": "2026-W42", "fuente_ingesta": "manual"}])) == 0
    assert kpi(lotes([{"origen": "discord", "periodo": "2026-W42", "fuente_ingesta": None}])) == 2
    mensajes = cliente.get("/api/mensajes" + lotes(seleccion) + "&limit=100", headers=H_OP).json()
    assert mensajes["total"] == 7 and len(mensajes["items"]) == 7
    # Selección inválida: 422 en vez de devolver el global en silencio.
    for malo in ("no-json", json.dumps({"origen": "x"}), json.dumps([{"origen": "x"}]),
                 json.dumps([{"origen": "x", "periodo": "y", "fuente_ingesta": "otra"}])):
        assert cliente.get(f"/api/dashboard/kpis?lotes={malo}", headers=H_OP).status_code == 422
    assert cliente.get("/api/mensajes/sentimiento/resumen?lotes=no-json", headers=H_OP).status_code == 422
