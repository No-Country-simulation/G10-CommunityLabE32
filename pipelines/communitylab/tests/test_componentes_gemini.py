"""Grafo real con la clase Componentes canónica y los cinco componentes Gemini (transporte simulado)."""
from functools import partial
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pipelines.communitylab import Componentes, construir_grafo, ejecutar_lote
from pipelines.communitylab import analisis_gemini, generadores
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
from pipelines.communitylab.gemini import ErrorConfiguracionIA
from pipelines.communitylab.gemini_falso import (
    GeminiFalso, configuracion, error, responder_con_senales, tarea_de,
)

BASE = Path(__file__).resolve().parents[1] / "ejemplos"
ENTRADA = json.loads((BASE / "entrada.json").read_text(encoding="utf-8"))
SENALES = json.loads((BASE / "senales_simuladas.json").read_text(encoding="utf-8"))


class PruebasComponentesGemini(unittest.TestCase):
    def componentes(self, responder, **cfg):
        self.falso = GeminiFalso(responder=responder)
        return crear_componentes_gemini(configuracion(**cfg), transporte=self.falso.transporte)

    def test_usa_la_clase_canonica_y_solo_componentes_reales(self):
        c = self.componentes(responder_con_senales(SENALES))
        self.assertIs(type(c), Componentes)
        self.assertIs(c.simulado, False)
        construir_grafo(c)  # el grafo real acepta la instancia
        esperadas = {"analizar": analisis_gemini.analizar, "puntuar": analisis_gemini.puntuar,
                     "generar_post": generadores.generar_post, "generar_faq": generadores.generar_faq,
                     "generar_highlights": generadores.generar_highlights}
        for nombre, funcion in esperadas.items():
            componente = getattr(c, nombre)
            self.assertIsInstance(componente, partial)
            self.assertIs(componente.func, funcion)

    def test_grafo_completo_con_analisis_y_puntuacion_reales(self):
        with patch("pipelines.communitylab.simulados.crear_componentes", side_effect=AssertionError("doble")):
            salida = ejecutar_lote(ENTRADA, self.componentes(responder_con_senales(SENALES)))
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        self.assertIs(salida["simulado"], False)
        activos = salida["activos_distribucion_generados"]
        self.assertEqual({a["formato"] for a in activos},
                         {"post_linkedin_x", "faq_tip_tecnico", "community_highlights"})
        self.assertTrue(all(a["estado"] == "borrador" and a["simulado"] is False for a in activos))
        bloqueos = {i for i, s in SENALES.items() if s["es_bloqueo"]}
        self.assertTrue(bloqueos and all(not bloqueos & set(a["fuentes"]) for a in activos))
        self.assertEqual(len(salida["alertas_internas"]), len(bloqueos))
        tareas = [tarea_de(p) for p in self.falso.peticiones]
        self.assertEqual(tareas, ["analizar", "puntuar", "generar", "generar", "generar"])
        # Cada generador recibió exactamente las fuentes seleccionadas por el router.
        for activo, decision in zip(activos, [d for d in salida["enrutamiento"]["decisiones"]
                                              if d["destino"] != "alerta_interna"]):
            self.assertEqual(sorted(activo["fuentes"]), sorted(decision["fuentes"]))

    def test_lote_en_bloques_comparte_presupuesto(self):
        salida = ejecutar_lote(ENTRADA, self.componentes(responder_con_senales(SENALES), tamano_bloque=2))
        self.assertEqual(salida["estado"], "completado_local")
        n = len(ENTRADA["interacciones"])
        self.assertEqual([tarea_de(p) for p in self.falso.peticiones].count("analizar"), (n + 1) // 2)
        sin_presupuesto = ejecutar_lote(ENTRADA, self.componentes(responder_con_senales(SENALES),
                                                                  tamano_bloque=2, max_llamadas=4))
        self.assertEqual(sin_presupuesto["estado"], "error")
        self.assertEqual(sin_presupuesto["errores"][0]["tipo"], "PresupuestoAgotadoIA")
        self.assertEqual(sin_presupuesto["activos_distribucion_generados"], [])

    def test_fallo_en_un_generador_no_deja_activos_ni_alertas_parciales(self):
        base = responder_con_senales(SENALES)
        generados = []

        def responder(p):
            if tarea_de(p) == "generar":
                generados.append(p)
                if len(generados) == 2:
                    return error(401)
            return base(p)
        salida = ejecutar_lote(ENTRADA, self.componentes(responder))
        self.assertEqual(salida["estado"], "error")
        self.assertEqual((salida["activos_distribucion_generados"], salida["alertas_internas"]), ([], []))
        self.assertEqual(salida["errores"][0]["tipo"], "ErrorConfiguracionIA")
        # Diagnóstico estructurado y redactado: estado y categoría, nunca textos del lote.
        diagnostico = salida["errores"][0]["diagnostico"]
        self.assertEqual((diagnostico["http"], diagnostico["categoria"]), (401, "credencial"))
        serializado = json.dumps(salida["errores"], ensure_ascii=False)
        for m in ENTRADA["interacciones"]:
            self.assertNotIn(m["texto"], serializado)

    def test_analisis_con_ids_inventados_falla_sin_inventar_resultados(self):
        def responder(p):
            ids = [m["id"] for m in json.loads(p["cuerpo"]["contents"][0]["parts"][0]["text"])]
            return 200, {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(
                {"resultados": [{"id": "inventado", "es_logro": True, "es_duda": False,
                                 "es_bloqueo": False, "tema": "x"}] * len(ids)})}]}}]}, {}
        salida = ejecutar_lote(ENTRADA, self.componentes(responder))
        self.assertEqual(salida["estado"], "error")
        self.assertEqual(salida["errores"][0]["tipo"], "RespuestaInvalidaIA")
        self.assertEqual(len(self.falso.peticiones), 2)  # rápido + escalado, luego se detiene

    def test_duda_sin_tema_y_relevancia_fuera_de_rango_son_contrato_invalido(self):
        malas = {i: {**s, "tema": "" if s["es_duda"] else s["tema"]} for i, s in SENALES.items()}
        salida = ejecutar_lote(ENTRADA, self.componentes(responder_con_senales(malas)))
        self.assertEqual(salida["errores"][0]["tipo"], "RespuestaInvalidaIA")
        fuera = {i: {**s, "relevancia": 1.5} for i, s in SENALES.items()}
        salida = ejecutar_lote(ENTRADA, self.componentes(responder_con_senales(fuera)))
        self.assertEqual((salida["errores"][0]["nodo"], salida["errores"][0]["tipo"]),
                         ("puntuar", "RespuestaInvalidaIA"))

    def test_sin_configuracion_no_cae_en_simulacion(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "GEMINI_MODELOS": ""}):
            with self.assertRaises(ErrorConfiguracionIA):
                crear_componentes_gemini()


if __name__ == "__main__":
    unittest.main()
