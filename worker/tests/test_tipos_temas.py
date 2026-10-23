"""Tipo de participación y tema por mensaje: se guardan tras el análisis y alimentan Analítica.

PostgreSQL local aislado (127.0.0.1:15439/worker_local). Gemini con transporte falso: sin red ni claves.
"""
import json
import os
import sys
from urllib.parse import urlparse

import pytest

from worker.core import Worker

OPERADOR = "operador-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}
# Señales que «devuelve» el modelo falso según el texto del mensaje.
SENALES = {
    "logro": {"es_logro": True, "es_duda": False, "es_bloqueo": False, "tema": "Certificación OCI"},
    "duda": {"es_logro": False, "es_duda": True, "es_bloqueo": False, "tema": "  LangGraph   reintentos "},
    "bloqueo": {"es_logro": False, "es_duda": True, "es_bloqueo": True, "tema": "Base de datos"},
    "saludo": {"es_logro": False, "es_duda": False, "es_bloqueo": False, "tema": "certificación oci"},
    "archivo": {"es_logro": True, "es_duda": False, "es_bloqueo": False, "tema": "testimonio"},
}


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


def procesar(cola, entrada):
    from pipelines.communitylab import ejecutar_lote
    from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
    from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, ok, tarea_de

    def responder(p):
        items = json.loads(p["cuerpo"]["contents"][0]["parts"][0]["text"])
        if tarea_de(p) == "analizar":
            return ok({"resultados": [{"id": m["id"], **SENALES[m["texto"].split()[0]], "sentimiento": "neutral"}
                                      for m in items]})
        return ok({"resultados": [{"id": m["id"], "relevancia": 0.1} for m in items]})   # sin generación

    cola.encolar(entrada)
    falso = GeminiFalso(responder=responder)
    worker = Worker(cola, lambda e, renovar: ejecutar_lote(e, crear_componentes_gemini(configuracion(), transporte=falso.transporte)))
    while worker.ejecutar_uno():
        pass


def lote(textos, tipos=None):
    return {"origen_comunidad": "discord", "periodo_referencia": "2026-W43", "cierre_periodo": False,
            "interacciones": [{"id": f"m-{i}", "autor": f"a-{i}", "canal": "general", "fecha": "2026-10-20T10:00:00Z",
                               "texto": t, **({"tipo": tipos[i]} if tipos and tipos.get(i) else {})}
                              for i, t in enumerate(textos)]}


def fila(cola, ident):
    with cola.conectar() as c:
        return c.execute("SELECT tipo, tema_ref FROM mensajes WHERE id_mensaje=%s", (ident,)).fetchone()


def test_tipo_y_tema_se_guardan_sin_pisar_el_tipo_de_origen(cliente, cola):
    textos = ["logro completé OCI", "duda cómo reintento", "bloqueo no puedo avanzar", "saludo hola", "archivo dato"]
    procesar(cola, lote(textos, tipos={4: "testimonio"}))
    # El análisis entrega el tema en minúsculas y con espacios normalizados.
    assert (fila(cola, "m-0")["tipo"], fila(cola, "m-0")["tema_ref"]) == ("logro", "certificación oci")
    assert (fila(cola, "m-1")["tipo"], fila(cola, "m-1")["tema_ref"]) == ("duda", "langgraph reintentos")
    assert fila(cola, "m-2")["tipo"] == "bloqueo"                       # bloqueo gana a duda
    assert fila(cola, "m-3")["tipo"] == "comentario"
    archivo = fila(cola, "m-4")
    assert (archivo["tipo"], archivo["tema_ref"]) == ("testimonio", "testimonio")   # el tipo del archivo se conserva
    with cola.conectar() as c:
        persistencia = c.execute("SELECT resultado->'persistencia' p FROM trabajos_worker").fetchone()["p"]
    assert persistencia["clasificaciones"] == 5
    # La API los expone y Analítica los agrega.
    items = {m["id_mensaje"]: m for m in cliente.get("/api/mensajes?limit=10", headers=H_OP).json()["items"]}
    assert items["m-1"]["tipo"] == "duda" and items["m-1"]["tema_ref"] == "langgraph reintentos"
    kpi = cliente.get("/api/dashboard/kpis", headers=H_OP).json()
    assert kpi["mensajes_por_tipo"] == {"logro": 1, "duda": 1, "bloqueo": 1, "comentario": 1, "testimonio": 1}
    # m-0 y m-3 comparten tema: cuenta como uno con 2 mensajes.
    assert kpi["temas_principales"][0] == {"tema": "certificación oci", "cantidad": 2}
    assert len(kpi["temas_principales"]) == 4


