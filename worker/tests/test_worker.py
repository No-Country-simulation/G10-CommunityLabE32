import copy
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from worker.core import Worker, ProcesamientoFallido, ReservaPerdida, Trabajo
from worker.processor import ProcesadorAislado, ejecutar_grafo


def lote():
    prefijo = uuid4().hex
    return {"origen_comunidad": "prueba_local", "periodo_referencia": "Semana 2",
            "cierre_periodo": True, "interacciones": [
                {"id": prefijo + str(i), "autor": f"persona-{i}", "canal": canal,
                 "fecha": "2026-10-02T12:00:00Z", "texto": texto, "tipo": tipo}
                for i, (tipo, canal, texto) in enumerate([
                    ("logro", "logros", "Conseguí mi primer empleo."),
                    ("duda", "python", "¿Cómo usar Python?"),
                    ("duda", "python", "También necesito aprender Python."),
                    ("bloqueo", "soporte", "Tengo un bloqueo; revisar internamente."),
                ])]}


class ColaMemoria:
    def __init__(self):
        self.trabajos = [Trabajo("a", "token-a", lote()), Trabajo("b", "token-b", lote())]
        self.finales = []
    def reservar(self):
        return self.trabajos.pop(0) if self.trabajos else None
    def renovar(self, trabajo):
        return True
    def terminar(self, trabajo, resultado):
        self.finales.append((trabajo.id, "terminado"))
        return True
    def fallar(self, trabajo, codigo):
        self.finales.append((trabajo.id, codigo))
        return True


def test_un_error_no_detiene_siguiente_lote():
    cola = ColaMemoria()
    n = 0
    def procesar(entrada, renovar):
        nonlocal n
        n += 1
        if n == 1:
            raise RuntimeError("secreto-no-debe-registrarse")
        return ejecutar_grafo(entrada, "simulado")
    w = Worker(cola, procesar)
    assert w.ejecutar_uno() and w.ejecutar_uno()
    assert not w.ejecutar_uno()
    assert cola.finales == [("a", "fallo_procesador"), ("b", "terminado")]


def test_resultado_error_no_se_marca_terminado():
    cola = ColaMemoria()
    Worker(cola, lambda *_: {"estado": "error"}).ejecutar_uno()
    assert cola.finales == [("a", "fallo_grafo")]


def test_reserva_perdida_no_sobrescribe_resultado():
    cola = ColaMemoria()
    cola.renovar = lambda *_: False
    def procesar(entrada, renovar):
        renovar()
    Worker(cola, procesar).ejecutar_uno()
    assert cola.finales == []


def bloqueado(conexion, entrada, modo):
    time.sleep(10)


def test_timeout_termina_proceso_hijo():
    inicio = time.monotonic()
    with pytest.raises(ProcesamientoFallido, match="timeout"):
        ProcesadorAislado("simulado", timeout=0.4, objetivo=bloqueado)(lote(), lambda: None)
    assert time.monotonic() - inicio < 5


def test_procesador_aislado_renueva_reserva():
    renovaciones = []
    salida = ProcesadorAislado("simulado", renovar_cada=0.01)(lote(), lambda: renovaciones.append(1))
    assert salida["simulado"] is True
    assert renovaciones


def test_cuatro_rutas_y_bloqueo_excluido():
    entrada = lote()
    salida = ejecutar_grafo(entrada, "simulado")
    assert salida["errores"] == []
    assert {d["ruta"] for d in salida["enrutamiento"]["decisiones"]} == {"logro", "dudas", "periodo", "bloqueo"}
    bloqueo = entrada["interacciones"][3]["id"]
    assert salida["alertas_internas"][0]["fuente"] == bloqueo
    assert all(bloqueo not in a["fuentes"] for a in salida["activos_distribucion_generados"])


@pytest.fixture
def cola():
    from worker.store_postgres import ColaPostgres
    url = os.environ.get("WORKER_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL local de pruebas")
    # Impide borrar tablas de otra base de datos por un error de configuración.
    from urllib.parse import urlparse
    parsed = urlparse(url)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/worker_local"
    q = ColaPostgres(url, lease=2, max_intentos=2)
    with q.conectar() as c:
        c.execute("TRUNCATE trabajos_worker, activos, mensajes")
    return q


