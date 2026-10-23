"""Agrupación de temas casi iguales (tildes, artículos y plural), sin red."""
import unittest

from pipelines.communitylab.router_base import enrutar_lote
from pipelines.communitylab.temas import agrupar_temas, clave_tema, etiqueta_tema


class PruebasTemas(unittest.TestCase):
    def test_variantes_del_mismo_tema_comparten_clave(self):
        pares = [("diapositivas sesion", "diapositivas de sesión"),
                 ("documentacion curso", "documentación del curso"),
                 ("ver factura", "ver facturas"),
                 ("reclamo de cliente", "reclamo de clientes"),
                 ("errores de pago", "error de pago"),
                 ("certificacion", "Certificación")]
        for a, b in pares:
            self.assertEqual(clave_tema(a), clave_tema(b), (a, b))

    def test_temas_distintos_no_se_mezclan(self):
        self.assertNotEqual(clave_tema("certificación aws"), clave_tema("certificación oci"))
        self.assertNotEqual(clave_tema("api gemini"), clave_tema("api gemini y 429"))

    def test_se_muestra_la_variante_mas_usada_y_luego_la_mejor_escrita(self):
        self.assertEqual(etiqueta_tema({"documentacion curso": 1, "documentación del curso": 1}),
                         "documentación del curso")
        self.assertEqual(etiqueta_tema({"ver factura": 3, "ver facturas": 1}), "ver factura")

    def test_agrupa_suma_ordena_y_limita(self):
        conteos = [("documentacion curso", 1), ("documentación del curso", 2), ("langgraph", 2),
                   ("diapositivas sesion", 1), ("", 4)]
        self.assertEqual(agrupar_temas(conteos),
                         [("documentación del curso", 3), ("langgraph", 2), ("diapositivas sesion", 1)])
        self.assertEqual(len(agrupar_temas(conteos, limite=2)), 2)

    def test_dudas_con_variantes_del_tema_generan_una_sola_faq(self):
        def mensaje(i, autor, tema):
            return {"id": i, "autor": autor, "canal": "c", "fecha": "2026-10-22T10:00:00Z", "texto": f"texto {i}",
                    "analisis": {"es_logro": False, "es_duda": True, "es_bloqueo": False, "tema": tema,
                                 "relevancia": 0.9}}
        r = enrutar_lote({"origen_comunidad": "o", "periodo_referencia": "2026-W43", "cierre_periodo": False,
                          "interacciones": [mensaje("a", "1", "sesión de práctica"),
                                            mensaje("b", "2", "sesion de practica"),
                                            mensaje("c", "3", "sesiones de práctica")]})
        (faq,) = [d for d in r["decisiones"] if d["ruta"] == "dudas"]
        self.assertEqual(faq["fuentes"], ["a", "b", "c"])
        self.assertIn("sesión de práctica", faq["motivo"])


if __name__ == "__main__":
    unittest.main()
