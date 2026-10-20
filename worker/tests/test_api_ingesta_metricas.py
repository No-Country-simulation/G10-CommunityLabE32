"""Contratos HTTP reales de ingesta, idempotencia, métricas y curaduría sobre PostgreSQL local.

Usan la base aislada de pruebas (127.0.0.1:15439/worker_local) y el modo simulado del
grafo: no llaman a Gemini ni a Discord. Los datos son ficticios.
"""
import copy
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest

from worker.core import Worker
from worker.processor import ejecutar_grafo

DATASET = json.loads((Path(__file__).resolve().parents[2] / "pipelines/communitylab/ejemplos/"
                      "dataset_demo_20_personas.json").read_text(encoding="utf-8"))


@pytest.fixture
def cola():
    from worker.store_postgres import ColaPostgres
    url = os.environ.get("WORKER_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL local de pruebas")
    parsed = urlparse(url)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/worker_local"
    q = ColaPostgres(url, lease=2, max_intentos=2)
    with q.conectar() as c:
        c.execute("TRUNCATE trabajos_worker, activos, mensajes")
    return q


@pytest.fixture
def cliente(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    # Pruebas funcionales de la interfaz: actúan como operador (el rechazo sin credencial se prueba
    # en test_acceso_seguridad.py). El token es ficticio y propio de cada ejecución.
    token = "operador-prueba-" + os.urandom(6).hex()
    monkeypatch.setenv("OPERADOR_TOKEN", token)
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    # Cada TestClient usa su propio event loop: no reutilizar conexiones asyncpg de otra prueba.
    engine.sync_engine.dispose(close=False)
    with TestClient(app, headers={"X-Operador-Token": token}) as c:
        yield c


def subir(cliente, contenido, nombre="lote.json", origen="CommunityLab", periodo="2026-W43", cierre=False):
    datos = contenido if isinstance(contenido, bytes) else json.dumps(contenido, ensure_ascii=False).encode()
    return cliente.post("/api/mensajes/procesamientos", files={"file": (nombre, io.BytesIO(datos))},
                        data={"origen_comunidad": origen, "periodo_referencia": periodo,
                              "cierre_periodo": str(cierre).lower()})


def procesar_todo(cola):
    worker = Worker(cola, lambda entrada, renovar: ejecutar_grafo(entrada, "simulado"))
    while worker.ejecutar_uno():
        pass


def contar(cola, tabla):
    with cola.conectar() as c:
        return c.execute(f"SELECT count(*) AS n FROM {tabla}").fetchone()["n"]


# --- Ingesta y validación -------------------------------------------------------------

def test_subida_valida_reenvio_reutiliza_y_metadatos_del_formulario_prevalecen(cliente, cola):
    archivo = {**DATASET, "origen_comunidad": "otro", "periodo_referencia": "Semana 2"}
    a = subir(cliente, archivo)
    assert a.status_code == 202, a.text
    cuerpo = a.json()
    assert (cuerpo["reutilizado"], cuerpo["interacciones"], cuerpo["estado"]) == (False, 20, "recibido")
    assert set(cuerpo["metadatos_archivo_ignorados"]) == {"origen_comunidad", "periodo_referencia", "cierre_periodo"}
    b = subir(cliente, archivo)
    assert (b.json()["procesamiento_id"], b.json()["reutilizado"]) == (cuerpo["procesamiento_id"], True)
    procesar_todo(cola)
    c = subir(cliente, archivo)  # Reenvío de un trabajo ya terminado: devuelve su estado real.
    assert (c.json()["reutilizado"], c.json()["estado"]) == (True, "terminado")
    with cola.conectar() as conexion:
        entrada = conexion.execute("SELECT entrada FROM trabajos_worker").fetchone()["entrada"]
    assert (entrada["origen_comunidad"], entrada["periodo_referencia"]) == ("CommunityLab", "2026-W43")


def test_otros_metadatos_crean_otro_lote_sin_duplicar_mensajes(cliente, cola):
    a = subir(cliente, DATASET, periodo="2026-W43")
    b = subir(cliente, DATASET, periodo="2026-W44")
    assert a.json()["procesamiento_id"] != b.json()["procesamiento_id"]
    assert contar(cola, "trabajos_worker") == 2
    assert contar(cola, "mensajes") == 20  # Deduplicación por ID de mensaje, no por lote.


def test_errores_de_validacion_ubicados_y_sin_contenido(cliente, cola):
    registros = copy.deepcopy(DATASET["interacciones"][:3])
    registros[0]["fecha"] = "19/10/2026"
    del registros[2]["autor"]
    r = subir(cliente, registros)
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "archivo_invalido"
    ubicaciones = {(e["registro"], e["campo"]) for e in detalle["errores"]}
    assert ubicaciones == {(1, "fecha"), (3, "autor")}
    assert {e["motivo"] for e in detalle["errores"] if e["campo"] == "autor"} == {"campo obligatorio ausente"}
    assert "500 registros" in detalle["ayuda"]
    assert registros[1]["texto"] not in r.text and "19/10/2026" not in r.text
    assert contar(cola, "trabajos_worker") == 0 and contar(cola, "mensajes") == 0


def test_limites_formato_y_duplicados_en_archivo(cliente, cola):
    muchos = [{"id": f"x-{i}", "autor": "a", "canal": "c", "fecha": "2026-10-19T10:00:00Z", "texto": f"t{i}"}
              for i in range(501)]
    assert subir(cliente, muchos).json()["detail"]["codigo"] == "demasiados_registros"
    grande = subir(cliente, b"[" + b" " * (5 * 1024 * 1024) + b"]")
    assert (grande.status_code, grande.json()["detail"]["codigo"]) == (413, "archivo_demasiado_grande")
    assert subir(cliente, b"hola", nombre="lote.txt").json()["detail"]["codigo"] == "formato_no_soportado"
    assert subir(cliente, b"{mal").json()["detail"]["codigo"] == "archivo_malformado"
    repetido = copy.deepcopy(DATASET["interacciones"][:2])
    repetido.append({**repetido[0], "texto": "otro texto"})
    errores = subir(cliente, repetido).json()["detail"]["errores"]
    assert errores == [{"registro": 3, "id": "demo-01", "campo": "id",
                        "motivo": "ID repetido con contenido distinto (registro 1)"}]
    identicos = DATASET["interacciones"][:2] + DATASET["interacciones"][:1]
    ok = subir(cliente, identicos)
    assert (ok.status_code, ok.json()["registros_duplicados_omitidos"], ok.json()["interacciones"]) == (202, 1, 2)


def test_csv_con_tipo_vacio_se_acepta(cliente):
    csv = ("id,autor,canal,fecha,texto,tipo\n"
           "c-1,Ana,general,2026-10-19T10:00:00Z,Hola a todos,\n"
           "c-2,Luis,python,2026-10-19T11:00:00Z,¿Cómo uso pytest?,duda\n").encode()
    r = subir(cliente, csv, nombre="lote.csv")
    assert r.status_code == 202, r.text


def test_conflictos_de_mensaje_e_idempotencia(cliente):
    assert subir(cliente, DATASET).status_code == 202
    alterado = copy.deepcopy(DATASET)
    alterado["interacciones"][0]["texto"] = "Texto distinto con el mismo ID"
    r = subir(cliente, alterado, periodo="otro")
    assert (r.status_code, r.json()["detail"]["codigo"]) == (409, "conflicto_mensaje")
    assert r.json()["detail"]["errores"][0]["id"] == "demo-01"

    lote = {"origen_comunidad": "api", "periodo_referencia": "p1", "interacciones": [
        {"id": f"api-{uuid4().hex}", "autor": "Ana", "canal": "c", "fecha": "2026-10-19T10:00:00Z", "texto": "hola"}]}
    cabecera = {"Idempotency-Key": "clave-prueba-" + uuid4().hex}
    a = cliente.post("/api/v1/trabajos", json=lote, headers=cabecera)
    b = cliente.post("/api/v1/trabajos", json=lote, headers=cabecera)
    assert (a.json()["reutilizado"], b.json()["reutilizado"]) == (False, True)
    otro = {**lote, "periodo_referencia": "p2"}
    c = cliente.post("/api/v1/trabajos", json=otro, headers=cabecera)
    assert (c.status_code, c.json()["detail"]["codigo"]) == (409, "conflicto_idempotencia")


# --- Métricas ---------------------------------------------------------------------------

def lote_con_bloqueo(periodo):
    return {"origen_comunidad": "CommunityLab", "periodo_referencia": periodo, "cierre_periodo": False,
            "interacciones": [
                {"id": "m-logro", "autor": "Ana", "canal": "logros", "fecha": "2026-10-19T10:00:00Z",
                 "texto": "Aprobé la certificación de Python.", "tipo": "logro"},
                {"id": "m-bloqueo", "autor": "Luis", "canal": "soporte", "fecha": "2026-10-19T11:00:00Z",
                 "texto": "Llevo días bloqueado con el despliegue.", "tipo": "bloqueo"}]}


def test_kpis_sin_doble_conteo_y_con_semantica_explicita(cliente, cola):
    cola.encolar(lote_con_bloqueo("2026-W43"))
    cola.encolar(lote_con_bloqueo("2026-W43"))  # Reenvío idéntico: mismo trabajo.
    cola.encolar(lote_con_bloqueo("2026-W44"))  # Mismos mensajes, otro período: otro trabajo.
    with cola.conectar() as c:  # Mensaje histórico con la palabra "error" pero sin alerta real.
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                     VALUES ('hist-1','Eva','2023-02-01T10:00:00Z','#dudas','pregunta_tecnica',
                             'Me sale un error al compilar')""")
    procesar_todo(cola)
    k = cliente.get("/api/dashboard/kpis").json()
    assert k["total_mensajes"] == 3
    assert k["alertas_internas"] == 1  # Un solo mensaje con bloqueo real.
    assert k["alertas_registradas"] == 2  # Una por cada lote distinto que lo incluyó.
    assert k["sentimiento"] == {"estado": "sin_datos", "clasificados": 0, "sin_clasificar": 3}
    assert k["publicados"] is None and k["publicacion_externa"] == "no_implementada"
    assert k["borradores_pendientes"] == k["activos_generados"] > 0
    with cola.conectar() as c:
        c.execute("UPDATE activos SET estado='aprobado' WHERE id_activo=(SELECT min(id_activo) FROM activos)")
    k2 = cliente.get("/api/dashboard/kpis").json()
    assert (k2["activos_aprobados"], k2["borradores_pendientes"]) == (1, k["borradores_pendientes"] - 1)

    w43 = cliente.get("/api/dashboard/kpis", params={"origen": "CommunityLab", "periodo": "2026-W43"}).json()
    assert (w43["total_mensajes"], w43["alertas_internas"], w43["alertas_registradas"]) == (2, 1, 1)
    assert w43["activos_generados"] == k["activos_generados"] // 2
    vacio = cliente.get("/api/dashboard/kpis", params={"origen": "inexistente"}).json()
    assert (vacio["total_mensajes"], vacio["activos_generados"], vacio["alertas_internas"]) == (0, 0, 0)
    ambitos = cliente.get("/api/dashboard/ambitos").json()["items"]
    assert {(a["origen"], a["periodo"]) for a in ambitos} == {("CommunityLab", "2026-W43"), ("CommunityLab", "2026-W44")}
    mensajes = cliente.get("/api/mensajes", params={"origen": "CommunityLab", "periodo": "2026-W44"}).json()
    assert mensajes["total"] == 2


# --- Resultados, diagnóstico y curaduría -----------------------------------------------

def test_resultado_aclara_persistencia_y_curaduria_filtra_por_trabajo(cliente, cola):
    primero = cola.encolar(lote_con_bloqueo("2026-W43"))
    cola.encolar(lote_con_bloqueo("2026-W44"))
    procesar_todo(cola)
    trabajo = cliente.get(f"/api/v1/trabajos/{primero}").json()
    assert trabajo["resultado"]["persistencia"]["postgres"] == "guardado"
    assert trabajo["resultado"]["almacenamiento"]["capa"] == "objetos_externos_oci"
    propios = cliente.get("/api/curaduria/activos", params={"trabajo": primero}).json()
    todos = cliente.get("/api/curaduria/activos").json()
    assert 0 < propios["total"] < todos["total"]
    esperados = {a["id_activo_curaduria"] for a in trabajo["resultado"]["activos_distribucion_generados"]}
    assert {a["id_activo"] for a in propios["items"]} == esperados
    detalle = cliente.get(f"/api/curaduria/activos/{propios['items'][0]['id_activo']}").json()
    assert isinstance(detalle["advertencias_fidelidad"], list)
    assert "m-bloqueo" not in {f for a in todos["items"] for f in a["fuentes"]}


MARCADOR = "CONTENIDO_PRIVADO_FICTICIO_7429"


def test_trabajo_con_error_expone_solo_diagnostico_de_catalogo(cliente, cola):
    identificador = cola.encolar(lote_con_bloqueo("2026-W43"))
    hostil = {"http": 400, "categoria": MARCADOR, "estado_proveedor": MARCADOR, "razon": MARCADOR,
              "campos": [f"contents[0].{MARCADOR}", "generation_config"],
              "detalle": f"Invalid input: {MARCADOR} AIzaSyFICTICIA0123456789",
              "peticion": {"items_esperados": 2, "otro": MARCADOR}, "extra": MARCADOR}
    salida_error = {"estado": "error", "errores": [{"tipo": "ErrorConfiguracionIA", "diagnostico": hostil}]}
    Worker(cola, lambda entrada, renovar: salida_error).ejecutar_uno()
    with cola.conectar() as c:  # Lo guardado por el worker
        guardado = c.execute("SELECT resultado FROM trabajos_worker WHERE id=%s", (identificador,)).fetchone()["resultado"]
    respuesta = cliente.get(f"/api/v1/trabajos/{identificador}")
    for texto in (json.dumps(guardado, ensure_ascii=False), respuesta.text):
        assert MARCADOR not in texto and "AIza" not in texto
    trabajo = respuesta.json()
    assert (trabajo["estado"], trabajo["error_codigo"]) == ("error", "ia_configuracion")
    assert trabajo["resultado"]["diagnostico"] == {
        "http": 400, "categoria": "peticion_rechazada", "estado_proveedor": "OTRO", "razon": "otra",
        "campos": ["contents[].*", "generation_config"], "detalle": "El proveedor rechazó la petición.",
        "peticion": {"items_esperados": 2}}


def test_api_normaliza_diagnosticos_guardados_por_versiones_anteriores(cliente, cola):
    identificador = cola.encolar(lote_con_bloqueo("2026-W43"))
    with cola.conectar() as c:  # Fila con el formato anterior (detalle libre del proveedor)
        c.execute("""UPDATE trabajos_worker SET estado='error', error_codigo='ia_configuracion',
                     resultado=%s WHERE id=%s""",
                  (json.dumps({"diagnostico": {"http": 400, "detalle": f"Invalid input: {MARCADOR}",
                                               "razon": MARCADOR}}), identificador))
    respuesta = cliente.get(f"/api/v1/trabajos/{identificador}")
    assert MARCADOR not in respuesta.text
    assert respuesta.json()["resultado"]["diagnostico"]["categoria"] == "peticion_rechazada"
