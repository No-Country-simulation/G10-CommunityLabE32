"""Worker en modo gemini con transporte simulado: sin red, sin claves reales."""
from functools import partial

import pytest

from pipelines.communitylab import componentes_gemini
from pipelines.communitylab.gemini_falso import (
    GeminiFalso, configuracion, error, responder_con_senales, tarea_de,
)
from worker import processor
from worker.core import ProcesamientoFallido, Worker
from worker.processor import ProcesadorAislado, _hijo, ejecutar_grafo
from worker.run import validar_configuracion
from worker.tests.test_worker import ColaMemoria, cola, expirar, lote  # noqa: F401 (fixture)


CREAR_ORIGINAL = componentes_gemini.crear_componentes_gemini


def senales_de(entrada):
    tipos = {"logro": "es_logro", "duda": "es_duda", "bloqueo": "es_bloqueo"}
    return {m["id"]: {**{s: tipos.get(m["tipo"]) == s for s in tipos.values()},
                      "tema": "python" if m["tipo"] == "duda" else m["canal"], "relevancia": 0.9}
            for m in entrada["interacciones"]}


@pytest.fixture
def gemini(monkeypatch):
    """Sustituye solo el transporte HTTP: los cinco componentes siguen siendo los reales."""
    estado = {}

    def instalar(responder):
        falso = GeminiFalso(responder=responder)
        estado["falso"] = falso
        monkeypatch.setattr(componentes_gemini, "crear_componentes_gemini",
                            partial(CREAR_ORIGINAL, configuracion(), transporte=falso.transporte))
        return falso
    return instalar


def test_modo_gemini_completa_lote_con_componentes_reales(gemini):
    entrada = lote()
    falso = gemini(responder_con_senales(senales_de(entrada)))
    salida = ejecutar_grafo(entrada, "gemini")
    assert salida["estado"] == "completado_local" and salida["simulado"] is False
    assert [tarea_de(p) for p in falso.peticiones][:2] == ["analizar", "puntuar"]
    assert len(salida["activos_distribucion_generados"]) == 3


def test_error_proveedor_no_se_convierte_en_exito(gemini):
    gemini(lambda p: error(503))
    salida = ejecutar_grafo(lote(), "gemini")
    assert salida["errores"] and salida["estado"] == "error"
    assert salida["activos_distribucion_generados"] == []


def test_codigo_de_ia_llega_al_worker():
    cola_ = ColaMemoria()
    cola_.trabajos = cola_.trabajos[:1]
    salida = {"estado": "error", "simulado": False, "errores": [
        {"nodo": "analizar", "codigo": "fallo_de_nodo", "tipo": "ErrorCuotaIA", "mensaje": "x"}]}
    Worker(cola_, lambda entrada, renovar: salida).ejecutar_uno()
    assert cola_.finales == [("a", "ia_cuota")]


