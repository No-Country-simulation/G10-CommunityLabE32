import os
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from pipelines.communitylab.grafo import construir_grafo, ejecutar_lote, preparar_entrada, ContratoInvalido
from pipelines.communitylab.simulados import crear_componentes
from pipelines.communitylab.router_base import Configuracion

BASE = Path(__file__).resolve().parents[1]


class PruebasGrafo(unittest.TestCase):
    def setUp(self):
        self.entrada = json.loads((BASE / "ejemplos/entrada.json").read_text(encoding="utf-8"))
        self.señales = json.loads((BASE / "ejemplos/senales_simuladas.json").read_text(encoding="utf-8"))
        self.componentes = crear_componentes(self.señales)
        # Cualquier intento de conexión durante una prueba provoca un fallo.
        self.red = patch.object(socket.socket, "connect", side_effect=AssertionError("RED PROHIBIDA"))
        self.conectar = self.red.start()
        self.addCleanup(self.red.stop)
        self.addCleanup(lambda: self.conectar.assert_not_called())

    def ejecutar(self, entrada=None, componentes=None, cfg=None):
        return ejecutar_lote(self.entrada if entrada is None else entrada,
                            self.componentes if componentes is None else componentes, cfg)

    def test_cuatro_rutas_y_consolidacion(self):
        s = self.ejecutar()
        self.assertEqual(s["estado"], "completado_local")
        self.assertTrue(s["simulado"])
        self.assertEqual(len(s["activos_distribucion_generados"]), 3)
        self.assertEqual([a["fuente"] for a in s["alertas_internas"]], ["m-06"])
        self.assertEqual({d["ruta"] for d in s["enrutamiento"]["decisiones"]}, {"logro", "dudas", "periodo", "bloqueo"})
        self.assertEqual(s["traza"][-1], "consolidacion")
        self.assertEqual(s["almacenamiento"]["estado"], "no_persistido")
        for a in s["activos_distribucion_generados"]:
            self.assertEqual(a["estado"], "borrador")
            self.assertNotIn("m-06", a["fuentes"])

    def test_generadores_reciben_solo_sus_fuentes(self):
        peticiones = []
        def generar(p):
            peticiones.append(deepcopy(p))
            self.assertEqual(p["fuentes"], [m["id"] for m in p["interacciones"]])
            self.assertNotIn("m-06", json.dumps(p))
            self.assertNotIn("timeout", json.dumps(p))
            return {"copy": "Prueba", "fuentes": p["fuentes"]}
        s = self.ejecutar(componentes=replace(self.componentes, generar_post=generar, generar_faq=generar, generar_highlights=generar))
        self.assertFalse(s["errores"])
        self.assertEqual([p["fuentes"] for p in peticiones], [["m-02", "m-03"], ["m-01"], ["m-01", "m-02", "m-03", "m-04", "m-05"]])

    def test_lote_vacio_no_invoca_ia(self):
        def prohibido(_):
            self.fail("Lote vacío no debe consumir IA")
        self.entrada["interacciones"] = []
        s = self.ejecutar(componentes=replace(self.componentes, analizar=prohibido, puntuar=prohibido))
        self.assertEqual(s["estado"], "completado_local")
        self.assertEqual(s["activos_distribucion_generados"], [])
        self.assertEqual(s["traza"], ["ingesta", "consolidacion"])

    def test_bloqueo_sin_generacion(self):
        self.entrada["interacciones"] = self.entrada["interacciones"][-1:]
        s = self.ejecutar()
        self.assertEqual(s["activos_distribucion_generados"], [])
        self.assertEqual(len(s["alertas_internas"]), 1)

    def test_sin_cierre_no_highlights(self):
        self.entrada["cierre_periodo"] = False
        s = self.ejecutar()
        self.assertNotIn("generador_highlights", s["traza"])
        self.assertEqual(len(s["activos_distribucion_generados"]), 2)

    def test_sin_ruta(self):
        self.entrada["cierre_periodo"] = False
        self.entrada["interacciones"] = self.entrada["interacciones"][3:4]
        s = self.ejecutar()
        self.assertEqual(s["estado"], "completado_local")
        self.assertEqual(len(s["enrutamiento"]["sin_ruta"]), 1)
        self.assertFalse(s["activos_distribucion_generados"])

    def test_entrada_invalida_corta_flujo(self):
        for entrada in (None, [], {}, {**self.entrada, "cierre_periodo": "true"},
                        {**self.entrada, "interacciones": [self.entrada["interacciones"][0]] * 2}):
            with self.subTest(entrada=type(entrada)):
                s = self.ejecutar(entrada=entrada) if entrada is not None else ejecutar_lote(None, self.componentes)
                self.assertEqual(s["estado"], "error")
                self.assertEqual(s["errores"][0]["nodo"], "ingesta")
                self.assertNotIn("analizar", s["traza"])

    def test_analisis_incompleto_o_desconocido(self):
        for resultado in ({}, {"inventado": {}}, []):
            s = self.ejecutar(componentes=replace(self.componentes, analizar=lambda _: resultado))
            self.assertEqual(s["errores"][0]["nodo"], "analizar")
            self.assertNotIn("router", s["traza"])

    def test_booleano_falso_como_texto_rechazado(self):
        self.señales["m-06"]["es_bloqueo"] = "false"
        s = self.ejecutar(componentes=crear_componentes(self.señales))
        self.assertEqual(s["errores"][0]["nodo"], "analizar")

    def test_puntuaciones_invalidas(self):
        for valor in (True, -0.1, 1.1, float("nan"), float("inf"), "0.8"):
            with self.subTest(valor=valor):
                self.señales["m-01"]["relevancia"] = valor
                s = self.ejecutar(componentes=crear_componentes(self.señales))
                self.assertEqual(s["errores"][0]["nodo"], "puntuar")

    def test_puntuacion_faltante(self):
        s = self.ejecutar(componentes=replace(self.componentes, puntuar=lambda _: {}))
        self.assertEqual(s["errores"][0]["nodo"], "puntuar")

    def test_fuentes_inventadas_omitidas_o_duplicadas_rechazadas(self):
        for fuentes in (["m-06"], [], ["m-01", "m-01"], [None]):
            with self.subTest(fuentes=fuentes):
                s = self.ejecutar(componentes=replace(self.componentes, generar_post=lambda _: {"copy": "X", "fuentes": fuentes}))
                self.assertEqual(s["estado"], "error")
                self.assertFalse(s["activos_distribucion_generados"])

    def test_generacion_vacia_o_campos_extra(self):
        for respuesta in ({"copy": "  ", "fuentes": ["m-01"]}, {"copy": "X", "fuentes": ["m-01"], "publicado": True}, None):
            s = self.ejecutar(componentes=replace(self.componentes, generar_post=lambda _: respuesta))
            self.assertEqual(s["estado"], "error")

    def test_error_no_expone_secretos_ni_resultados_parciales(self):
        def fallar(_):
            raise RuntimeError("clave_privada_y_texto_de_usuario")
        s = self.ejecutar(componentes=replace(self.componentes, generar_highlights=fallar))
        self.assertEqual(s["estado"], "error")
        self.assertFalse(s["activos_distribucion_generados"])
        self.assertFalse(s["alertas_internas"])
        self.assertNotIn("clave_privada", json.dumps(s))
        self.assertEqual(s["errores"][0]["tipo"], "RuntimeError")

    def test_fallo_analizador_no_invoca_puntuador(self):
        def fallar(_):
            raise TimeoutError()
        s = self.ejecutar(componentes=replace(self.componentes, analizar=fallar))
        self.assertEqual(s["estado"], "error")
        self.assertNotIn("puntuar", s["traza"])

    def test_no_mutacion_y_reproducibilidad(self):
        original = deepcopy(self.entrada)
        a = self.ejecutar()
        self.assertEqual(self.entrada, original)
        self.entrada["interacciones"].reverse()
        self.assertEqual(a, self.ejecutar())

    def test_callback_no_altera_estado(self):
        def analizar(lote):
            resultado = self.componentes.analizar(lote)
            lote["interacciones"].clear()
            return resultado
        s = self.ejecutar(componentes=replace(self.componentes, analizar=analizar))
        self.assertEqual(len(s["fuentes"]), 6)

    def test_instancia_reutilizable_sin_contaminar_lotes(self):
        g = construir_grafo(self.componentes)
        a = g.invoke({"entrada": self.entrada}, config={"recursion_limit": 100})
        b = g.invoke({"entrada": {**self.entrada, "interacciones": []}})
        self.assertEqual(len(a["salida"]["activos_distribucion_generados"]), 3)
        self.assertEqual(b["salida"]["activos_distribucion_generados"], [])

    def test_lote_grande_supera_limite_por_defecto_langgraph(self):
        self.entrada["interacciones"] = [{**self.entrada["interacciones"][0], "id": f"m-{i:03d}"} for i in range(100)]
        senales = {m["id"]: self.señales["m-01"] for m in self.entrada["interacciones"]}
        s = self.ejecutar(componentes=crear_componentes(senales))
        self.assertEqual(s["estado"], "completado_local")
        self.assertEqual(len(s["activos_distribucion_generados"]), 101)
        self.assertEqual(len({a["id_activo"] for a in s["activos_distribucion_generados"]}), 101)

    def test_configuracion_router_respetada(self):
        s = self.ejecutar(cfg=Configuracion(relevancia_minima=1))
        self.assertFalse(s["activos_distribucion_generados"])
        self.assertEqual(len(s["alertas_internas"]), 1)

    def test_adaptador_pydantic(self):
        from pydantic import BaseModel
        class Interaccion(BaseModel):
            id: str
            autor: str
            canal: str
            fecha: str
            texto: str
        modelos = [Interaccion(**m) for m in self.entrada["interacciones"]]
        entrada = preparar_entrada(modelos, origen_comunidad="demo", periodo_referencia="2026-W40", cierre_periodo=True)
        self.assertEqual(self.ejecutar(entrada)["estado"], "completado_local")

    def test_adaptador_exige_lista(self):
        with self.assertRaises(ContratoInvalido):
            preparar_entrada({}, origen_comunidad="demo", periodo_referencia="semana", cierre_periodo=False)

    def test_componentes_explicitos(self):
        with self.assertRaises(ContratoInvalido):
            construir_grafo(None)
        with self.assertRaises(ContratoInvalido):
            replace(self.componentes, simulado="false")

    def test_tipo_no_sustituye_analisis(self):
        self.entrada["interacciones"][-1]["tipo"] = "recomendacion_repositorio"
        s = self.ejecutar()
        self.assertEqual(s["alertas_internas"][0]["fuente"], "m-06")

    def test_salida_serializable(self):
        json.dumps(self.ejecutar(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