def test_analitica_agrupa_variantes_del_mismo_tema(cliente, cola):
    procesar(cola, lote(["logro a", "saludo b", "duda c"]))
    # Mismo asunto escrito distinto en lotes distintos (con y sin tildes, con y sin «del»).
    with cola.conectar() as c:
        for ident, tema in (("m-0", "documentacion curso"), ("m-1", "documentación del curso"), ("m-2", "langgraph")):
            c.execute("UPDATE mensajes SET tema_ref=%s WHERE id_mensaje=%s", (tema, ident))
    kpi = cliente.get("/api/dashboard/kpis", headers=H_OP).json()
    assert kpi["temas_principales"] == [{"tema": "documentación del curso", "cantidad": 2},
                                        {"tema": "langgraph", "cantidad": 1}]


def test_reproceso_no_pisa_lo_ya_clasificado(cola):
    procesar(cola, lote(["logro primero"]))
    with cola.conectar() as c:
        c.execute("UPDATE mensajes SET tema_ref='Tema editado' WHERE id_mensaje='m-0'")
    entrada = lote(["logro primero"])
    entrada["cierre_periodo"] = True                                   # otro trabajo, mismo mensaje
    procesar(cola, entrada)
    assert (fila(cola, "m-0")["tipo"], fila(cola, "m-0")["tema_ref"]) == ("logro", "Tema editado")


def test_script_completa_mensajes_ya_procesados_desde_el_enrutamiento(cola, monkeypatch, capsys):
    with cola.conectar() as c:
        for i in range(6):
            c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                VALUES (%s, 'a', '2026-10-20T10:00:00Z', 'general', %s, 'Mensaje ficticio')""",
                      (f"v-{i}", "pregunta_tecnica" if i == 5 else "sin_clasificar"))
        enrutamiento = {"decisiones": [
            {"ruta": "logro", "fuentes": ["v-0"], "motivo": "Logro relevante"},
            {"ruta": "bloqueo", "fuentes": ["v-1"], "motivo": "Bloqueo detectado"},
            {"ruta": "dudas", "fuentes": ["v-1", "v-2", "v-5"], "motivo": "Duda recurrente sobre 'Docker' entre 2 autores distintos."},
            {"ruta": "periodo", "fuentes": ["v-0", "v-1", "v-2"], "motivo": "Cierre"}],
            "sin_ruta": [{"fuente": "v-3", "motivo": "Duda sin recurrencia suficiente y sin otra ruta aplicable."},
                         {"fuente": "v-4", "motivo": "Relevancia inferior al umbral configurado."}]}
        c.execute("INSERT INTO trabajos_worker (id, entrada, estado, resultado) VALUES ('t-viejo', '{}', 'terminado', %s)",
                  (json.dumps({"simulado": False, "enrutamiento": enrutamiento}),))
        c.execute("INSERT INTO trabajos_worker (id, entrada, estado, resultado) VALUES ('t-sim', '{}', 'terminado', %s)",
                  (json.dumps({"simulado": True, "enrutamiento": {"decisiones": [{"ruta": "logro", "fuentes": ["v-4"]}]}}),))
    from backend.scripts import reclasificar_mensajes
    monkeypatch.setenv("DATABASE_URL", cola.url)
    monkeypatch.setattr(sys, "argv", ["reclasificar_mensajes"])
    reclasificar_mensajes.main()
    assert "con_cambios=5 aplicado=False" in capsys.readouterr().out and fila(cola, "v-0")["tipo"] == "sin_clasificar"
    monkeypatch.setattr(sys, "argv", ["reclasificar_mensajes", "--aplicar"])
    reclasificar_mensajes.main()
    resultado = {f"v-{i}": tuple(fila(cola, f"v-{i}").values()) for i in range(6)}
    assert resultado == {
        "v-0": ("logro", None),
        "v-1": ("bloqueo", "Docker"),            # bloqueo gana; conserva el tema de la duda
        "v-2": ("duda", "Docker"),
        "v-3": ("duda", None),
        "v-4": ("sin_clasificar", None),         # el enrutamiento no lo distingue; el simulado no cuenta
        "v-5": ("pregunta_tecnica", "Docker"),   # el tipo de origen se conserva; el tema se completa
    }


def test_clasificacion_precedencia_y_tema_acotado():
    from pipelines.communitylab.grafo import clasificacion_de
    assert clasificacion_de({"es_bloqueo": True, "es_duda": True, "es_logro": True, "tema": "a"})["tipo"] == "bloqueo"
    assert clasificacion_de({"es_duda": True, "es_logro": True, "tema": "a"})["tipo"] == "duda"
    assert clasificacion_de({"es_logro": True, "tema": ""}) == {"tipo": "logro", "tema": None}
    assert clasificacion_de({"tema": "  dos   palabras "}) == {"tipo": "comentario", "tema": "dos palabras"}
    assert len(clasificacion_de({"tema": "x" * 150})["tema"]) == 100