def test_hijo_envia_solo_codigo_controlado(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_MODELOS", "")

    class Conexion:
        enviado = None
        def send(self, valor):
            Conexion.enviado = valor
        def close(self):
            pass
    _hijo(Conexion(), lote(), "gemini")
    assert Conexion.enviado == (False, "ia_configuracion")


def test_hijo_configura_logging_para_las_metricas(monkeypatch):
    llamadas = []
    monkeypatch.setattr(processor.logging, "basicConfig", lambda **kw: llamadas.append(kw))
    monkeypatch.setattr(processor, "ejecutar_grafo", lambda entrada, modo: {"estado": "ok"})

    class Conexion:
        def send(self, valor):
            pass
        def close(self):
            pass
    _hijo(Conexion(), lote(), "gemini")
    assert llamadas and llamadas[0]["level"] == processor.logging.INFO


def hijo_sin_presupuesto(conexion, entrada, modo):
    conexion.send((False, "ia_presupuesto"))
    conexion.close()


def hijo_con_codigo_ajeno(conexion, entrada, modo):
    conexion.send((False, "texto libre del proveedor"))
    conexion.close()


def test_procesador_aislado_traduce_solo_codigos_conocidos():
    with pytest.raises(ProcesamientoFallido, match="ia_presupuesto"):
        ProcesadorAislado("gemini", timeout=30, objetivo=hijo_sin_presupuesto)(lote(), lambda: None)
    with pytest.raises(ProcesamientoFallido, match="^fallo_procesador$"):
        ProcesadorAislado("gemini", timeout=30, objetivo=hijo_con_codigo_ajeno)(lote(), lambda: None)


@pytest.mark.parametrize("modo, entorno, timeout", [
    ("openrouter", {}, 120),
    ("gemini", {"GEMINI_API_KEY": "", "GEMINI_MODELOS": "gemini-a"}, 120),
    ("gemini", {"GEMINI_API_KEY": "k", "GEMINI_MODELOS": ""}, 120),
    ("gemini", {"GEMINI_API_KEY": "k", "GEMINI_MODELOS": "gemini-a", "GEMINI_PRESUPUESTO_SEGUNDOS": "115"}, 120),
])
def test_configuracion_invalida_falla_al_arrancar(monkeypatch, modo, entorno, timeout):
    for clave, valor in entorno.items():
        monkeypatch.setenv(clave, valor)
    with pytest.raises(SystemExit):
        validar_configuracion(modo, timeout)


def test_configuracion_valida(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-ficticia")
    monkeypatch.setenv("GEMINI_MODELOS", "gemini-a,gemini-b")
    monkeypatch.setenv("GEMINI_PRESUPUESTO_SEGUNDOS", "100")
    validar_configuracion("gemini", 120)
    validar_configuracion("simulado", 120)


# --- PostgreSQL real desechable (127.0.0.1:15439/worker_local) ---

def procesar_gemini(entrada, renovar):
    return ejecutar_grafo(entrada, "gemini")


def test_postgres_lote_gemini_terminado_con_activos_validos(cola, gemini):
    entrada = lote()
    gemini(responder_con_senales(senales_de(entrada), copy="Borrador real para curaduría."))
    id_ = cola.encolar(entrada)
    Worker(cola, procesar_gemini).ejecutar_uno()
    trabajo = cola.obtener(id_)
    assert trabajo["estado"] == "terminado" and trabajo["resultado"]["simulado"] is False
    ids = {m["id"] for m in entrada["interacciones"]}
    bloqueo = next(m["id"] for m in entrada["interacciones"] if m["tipo"] == "bloqueo")
    with cola.conectar() as c:
        activos = c.execute("SELECT * FROM activos").fetchall()
    assert {a["formato"] for a in activos} == {"linkedin", "faq", "newsletter"}
    for a in activos:
        assert a["estado"] == "generado" and not a["titulo"].startswith("[SIMULADO]")
        assert a["copy"] == "Borrador real para curaduría."
        assert set(a["fuentes"]) <= ids and bloqueo not in a["fuentes"]


def test_postgres_fallo_gemini_sin_activos_parciales(cola, gemini):
    entrada = lote()
    base = responder_con_senales(senales_de(entrada))
    generados = []

    def responder(p):
        if tarea_de(p) == "generar":
            generados.append(p)
            if len(generados) == 3:
                return error(429, detalles=[{"violations": [{"quotaId": "RequestsPerDay"}]}])
        return base(p)
    gemini(responder)
    id_ = cola.encolar(entrada)
    Worker(cola, procesar_gemini).ejecutar_uno()
    trabajo = cola.obtener(id_)
    assert (trabajo["estado"], trabajo["error_codigo"]) == ("error", "ia_cuota")
    with cola.conectar() as c:
        assert c.execute("SELECT count(*) AS n FROM activos").fetchone()["n"] == 0


def test_postgres_repeticion_no_duplica_activos(cola, gemini):
    entrada = lote()
    gemini(responder_con_senales(senales_de(entrada)))
    id_ = cola.encolar(entrada)
    primero = cola.reservar()
    salida = procesar_gemini(primero.entrada, None)
    expirar(cola, primero)  # el primer intento pierde la reserva tras generar
    segundo = cola.reservar()
    assert segundo.id == id_ and cola.terminar(segundo, procesar_gemini(segundo.entrada, None))
    assert cola.terminar(primero, salida) is False
    with cola.conectar() as c:
        assert c.execute("SELECT count(*) AS n FROM activos").fetchone()["n"] == 3
