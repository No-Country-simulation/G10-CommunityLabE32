"""Lotes parciales (previo=true) y sentimiento en el grafo, sin red."""
import os
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from copy import deepcopy
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from pipelines.communitylab.grafo import ejecutar_lote
from pipelines.communitylab.router_base import EntradaInvalida, enrutar_lote
from pipelines.communitylab.simulados import crear_componentes
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, responder_con_senales, tarea_de

BASE = Path(__file__).resolve().parents[1] / "ejemplos"


def mensaje(i, autor, analisis, previo=None):
    m = {"id": i, "autor": autor, "canal": "c", "fecha": "2026-10-12T10:00:00Z",
         "texto": f"texto {i}", "analisis": analisis}
    if previo is not None:
        m["previo"] = previo
    return m


def senal(logro=False, duda=False, bloqueo=False, tema="t", relevancia=0.9):
    return {"es_logro": logro, "es_duda": duda, "es_bloqueo": bloqueo, "tema": tema,
            "relevancia": relevancia}


def lote(mensajes, cierre=False):
    return {"origen_comunidad": "o", "periodo_referencia": "2026-W42", "cierre_periodo": cierre,
            "interacciones": mensajes}


class PruebasRouterPrevio(unittest.TestCase):
    def test_bloqueo_previo_no_repite_alerta(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(bloqueo=True), previo=True),
                               mensaje("b", "2", senal(bloqueo=True))]))
        self.assertEqual([d["fuentes"] for d in r["decisiones"]], [["b"]])
        self.assertIn("ya alertado", r["sin_ruta"][0]["motivo"])

    def test_logro_previo_no_genera_post(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(logro=True), previo=True)]))
        self.assertEqual(r["decisiones"], [])
        self.assertIn("lote parcial anterior", r["sin_ruta"][0]["motivo"])

    def test_duda_recurrente_entre_lotes_genera_faq_con_contexto(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(duda=True, tema="docker"), previo=True),
                               mensaje("b", "2", senal(duda=True, tema="docker"))]))
        self.assertEqual([(d["ruta"], d["fuentes"]) for d in r["decisiones"]], [("dudas", ["a", "b"])])

    def test_faq_solo_con_previos_no_se_regenera(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(duda=True, tema="docker"), previo=True),
                               mensaje("b", "2", senal(duda=True, tema="docker"), previo=True)]))
        self.assertEqual(r["decisiones"], [])

    def test_cierre_incluye_previos_en_highlights_y_excluye_bloqueos(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(logro=True), previo=True),
                               mensaje("b", "2", senal(logro=True)),
                               mensaje("c", "3", senal(bloqueo=True), previo=True)], cierre=True))
        rutas = {d["ruta"]: d["fuentes"] for d in r["decisiones"]}
        self.assertEqual(rutas, {"logro": ["b"], "periodo": ["a", "b"]})

    def test_previo_invalido_y_relevancia_se_mantiene(self):
        with self.assertRaises(EntradaInvalida):
            enrutar_lote(lote([mensaje("a", "1", senal(), previo="si")]))
        r = enrutar_lote(lote([mensaje("a", "1", senal(logro=True, relevancia=0.3))]))
        self.assertEqual(r["decisiones"], [])
        self.assertIn("Relevancia", r["sin_ruta"][0]["motivo"])

    def test_sin_previo_el_comportamiento_es_el_anterior(self):
        r = enrutar_lote(lote([mensaje("a", "1", senal(logro=True))]))
        self.assertEqual([d["ruta"] for d in r["decisiones"]], ["logro"])


class PruebasGrafoParcialYSentimiento(unittest.TestCase):
    def setUp(self):
        self.entrada = json.loads((BASE / "entrada.json").read_text(encoding="utf-8"))
        self.senales = json.loads((BASE / "senales_simuladas.json").read_text(encoding="utf-8"))
        red = patch.object(socket.socket, "connect", side_effect=AssertionError("RED PROHIBIDA"))
        red.start()
        self.addCleanup(red.stop)

    def test_previo_se_propaga_y_no_duplica_activos(self):
        entrada = deepcopy(self.entrada)
        entrada["cierre_periodo"] = False
        for m in entrada["interacciones"]:
            if m["id"] in ("m-01", "m-06"):
                m["previo"] = True
        salida = ejecutar_lote(entrada, crear_componentes(self.senales))
        self.assertEqual(salida["estado"], "completado_local")
        fuentes = {f for a in salida["activos_distribucion_generados"] for f in a["fuentes"]}
        self.assertNotIn("m-01", fuentes)
        self.assertEqual(salida["alertas_internas"], [])

    def test_previo_no_booleano_es_contrato_invalido(self):
        entrada = deepcopy(self.entrada)
        entrada["interacciones"][0]["previo"] = "true"
        salida = ejecutar_lote(entrada, crear_componentes(self.senales))
        self.assertEqual((salida["estado"], salida["errores"][0]["tipo"]), ("error", "ContratoInvalido"))

    def test_sentimiento_viaja_en_la_misma_llamada_de_analisis(self):
        senales = {i: {**s, "sentimiento": "positivo" if s["es_logro"] else "indeterminado"}
                   for i, s in self.senales.items()}
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=self.entrada["interacciones"]))
        salida = ejecutar_lote(self.entrada, crear_componentes_gemini(configuracion(), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        self.assertEqual(set(salida["sentimientos"]), {m["id"] for m in self.entrada["interacciones"]})
        self.assertEqual(salida["sentimientos"]["m-01"], "positivo")
        # Sin llamadas extra: 1 analizar + 1 puntuar + generadores.
        self.assertEqual([tarea_de(p) for p in falso.peticiones].count("analizar"), 1)

    def test_sentimiento_ausente_o_invalido_queda_sin_analizar_sin_romper_el_lote(self):
        senales = {i: {**s, "sentimiento": "feliz" if i == "m-01" else "negativo"}
                   for i, s in self.senales.items()}
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=self.entrada["interacciones"]))
        salida = ejecutar_lote(self.entrada, crear_componentes_gemini(configuracion(), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        self.assertNotIn("m-01", salida["sentimientos"])  # nunca se convierte en neutral
        self.assertEqual(salida["sentimientos"]["m-02"], "negativo")
        self.assertTrue(salida["activos_distribucion_generados"])

    def test_simulado_no_inventa_sentimiento(self):
        salida = ejecutar_lote(self.entrada, crear_componentes(self.senales))
        self.assertEqual(salida["sentimientos"], {})


if __name__ == "__main__":
    unittest.main()
