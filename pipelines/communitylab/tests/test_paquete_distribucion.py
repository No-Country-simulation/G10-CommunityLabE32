"""Paquete de distribución con la forma del enunciado, sin red."""
from datetime import date
import unittest

from pipelines.communitylab.paquete import (fecha_por_defecto, id_por_defecto, paquete_distribucion,
                                            periodo_actual, ruta_paquete, sentimiento_predominante)

RESULTADO = {
    "origen_comunidad": "Discord_Grupo_ONE_G10", "periodo_referencia": "Semana_04",
    "activos_distribucion_generados": [
        {"formato": "post_linkedin_x", "copy": "post", "fuentes": ["a"], "id_activo_curaduria": "act-1"},
        {"formato": "community_highlights", "copy": "resumen", "fuentes": ["a", "b"]},
        {"formato": "faq_tip_tecnico", "copy": "faq", "fuentes": ["b", "c"]},
    ],
    "alertas_internas": [{"fuente": "d"}],
    "sentimientos": {"a": "positivo", "b": "neutral", "c": "positivo", "d": "negativo"},
    "clasificaciones": {"a": {"tipo": "logro", "tema": "contratación"}, "b": {"tipo": "duda", "tema": "langgraph"},
                        "c": {"tipo": "duda", "tema": "langgraph"}, "d": {"tipo": "bloqueo", "tema": None}},
    "almacenamiento": {"capa": "oci_object_storage", "estado": "guardado", "ruta_objeto": "activos/x.json"},
}


class PruebasPaquete(unittest.TestCase):
    def test_forma_del_enunciado(self):
        p = paquete_distribucion(RESULTADO, procesamiento_id="t1", total_interacciones=4)
        self.assertEqual(p["status"], "exito")
        resumen = p["resumen_comunidad"]
        self.assertEqual(resumen["total_interacciones_procesadas"], 4)
        self.assertEqual(resumen["sentimiento_predominante"], "Positivo")
        self.assertEqual(resumen["temas_principales"], ["langgraph", "contratación"])
        self.assertEqual(resumen["alertas_internas"], 1)
        activos = p["activos_distribucion_generados"]
        self.assertEqual([a["copy"] for a in activos["post_linkedin"]], ["post"])
        self.assertEqual([a["copy"] for a in activos["destaque_newsletter_semanal"]], ["resumen"])
        self.assertEqual([a["fuentes"] for a in activos["sugerencia_contenido_faq"]], [["b", "c"]])
        self.assertEqual(activos["post_linkedin"][0]["estado"], "borrador")
        self.assertEqual(p["almacenamiento_oci"]["ruta_objeto"], "activos/x.json")

    def test_sentimiento_predominante(self):
        self.assertEqual(sentimiento_predominante({}), "Sin datos")
        self.assertEqual(sentimiento_predominante({"a": "positivo", "b": "positivo", "c": "positivo"}),
                         "Altamente positivo")
        self.assertEqual(sentimiento_predominante({"a": "neutral", "b": "neutral", "c": "positivo"}), "Neutral")

    def test_ruta_del_objeto_en_el_bucket(self):
        self.assertEqual(ruta_paquete("2026-W43", "t1"), "activos/2026-W43/t1/paquete-distribucion.json")
        self.assertEqual(ruta_paquete("Semana 04 / prueba", "t1"), "activos/Semana-04-prueba/t1/paquete-distribucion.json")

    def test_fecha_e_id_estables_para_reenviar_el_mismo_lote(self):
        self.assertEqual(fecha_por_defecto("2026-W43"), "2026-10-19T12:00:00Z")
        self.assertEqual(fecha_por_defecto("Semana_04", hoy=date(2026, 10, 22)), "2026-10-22T12:00:00Z")
        self.assertEqual(periodo_actual(date(2026, 10, 22)), "2026-W43")
        uno = id_por_defecto("o", "p", 0, "Ana", "#c", "hola")
        self.assertEqual(uno, id_por_defecto("o", "p", 0, "Ana", "#c", "hola"))
        self.assertNotEqual(uno, id_por_defecto("o", "p", 1, "Ana", "#c", "hola"))


if __name__ == "__main__":
    unittest.main()
