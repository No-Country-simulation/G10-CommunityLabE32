"""Regresiones de fidelidad editorial, diagnóstico de Gemini y procesamiento por bloques.

Todas usan el doble de transporte (sin red ni claves). Los casos de fidelidad reproducen
afirmaciones no sustentadas observadas en la prueba real del 17/10 con el dataset de demo.
"""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pipelines.communitylab import Componentes, ejecutar_lote
from pipelines.communitylab import grafo as modulo_grafo
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini
from pipelines.communitylab.diagnostico import normalizar_diagnostico
from pipelines.communitylab.gemini import diagnostico_seguro
from pipelines.communitylab.gemini_falso import (
    CLAVE_FICTICIA, GeminiFalso, configuracion, error, responder_con_senales, tarea_de,
)
from pipelines.communitylab.generadores.fidelidad import revisar_fidelidad

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"
DATASET = json.loads((EJEMPLOS / "dataset_demo_20_personas.json").read_text(encoding="utf-8"))
POR_ID = {m["id"]: m for m in DATASET["interacciones"]}


def tipos(advertencias):
    return {a["tipo"] for a in advertencias}


class PruebasFidelidad(unittest.TestCase):
    def test_repositorio_con_guia_y_configuracion_inventadas(self):
        # demo-04 solo menciona un bot open source y 20 estrellas.
        copy = ("⚙️ Andrés Castillo publica su bot de Discord.\n\nAndrés liberó un bot que resume "
                "conversaciones largas. El repositorio incluye la configuración y una guía de despliegue.\n"
                "#OpenSource #Discord")
        advertencias = revisar_fidelidad(copy, [POR_ID["demo-04"]], "post_linkedin_x")
        detalles = {a["detalle"] for a in advertencias if a["tipo"] == "detalle_no_sustentado"}
        self.assertTrue({"configuración", "guía o tutorial", "despliegue"} <= detalles, advertencias)

    def test_responsabilidades_laborales_inventadas(self):
        # demo-08 solo dice que firmó su primer contrato como backend junior.
        copy = ("💼 Camila Rojas se incorpora como desarrolladora backend junior.\n\nEn su nuevo rol "
                "estará a cargo de las API de pagos y coordinará las revisiones de código.")
        advertencias = revisar_fidelidad(copy, [POR_ID["demo-08"]], "post_linkedin_x")
        self.assertIn("responsabilidades o funciones",
                      {a["detalle"] for a in advertencias if a["tipo"] == "detalle_no_sustentado"})

    def test_faq_no_presenta_diagnostico_que_las_fuentes_no_dan(self):
        fuentes = [POR_ID["demo-02"], POR_ID["demo-03"]]
        copy = ("FAQ: Reintentos en LangGraph\n\nPregunta: ¿Cómo configuro reintentos?\n\nRespuesta: "
                "El flujo carecía de la política de reintentos; la causa es un nodo sin RetryPolicy.")
        self.assertIn("diagnostico_no_sustentado", tipos(revisar_fidelidad(copy, fuentes, "faq_tip_tecnico")))
        recomendacion = ("FAQ: Reintentos en LangGraph\n\nPregunta: ¿Cómo configuro reintentos con espera "
                         "exponencial?\n\nRespuesta: Una opción es definir una política de reintentos en el "
                         "nodo que llama al modelo y limitar la cantidad de intentos.")
        self.assertEqual(revisar_fidelidad(recomendacion, fuentes, "faq_tip_tecnico"), [])

    def test_logro_colectivo_no_se_atribuye_a_una_persona(self):
        individual = "🏆 Isabela Cruz lanzó el dashboard de métricas con Next.js y FastAPI."
        self.assertIn("posible_atribucion_individual",
                      tipos(revisar_fidelidad(individual, [POR_ID["demo-12"]], "post_linkedin_x")))
        colectivo = "🏆 El equipo de Isabela Cruz terminó el dashboard de métricas con Next.js y FastAPI."
        self.assertNotIn("posible_atribucion_individual",
                         tipos(revisar_fidelidad(colectivo, [POR_ID["demo-12"]], "post_linkedin_x")))

    def test_cifras_alteradas_se_marcan_y_las_correctas_no(self):
        fuente = [POR_ID["demo-04"]]
        self.assertIn("cifra_no_sustentada",
                      tipos(revisar_fidelidad("El bot ya tiene 50 estrellas en GitHub.", fuente, "post_linkedin_x")))
        self.assertNotIn("cifra_no_sustentada",
                         tipos(revisar_fidelidad("El bot ya tiene 20 estrellas en GitHub.", fuente, "post_linkedin_x")))

    def test_periodo_listas_y_hashtags_no_son_cifras_inventadas(self):
        copy = "Resumen 2026-W43\n1. Logros\n2. Dudas\n#Top10"
        self.assertEqual(revisar_fidelidad(copy, [POR_ID["demo-01"]], "community_highlights",
                                           contexto=("CommunityLab", "2026-W43")), [])

    def test_ids_y_referencias_de_fuente_no_son_cifras(self):
        # Falso positivo detectado en la prueba local: "[Fuente: ... - demo-02]".
        copy = "Resumen de dudas. [Fuente: Diego Ramírez - demo-02] [Fuente: Sofía Torres - demo-03]"
        self.assertEqual(revisar_fidelidad(copy, [POR_ID["demo-02"], POR_ID["demo-03"]], "faq_tip_tecnico"), [])

    def test_alcance_inventado_en_muestras_reales(self):
        # Textos reales del trabajo bcc99527 (17/10): la fuente no describe esas funciones ni contenidos.
        camila = ("💼 Camila Rojas asume el rol de desarrolladora backend junior.\n\nLa posición abarca el diseño "
                  "de servicios web y el mantenimiento de APIs para los sistemas de la empresa.")
        self.assertIn("alcance o contenido descrito",
                      {a["detalle"] for a in revisar_fidelidad(camila, [POR_ID["demo-08"]], "post_linkedin_x")})
        ricardo = "Este entrenamiento cubrió el análisis de planes de ejecución."
        self.assertIn("detalle_no_sustentado", tipos(revisar_fidelidad(ricardo, [POR_ID["demo-17"]], "post_linkedin_x")))

    def test_datos_copiados_de_la_fuente_no_cuentan_como_encuadre_colectivo(self):
        # demo-20 dice "Organizamos"; "9 equipos" y "40 participantes" son datos, no reconocen al equipo.
        ana = "🏆 Ana Valenzuela lidera el hackathon con 40 participantes, 9 equipos y 3 proyectos activos."
        advertencias = revisar_fidelidad(ana, [POR_ID["demo-20"]], "post_linkedin_x")
        self.assertIn("posible_atribucion_individual", tipos(advertencias))
        self.assertIn("responsabilidades o funciones", {a["detalle"] for a in advertencias})

    def test_numero_de_semana_del_periodo_no_es_cifra_inventada(self):
        copy = "Community Highlights | Semana 43\nResumen de la semana."
        self.assertEqual(revisar_fidelidad(copy, [POR_ID["demo-01"]], "community_highlights",
                                           contexto=("CommunityLab", "2026-W43")), [])

    def test_post_fiel_sin_advertencias(self):
        copy = ("🏆 Mariana López obtiene la certificación AWS Cloud Practitioner.\n\nFelicitamos a Mariana "
                "por aprobar la certificación tras seis semanas de estudio con recursos del canal de cloud.\n"
                "#AWS #Cloud")
        self.assertEqual(revisar_fidelidad(copy, [POR_ID["demo-01"]], "post_linkedin_x"), [])

    def test_archivo_inventado(self):
        self.assertIn("archivo_no_sustentado",
                      tipos(revisar_fidelidad("Incluye un deploy.yml listo.", [POR_ID["demo-13"]], "post_linkedin_x")))


