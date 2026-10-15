"""Política del cliente Gemini con transporte y reloj controlados (sin red ni claves)."""
import logging
import unittest

import httpx

from pipelines.communitylab.gemini import (
    ClienteGemini, ConfiguracionGemini, ContenidoBloqueadoIA, ErrorConfiguracionIA,
    ErrorCuotaIA, ErrorTransitorioIA, PresupuestoAgotadoIA, RespuestaInvalidaIA,
)
from pipelines.communitylab.gemini_falso import (
    CLAVE_FICTICIA, GeminiFalso, Reloj, configuracion, cuerpo_ok, error, ok,
)

ESQUEMA = {"type": "object", "properties": {"valor": {"type": "integer"}},
           "required": ["valor"], "additionalProperties": False}


def validar(objeto):
    if not isinstance(objeto, dict) or set(objeto) != {"valor"} or type(objeto["valor"]) is not int:
        raise ValueError("contrato")
    return objeto["valor"]


class PruebasClienteGemini(unittest.TestCase):
    def cliente(self, guion, **cfg):
        self.reloj = Reloj()
        self.falso = GeminiFalso(guion, reloj=self.reloj, latencia=0.5)
        return ClienteGemini(configuracion(**cfg), transporte=self.falso.transporte,
                             reloj=self.reloj, dormir=self.reloj.dormir)

    def generar(self, cliente):
        return cliente.generar_json("prueba", "sistema", "usuario", ESQUEMA, validar)

    def test_exito_con_salida_estructurada_y_clave_en_cabecera(self):
        with self.assertLogs("communitylab.gemini", logging.INFO) as logs:
            self.assertEqual(self.generar(self.cliente([ok({"valor": 7})])), 7)
        p = self.falso.peticiones[0]
        config = p["cuerpo"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseJsonSchema"], ESQUEMA)
        self.assertEqual(config["candidateCount"], 1)
        self.assertEqual(p["cabeceras"]["x-goog-api-key"], CLAVE_FICTICIA)
        self.assertEqual(self.falso.modelos, ["gemini-rapido"])
        registro = "\n".join(logs.output)
        self.assertIn("resultado=ok", registro)
        self.assertNotIn(CLAVE_FICTICIA, registro)
        self.assertNotIn("usuario", registro)

    def test_plazo_por_peticion_limitado_por_el_presupuesto(self):
        cliente = self.cliente([ok({"valor": 1})], timeout_peticion=10, presupuesto_segundos=10)
        self.reloj.ahora = 4  # quedan 6 s del trabajo
        self.generar(cliente)
        self.assertAlmostEqual(self.falso.peticiones[0]["timeout"]["read"], 6)

    def test_contrato_invalido_escala_al_siguiente_modelo(self):
        with self.assertLogs("communitylab.gemini", logging.INFO) as logs:
            valor = self.generar(self.cliente([ok({"otro": 1}), ok({"valor": 3})]))
        self.assertEqual(valor, 3)
        self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-escalado"])
        self.assertTrue(any("escalamiento" in l and "motivo=contrato" in l for l in logs.output))

    def test_json_invalido_truncado_vacio_y_sin_candidato_escalan(self):
        casos = {
            "json_invalido": (200, cuerpo_ok(None, texto="{no es json"), {}),
            "truncado": ok({"valor": 1}, finish="MAX_TOKENS"),
            "vacio": (200, cuerpo_ok(None, texto="  "), {}),
            "sin_candidato": (200, {"candidates": []}, {}),
            "terminacion": ok({"valor": 1}, finish="MALFORMED_RESPONSE"),
        }
        for motivo, paso in casos.items():
            with self.subTest(motivo=motivo):
                self.assertEqual(self.generar(self.cliente([paso, ok({"valor": 2})])), 2)
                self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-escalado"])

    def test_agotar_modelos_es_respuesta_invalida_sin_inventar(self):
        cliente = self.cliente([ok({"valor": "x"}), ok({"valor": None})])
        with self.assertRaises(RespuestaInvalidaIA):
            self.generar(cliente)
        self.assertEqual(len(self.falso.peticiones), 2)

    def test_partes_de_razonamiento_se_ignoran(self):
        cuerpo = cuerpo_ok({"valor": 5})
        cuerpo["candidates"][0]["content"]["parts"].insert(0, {"text": "pensando...", "thought": True})
        self.assertEqual(self.generar(self.cliente([(200, cuerpo, {})])), 5)

    def test_credenciales_y_configuracion_no_escalan_ni_reintentan(self):
        for estado in (400, 401, 403, 404):
            with self.subTest(estado=estado):
                cliente = self.cliente([error(estado, mensaje="API key not valid: secreto-interno")])
                with self.assertRaises(ErrorConfiguracionIA) as ctx:
                    self.generar(cliente)
                self.assertEqual(len(self.falso.peticiones), 1)
                self.assertNotIn("secreto-interno", str(ctx.exception))
                self.assertEqual(self.reloj.esperas, [])

    def test_429_respeta_retry_after_y_reintenta_mismo_modelo(self):
        cliente = self.cliente([error(429, cabeceras={"Retry-After": "3"}), ok({"valor": 9})])
        self.assertEqual(self.generar(cliente), 9)
        self.assertEqual(self.reloj.esperas, [3.0])
        self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-rapido"])

    def test_429_con_retryinfo_en_el_cuerpo(self):
        detalle = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "2s"}]
        cliente = self.cliente([error(429, detalles=detalle), ok({"valor": 1})])
        self.generar(cliente)
        self.assertEqual(self.reloj.esperas, [2.0])

    def test_cuota_diaria_no_reintenta_ni_escala(self):
        detalle = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]
        cliente = self.cliente([error(429, detalles=detalle)])
        with self.assertRaises(ErrorCuotaIA):
            self.generar(cliente)
        self.assertEqual(len(self.falso.peticiones), 1)

    def test_429_persistente_es_cuota_sin_escalar(self):
        cliente = self.cliente([error(429), error(429)], reintentos=1)
        with self.assertRaises(ErrorCuotaIA):
            self.generar(cliente)
        self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-rapido"])
        self.assertEqual(self.reloj.esperas, [1.0])

    def test_retry_after_mayor_que_la_espera_maxima_no_espera(self):
        cliente = self.cliente([error(429, cabeceras={"Retry-After": "60"})], espera_maxima=10)
        with self.assertRaises(ErrorCuotaIA):
            self.generar(cliente)
        self.assertEqual((len(self.falso.peticiones), self.reloj.esperas), (1, []))

    def test_5xx_reintenta_con_espera_acotada(self):
        cliente = self.cliente([error(503), ok({"valor": 4})])
        self.assertEqual(self.generar(cliente), 4)
        self.assertEqual(self.reloj.esperas, [1.0])

    def test_timeout_y_conexion_agotan_reintentos(self):
        cliente = self.cliente([httpx.ReadTimeout("t"), httpx.ConnectError("c")], reintentos=1)
        with self.assertRaises(ErrorTransitorioIA):
            self.generar(cliente)
        self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-rapido"])

    def test_presupuesto_de_llamadas(self):
        cliente = self.cliente([ok({"otro": 1})], max_llamadas=1)
        with self.assertRaises(PresupuestoAgotadoIA):
            self.generar(cliente)
        self.assertEqual(len(self.falso.peticiones), 1)

    def test_presupuesto_de_tiempo_corta_antes_de_llamar(self):
        cliente = self.cliente([], presupuesto_segundos=20)
        self.reloj.ahora = 19.5
        with self.assertRaises(PresupuestoAgotadoIA):
            self.generar(cliente)
        self.assertEqual(self.falso.peticiones, [])

    def test_no_espera_si_no_queda_presupuesto(self):
        cliente = self.cliente([error(503)], presupuesto_segundos=10, timeout_peticion=5)
        self.reloj.ahora = 8.5  # tras la llamada quedan 1 s: no hay margen para esperar y reintentar
        with self.assertRaises(ErrorTransitorioIA):
            self.generar(cliente)
        self.assertEqual(self.reloj.esperas, [])

    def test_presupuesto_de_tokens(self):
        cliente = self.cliente([ok({"valor": 1}, tokens=500)], max_tokens_trabajo=400)
        self.generar(cliente)
        with self.assertRaises(PresupuestoAgotadoIA):
            self.generar(cliente)
        self.assertEqual(len(self.falso.peticiones), 1)

    def test_bloqueo_de_seguridad_no_escala(self):
        for paso in (ok({"valor": 1}, finish="SAFETY"),
                     (200, {"promptFeedback": {"blockReason": "SAFETY"}}, {})):
            with self.subTest(paso=paso[1].get("promptFeedback", "candidato")):
                cliente = self.cliente([paso])
                with self.assertRaises(ContenidoBloqueadoIA):
                    self.generar(cliente)
                self.assertEqual(len(self.falso.peticiones), 1)


