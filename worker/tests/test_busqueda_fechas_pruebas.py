"""Búsqueda en Interacciones, fidelidad del texto vigente, fechas en UTC y lotes de prueba ocultos.

PostgreSQL local aislado (127.0.0.1:15439/worker_local); datos y tokens ficticios generados aquí.
"""
import json
import os
import sys
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


def mensaje(c, ident, texto, autor="Persona", canal="general", sentimiento=None):
    c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto, sentimiento_ref)
        VALUES (%s, %s, '2026-10-15T10:00:00+00:00', %s, 'sin_clasificar', %s, %s)""",
              (ident, autor, canal, texto, sentimiento))


def test_busqueda_filtra_antes_de_contar(cliente, cola):
    with cola.conectar() as c:
        mensaje(c, "b-1", "Terminé el reto de SQL con índices", sentimiento="positivo")
        mensaje(c, "b-2", "Duda: ¿cómo hago un JOIN en sql?", sentimiento="neutral")
        mensaje(c, "b-3", "Hoy escuché una canción nueva", autor="Ana López")
        mensaje(c, "b-4", "Avance del 100% en el curso")
        mensaje(c, "b-5", "Sin relación", canal="python_avanzado")
    total = lambda q: cliente.get("/api/mensajes", params={"q": q, "limit": 100}, headers=H_OP).json()["total"]
    assert total("SQL") == 2 and total("sql") == 2                  # sin distinguir mayúsculas
    assert total("cancion") == 1 and total("LOPEZ") == 1             # sin tildes, también en el autor
    assert total("zzzauditoriacommunitylab") == 0
    assert total("100%") == 1 and total("%") == 1                    # % es literal, no comodín
    assert total("_avanzado") == 1 and total("python_") == 1         # _ literal (canal)
    assert total("") == total("   ") == 5                            # vacío = sin filtro
    con_sentimiento = cliente.get("/api/mensajes", params={"q": "sql", "sentimiento": "positivo"}, headers=H_OP).json()
    assert con_sentimiento["total"] == 1 and con_sentimiento["items"][0]["id_mensaje"] == "b-1"
    pagina = cliente.get("/api/mensajes", params={"q": "sql", "limit": 1, "skip": 1}, headers=H_OP).json()
    assert (pagina["total"], len(pagina["items"])) == (2, 1)


def _activo(c, ident, fuente_texto, advertencias):
    mensaje(c, f"f-{ident}", fuente_texto)
    c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version, advertencias_fidelidad,
        fecha_creacion, fecha_actualizacion) VALUES (%s, 'linkedin', 'Logro', 'Ana completó su ejercicio.\n#Python',
        'generado', %s, 1, %s, '2026-10-21 06:51:38', '2026-10-21 06:51:38')""",
              (ident, json.dumps([f"f-{ident}"]), json.dumps(advertencias)))


FALSA = [{"tipo": "posible_atribucion_individual", "detalle": "la fuente describe un logro colectivo"}]
INDIVIDUAL = "Hoy completé individualmente un ejercicio de Python. No fue un logro de todo el equipo."


def test_fechas_de_activos_en_utc_explicito(cliente, cola):
    with cola.conectar() as c:
        _activo(c, "act-fecha", INDIVIDUAL, [])
    detalle = cliente.get("/api/curaduria/activos/act-fecha", headers=H_OP).json()
    assert detalle["fecha_actualizacion"] in ("2026-10-21T06:51:38Z", "2026-10-21T06:51:38+00:00")
    listado = cliente.get("/api/curaduria/activos", headers=H_OP).json()["items"][0]
    assert listado["fecha_creacion"].endswith(("Z", "+00:00"))


def test_editar_recalcula_fidelidad_y_script_corrige_las_guardadas(cliente, cola, monkeypatch, capsys):
    with cola.conectar() as c:
        _activo(c, "act-edit", INDIVIDUAL, FALSA)
        _activo(c, "act-script", INDIVIDUAL, FALSA)
        _activo(c, "act-colectivo", "Organizamos el hackathon con 9 equipos.", [])
    r = cliente.patch("/api/curaduria/activos/act-edit", json={"copy": "Ana terminó su ejercicio de Python.\n#Python"},
                      headers=H_OP).json()
    assert r["advertencias_fidelidad"] == [] and r["version"] == 2
    # Script: primero solo informa; con --aplicar corrige la falsa y detecta la colectiva real.
    from backend.scripts import recalcular_fidelidad
    monkeypatch.setenv("DATABASE_URL", cola.url)
    monkeypatch.setattr(sys, "argv", ["recalcular_fidelidad"])
    recalcular_fidelidad.main()
    assert "con_cambios=2 aplicado=False" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["recalcular_fidelidad", "--aplicar"])
    recalcular_fidelidad.main()
    with cola.conectar() as c:
        guardadas = {f["id_activo"]: [a["tipo"] for a in f["advertencias_fidelidad"]] for f in
                     c.execute("SELECT id_activo, advertencias_fidelidad FROM activos")}
    assert guardadas == {"act-edit": [], "act-script": [], "act-colectivo": ["posible_atribucion_individual"]}