MARCADOR = "CONTENIDO_PRIVADO_FICTICIO_7429"
CLAVE_MARCADOR = "AIzaSyFICTICIA_" + "0123456789abcdefXYZ"
CONVERSACION = "Hola, soy Laura y llevo tres días bloqueada con el despliegue"


def cuerpo_hostil():
    """Respuesta 400 que refleja datos de la petición en todos los campos de texto."""
    return {"error": {
        "code": 400, "status": MARCADOR,
        "message": f'Invalid input: {MARCADOR} "{MARCADOR}" key={CLAVE_MARCADOR} texto: {CONVERSACION}',
        "details": [
            {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": MARCADOR,
             "metadata": {"valor": MARCADOR}},
            {"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
                {"field": f"contents[0].parts[0].{MARCADOR}", "description": MARCADOR},
                {"field": MARCADOR, "description": CONVERSACION},
                {"field": "generationConfig.responseJsonSchema", "description": MARCADOR},
                {"field": 42}, "no-es-un-dict"]},
            "texto suelto", 7, None]}}


def sin_marcadores(prueba, texto):
    for marcador in (MARCADOR, CLAVE_MARCADOR, "AIza", "Laura", "bloqueada"):
        prueba.assertNotIn(marcador, texto)


class PruebasDiagnosticoGemini(unittest.TestCase):
    def test_texto_libre_status_reason_y_campos_no_se_copian(self):
        d = diagnostico_seguro(400, cuerpo_hostil(), {"bytes_peticion": 10, "valores_enum": 40, "otro": MARCADOR})
        sin_marcadores(self, json.dumps(d, ensure_ascii=False))
        self.assertEqual((d["http"], d["categoria"], d["estado_proveedor"], d["razon"]),
                         (400, "peticion_rechazada", "OTRO", "otra"))
        self.assertEqual(d["campos"], ["contents[].parts[].*", "*", "generation_config.response_json_schema"])
        self.assertEqual(d["peticion"], {"bytes_peticion": 10, "valores_enum": 40})
        self.assertEqual(d["detalle"], "El proveedor rechazó la petición.")

    def test_valores_conocidos_conservan_categorias_utiles(self):
        cuerpo = {"error": {"status": "INVALID_ARGUMENT", "message": "Request contains an invalid argument.",
                            "details": [{"reason": "API_KEY_INVALID"},
                                        {"fieldViolations": [{"field": "generation_config.response_json_schema"}]}]}}
        d = diagnostico_seguro(400, cuerpo)
        self.assertEqual((d["estado_proveedor"], d["razon"], d["campos"]),
                         ("INVALID_ARGUMENT", "API_KEY_INVALID", ["generation_config.response_json_schema"]))
        self.assertIn("argumento inválido", d["detalle"])
        self.assertNotIn("Request contains", json.dumps(d))
        self.assertEqual(diagnostico_seguro(401, {})["categoria"], "credencial")
        self.assertEqual(diagnostico_seguro(404, {})["categoria"], "modelo_o_ruta")

    def test_estructuras_inesperadas_no_provocan_excepciones(self):
        for cuerpo in (None, [], "texto", {"error": "texto"}, {"error": {"details": "x", "status": 5}},
                       {"error": {"details": [{"reason": ["lista"]}, {"fieldViolations": "x"}]}}):
            d = diagnostico_seguro(400, cuerpo)
            self.assertEqual(d["categoria"], "peticion_rechazada")
        self.assertIsNone(normalizar_diagnostico("no-es-dict"))
        self.assertEqual(normalizar_diagnostico({"http": "400", "campos": "x"})["categoria"], "otro")
        # Idempotente: normalizar dos veces no cambia el resultado.
        d = diagnostico_seguro(400, cuerpo_hostil())
        self.assertEqual(normalizar_diagnostico(d), d)

    def test_400_hostil_no_llega_a_logs_ni_al_resultado_del_grafo(self):
        falso = GeminiFalso(responder=lambda p: (400, cuerpo_hostil(), {}))
        componentes = crear_componentes_gemini(configuracion(tamano_bloque=40), transporte=falso.transporte)
        with self.assertLogs("communitylab.gemini", level="INFO") as registro:
            salida = ejecutar_lote({**DATASET}, componentes)
        self.assertEqual(salida["estado"], "error")
        self.assertEqual(len(falso.peticiones), 1)  # Un 400 no se escala ni se reintenta.
        diagnostico = salida["errores"][0]["diagnostico"]
        self.assertEqual(diagnostico["peticion"]["items_esperados"], 20)
        # 20 IDs + 4 valores del enum de sentimiento.
        self.assertEqual(diagnostico["peticion"]["valores_enum"], 24)
        texto = "\n".join(registro.output) + json.dumps(salida, ensure_ascii=False)
        self.assertIn("gemini diagnostico", texto)
        sin_marcadores(self, texto)
        self.assertNotIn(CLAVE_FICTICIA, texto)
        for m in DATASET["interacciones"]:
            self.assertNotIn(m["texto"], texto)

    def test_grafo_normaliza_diagnosticos_de_cualquier_componente(self):
        class ErrorConDiagnostico(Exception):
            diagnostico = {"http": 400, "estado_proveedor": MARCADOR, "razon": MARCADOR,
                           "detalle": MARCADOR, "campos": [MARCADOR], "extra": MARCADOR}

        def analizar(_):
            raise ErrorConDiagnostico()
        componentes = Componentes(analizar=analizar, puntuar=dict, generar_post=dict, generar_faq=dict,
                                  generar_highlights=dict, simulado=False)
        salida = ejecutar_lote({**DATASET}, componentes)
        sin_marcadores(self, json.dumps(salida, ensure_ascii=False))
        self.assertEqual(salida["errores"][0]["diagnostico"]["estado_proveedor"], "OTRO")