class PruebasConfiguracion(unittest.TestCase):
    def test_desde_entorno(self):
        cfg = ConfiguracionGemini.desde_entorno({
            "GEMINI_API_KEY": "k", "GEMINI_MODELOS": "gemini-a, gemini-b",
            "GEMINI_NIVEL_RAZONAMIENTO": "low", "GEMINI_PRESUPUESTO_SEGUNDOS": "90"})
        self.assertEqual(cfg.modelos, ("gemini-a", "gemini-b"))
        self.assertEqual((cfg.nivel_razonamiento, cfg.presupuesto_segundos), ("LOW", 90.0))
        self.assertNotIn("'k'", repr(cfg))

    def test_configuracion_invalida(self):
        base = {"GEMINI_API_KEY": "k", "GEMINI_MODELOS": "gemini-a"}
        for cambio in ({"GEMINI_API_KEY": ""}, {"GEMINI_MODELOS": ""},
                       {"GEMINI_MODELOS": "gpt-4"}, {"GEMINI_MODELOS": "gemini-a,gemini-a"},
                       {"GEMINI_TIMEOUT_PETICION": "50", "GEMINI_PRESUPUESTO_SEGUNDOS": "20"},
                       {"GEMINI_REINTENTOS": "9"}, {"GEMINI_NIVEL_RAZONAMIENTO": "extremo"},
                       {"GEMINI_MAX_LLAMADAS": "muchas"}):
            with self.subTest(cambio=cambio), self.assertRaises(ErrorConfiguracionIA):
                ConfiguracionGemini.desde_entorno({**base, **cambio})

    def test_nivel_de_razonamiento_y_temperatura_opcionales(self):
        falso = GeminiFalso([ok({"valor": 1})])
        cfg = configuracion(nivel_razonamiento="MINIMAL", temperatura=0.2)
        ClienteGemini(cfg, transporte=falso.transporte).generar_json("t", "s", "u", ESQUEMA, validar)
        config = falso.peticiones[0]["cuerpo"]["generationConfig"]
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "MINIMAL"})
        self.assertEqual(config["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