def test_lotes_de_prueba_ocultos_por_defecto(cliente, cola, monkeypatch, capsys):
    with cola.conectar() as c:
        for i in range(1, 6):
            mensaje(c, f"m-{i}", f"Mensaje ficticio {i}")
        trabajos = [("t-real", "CommunityLab", "2026-W43", ["m-1", "m-2", "m-3"], ["m-1"]),
                    ("t-prueba", "CommunityLab-prueba", "2026-W42", ["m-3", "m-4", "m-5"], ["m-4"])]
        for ident, origen, periodo, ids, alertas in trabajos:
            c.execute("""INSERT INTO trabajos_worker (id, entrada, estado, resultado, fuente) VALUES (%s,%s,'terminado',%s,'manual')""",
                      (ident, json.dumps({"origen_comunidad": origen, "periodo_referencia": periodo,
                                          "interacciones": [{"id": i} for i in ids]}),
                       json.dumps({"alertas_internas": [{"id_alerta": f"a-{f}", "fuente": f, "mensaje": "Bloqueo"} for f in alertas],
                                   "activos_distribucion_generados": [{"id_activo": f"g-{ident}"}]})))
        from backend.app.services.ambito import id_activo_curaduria
        for ident in ("t-real", "t-prueba"):
            c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version, fecha_creacion,
                fecha_actualizacion) VALUES (%s, 'linkedin', 'Logro', 'Texto', 'generado', '[]', 1, now(), now())""",
                      (id_activo_curaduria(ident, f"g-{ident}"),))
    # Marcar con el script (y listar).
    from backend.scripts import marcar_prueba
    monkeypatch.setenv("DATABASE_URL", cola.url)
    monkeypatch.setattr(sys, "argv", ["marcar_prueba", "--origen", "CommunityLab-prueba", "--periodo", "2026-W42"])
    marcar_prueba.main()
    assert "marcados como prueba: 1 trabajos" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["marcar_prueba", "--listar"])
    marcar_prueba.main()
    assert "CommunityLab-prueba | 2026-W42 | manual | trabajos=1 de_prueba=1" in capsys.readouterr().out

    g = lambda ruta, **p: cliente.get(ruta, params=p, headers=H_OP).json()
    kpi, kpi_todo = g("/api/dashboard/kpis"), g("/api/dashboard/kpis", incluir_pruebas=True)
    # m-4 y m-5 solo están en el lote de prueba; m-3 también en el real, así que se ve.
    assert (kpi["total_mensajes"], kpi_todo["total_mensajes"]) == (3, 5)
    assert (kpi["alertas_internas"], kpi_todo["alertas_internas"]) == (1, 2)
    assert (kpi["activos_generados"], kpi_todo["activos_generados"]) == (1, 2)
    assert {m["id_mensaje"] for m in g("/api/mensajes", limit=100)["items"]} == {"m-1", "m-2", "m-3"}
    assert g("/api/mensajes", limit=100, incluir_pruebas=True)["total"] == 5
    assert g("/api/mensajes/sentimiento/resumen")["total"] == 3
    assert [a["origen"] for a in g("/api/dashboard/ambitos")["items"]] == ["CommunityLab"]
    con_pruebas = {a["origen"]: a["es_prueba"] for a in g("/api/dashboard/ambitos", incluir_pruebas=True)["items"]}
    assert con_pruebas == {"CommunityLab": False, "CommunityLab-prueba": True}
    assert g("/api/dashboard/alertas")["total"] == 1 and g("/api/dashboard/alertas", incluir_pruebas=True)["total"] == 2
    assert g("/api/curaduria/activos")["total"] == 1 and g("/api/curaduria/activos", incluir_pruebas=True)["total"] == 2
    # Desmarcar lo vuelve a mostrar.
    monkeypatch.setattr(sys, "argv", ["marcar_prueba", "--origen", "CommunityLab-prueba", "--periodo", "2026-W42", "--quitar"])
    marcar_prueba.main()
    assert g("/api/dashboard/kpis")["total_mensajes"] == 5