class PruebasBloques(unittest.TestCase):
    def test_lote_grande_se_divide_en_bloques_acotados(self):
        interacciones = [{"id": f"hist-{i:04d}", "autor": f"persona {i}", "canal": "dudas",
                          "fecha": "2023-02-01T10:00:00Z", "texto": f"Consulta número {i}"} for i in range(85)]
        senales = {m["id"]: {"es_logro": False, "es_duda": False, "es_bloqueo": False,
                             "tema": "general", "relevancia": 0.1} for m in interacciones}
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=interacciones))
        componentes = crear_componentes_gemini(configuracion(tamano_bloque=40, max_llamadas=16),
                                               transporte=falso.transporte)
        salida = ejecutar_lote({"origen_comunidad": "prueba", "periodo_referencia": "2023-W05",
                                "cierre_periodo": False, "interacciones": interacciones}, componentes)
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        tareas = [tarea_de(p) for p in falso.peticiones]
        # Bloques dimensionados por el límite de salida (analisis_gemini._bloque_efectivo), acotados por 40.
        from pipelines.communitylab.analisis_gemini import _bloque_efectivo
        cliente = SimpleNamespace(cfg=configuracion(tamano_bloque=40, max_llamadas=16))
        esperado = tuple(-(-85 // _bloque_efectivo(cliente, t)) for t in ("analizar", "puntuar"))
        self.assertEqual((tareas.count("analizar"), tareas.count("puntuar")), esperado)
        for p in falso.peticiones:
            items = p["cuerpo"]["generationConfig"]["responseJsonSchema"]["properties"]["resultados"]
            # Bloques acotados y sin longitud fija del array (ver analisis_gemini._esquema).
            self.assertLessEqual(len(items["items"]["properties"]["id"]["enum"]), 40)
            self.assertNotIn("minItems", items)
            self.assertNotIn("maxItems", items)


class PruebasPresupuestoCierre(unittest.TestCase):
    """Límite conocido (docs/gemini-grafo-worker.md): 16 llamadas por trabajo y generadores sin tope.
    Con la configuración de la VM (bloque 40, salida 2048 -> bloques de 22 y 40), un cierre de N mensajes
    usa ceil(N/22) + ceil(N/40) llamadas base + 1 highlights (si hay mensajes relevantes) + 1 por logro/FAQ.
    Sin nada relevante, 220 mensajes caben justo (10 + 6) y 221 ya no (11 + 6). Si no cabe, el trabajo
    falla ENTERO con PresupuestoAgotadoIA: no hay borradores parciales ni descartes silenciosos."""

    def _cierre(self, n, logros):
        interacciones = [{"id": f"w-{i:04d}", "autor": f"persona {i}", "canal": "general",
                          "fecha": "2026-10-20T10:00:00Z", "texto": f"Mensaje ficticio {i}"} for i in range(n)]
        senales = {m["id"]: {"es_logro": i < logros, "es_duda": False, "es_bloqueo": False,
                             "tema": f"tema {i}", "relevancia": 0.9 if i < logros else 0.1}
                   for i, m in enumerate(interacciones)}
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=interacciones))
        componentes = crear_componentes_gemini(configuracion(tamano_bloque=40, max_llamadas=16),
                                               transporte=falso.transporte)
        salida = ejecutar_lote({"origen_comunidad": "prueba", "periodo_referencia": "2026-W43",
                                "cierre_periodo": True, "interacciones": interacciones}, componentes)
        return salida, len(falso.peticiones)

    def test_cierre_de_150_con_4_logros_cabe_justo_en_16_llamadas(self):
        salida, llamadas = self._cierre(150, 4)
        self.assertEqual(salida["errores"], [])
        self.assertEqual(llamadas, 7 + 4 + 1 + 4)          # analizar + puntuar + highlights + posts
        self.assertEqual(len(salida["activos_distribucion_generados"]), 5)

    def test_cierre_que_no_cabe_falla_entero_sin_borradores_parciales(self):
        self.assertEqual(self._cierre(220, 0)[0]["errores"], [])
        for n, logros in ((150, 5), (221, 0)):
            with self.subTest(n=n, logros=logros):
                salida, llamadas = self._cierre(n, logros)
                self.assertLessEqual(llamadas, 16)
                self.assertEqual(salida["errores"][0]["tipo"], "PresupuestoAgotadoIA")
                self.assertEqual(salida["activos_distribucion_generados"], [])