def test_postgres_flujo_persistencia_y_curaduria(cola):
    entrada = lote()
    id_ = cola.encolar(entrada)
    assert cola.obtener(id_)["estado"] == "recibido"
    Worker(cola, lambda entrada, renovar: ejecutar_grafo(entrada, "simulado")).ejecutar_uno()
    resultado = cola.obtener(id_)
    assert resultado["estado"] == "terminado"
    assert resultado["historial"] == ["recibido", "procesando", "terminado"]
    assert resultado["resultado"]["simulado"] is True
    with cola.conectar() as c:
        activos = c.execute("SELECT * FROM activos").fetchall()
    assert len(activos) == 3
    assert {a["formato"] for a in activos} == {"linkedin", "faq", "newsletter"}
    assert all(a["estado"] == "generado" and a["titulo"].startswith("[SIMULADO]") for a in activos)


def test_dos_workers_no_reservan_mismo_trabajo(cola):
    cola.encolar(lote())
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: cola.reservar(), range(2)))
    assert sum(r is not None for r in resultados) == 1


def expirar(cola, trabajo):
    with cola.conectar() as c:
        c.execute("UPDATE trabajos_worker SET vence=clock_timestamp()-interval '1 second' WHERE id=%s", (trabajo.id,))


def test_reinicio_recuperacion_y_token_viejo(cola):
    id_ = cola.encolar(lote())
    viejo = cola.reservar()
    expirar(cola, viejo)
    nuevo = cola.reservar()
    assert viejo.id == nuevo.id and viejo.token != nuevo.token
    assert cola.renovar(viejo) is False
    assert cola.fallar(viejo, "fallo_procesador") is False
    salida = ejecutar_grafo(nuevo.entrada, "simulado")
    assert cola.terminar(viejo, salida) is False
    assert cola.terminar(nuevo, salida) is True
    assert cola.terminar(nuevo, salida) is False
    assert cola.obtener(id_)["intentos"] == 2


def test_reservas_agotadas_no_bucle_infinito(cola):
    id_ = cola.encolar(lote())
    for _ in range(2):
        t = cola.reservar()
        expirar(cola, t)
    assert cola.reservar() is None
    assert cola.obtener(id_)["error_codigo"] == "reserva_agotada"


def test_reserva_expirada_no_acepta_resultado(cola):
    cola.encolar(lote())
    t = cola.reservar()
    salida = ejecutar_grafo(t.entrada, "simulado")
    expirar(cola, t)
    assert cola.terminar(t, salida) is False


def test_persistencia_atomica_sin_activos_parciales(cola):
    id_ = cola.encolar(lote())
    t = cola.reservar()
    salida = ejecutar_grafo(t.entrada, "simulado")
    salida["activos_distribucion_generados"][-1]["formato"] = "invalido"
    with pytest.raises(KeyError):
        cola.terminar(t, salida)
    with cola.conectar() as c:
        assert c.execute("SELECT count(*) AS n FROM activos").fetchone()["n"] == 0
    assert cola.obtener(id_)["estado"] == "procesando"


def test_rechaza_colision_de_id_sin_sobrescribir_fuente(cola):
    entrada = lote()
    cola.encolar(entrada)
    entrada["interacciones"][0]["texto"] = "Texto cambiado"
    with pytest.raises(ValueError, match="contenido diferente"):
        cola.encolar(entrada)


def test_fallo_y_siguiente_en_postgres(cola):
    malo, bueno = cola.encolar(lote()), cola.encolar(lote())
    def procesar(entrada, renovar):
        if cola.obtener(malo)["estado"] == "procesando":
            raise ProcesamientoFallido("timeout")
        return ejecutar_grafo(entrada, "simulado")
    w = Worker(cola, procesar)
    w.ejecutar_uno()
    w.ejecutar_uno()
    assert cola.obtener(malo)["estado"] == "error"
    assert cola.obtener(bueno)["estado"] == "terminado"


def test_api_registra_consulta_y_rechaza_archivo_invalido(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as cliente:
        respuesta = cliente.post("/api/v1/trabajos", json=lote())
        assert respuesta.status_code == 202, respuesta.text
        assert cliente.get(respuesta.json()["consulta"]).json()["estado"] == "recibido"
        assert cliente.get("/api/v1/trabajos/inexistente").status_code == 404
        for contenido in (b"{mal", b"42", b"[{}]"):
            r = cliente.post("/api/mensajes/procesamientos", files={"file": ("datos.json", contenido)},
                             data={"origen_comunidad": "prueba", "periodo_referencia": "S2"})
            assert r.status_code == 422, r.text


@pytest.mark.parametrize("campo", ["fecha", "canal", "autor", "texto", "id"])
def test_campos_vacios_no_aceptados(cola, campo):
    entrada = lote()
    entrada["interacciones"][0][campo] = ""
    with pytest.raises(ValueError):
        cola.encolar(entrada)