class PruebasGrafoFidelidad(unittest.TestCase):
    def test_activos_incluyen_advertencias_y_almacenamiento_aclarado(self):
        senales = {m["id"]: {"es_logro": m["id"] == "demo-04", "es_duda": False, "es_bloqueo": False,
                             "tema": "proyectos", "relevancia": 0.9 if m["id"] == "demo-04" else 0.1}
                   for m in DATASET["interacciones"]}
        copy = "Andrés publicó su bot. El repositorio incluye la guía de despliegue."
        falso = GeminiFalso(responder=responder_con_senales(senales, copy=copy, interacciones=DATASET["interacciones"]))
        salida = ejecutar_lote({**DATASET, "cierre_periodo": False},
                               crear_componentes_gemini(configuracion(), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "completado_local", salida["errores"])
        [activo] = salida["activos_distribucion_generados"]
        self.assertTrue(activo["advertencias_fidelidad"])
        self.assertEqual(salida["almacenamiento"]["capa"], "objetos_externos_oci")

    def test_bloqueo_nunca_llega_a_un_generador(self):
        senales = {m["id"]: {"es_logro": True, "es_duda": False, "es_bloqueo": m["id"] == "demo-06",
                             "tema": "x", "relevancia": 0.9} for m in DATASET["interacciones"]}
        falso = GeminiFalso(responder=responder_con_senales(senales, interacciones=DATASET["interacciones"]))
        original = modulo_grafo.enrutar_lote

        def router_defectuoso(lote, cfg):
            resultado = original(lote, cfg)
            resultado["decisiones"].insert(0, {"ruta": "logro", "destino": "generador_post_linkedin_x",
                                               "fuentes": ["demo-06"], "motivo": "defecto simulado"})
            return resultado
        with patch.object(modulo_grafo, "enrutar_lote", router_defectuoso):
            salida = ejecutar_lote({**DATASET, "cierre_periodo": False},
                                   crear_componentes_gemini(configuracion(max_llamadas=40), transporte=falso.transporte))
        self.assertEqual(salida["estado"], "error")
        self.assertEqual(salida["activos_distribucion_generados"], [])
        self.assertEqual(salida["errores"][0]["tipo"], "ContratoInvalido")


if __name__ == "__main__":
    unittest.main()
