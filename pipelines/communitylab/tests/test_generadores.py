"""Generadores de Fabián con Gemini simulado por transporte (sin red ni claves)."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from pipelines.communitylab.gemini import ClienteGemini, RespuestaInvalidaIA
from pipelines.communitylab.gemini_falso import GeminiFalso, configuracion, cuerpo_ok, ok
from pipelines.communitylab.generadores import generar_faq, generar_highlights, generar_post
from pipelines.communitylab.generadores.contrato import (
    dispatch_generator, validar_contrato_entrada, validar_contrato_salida,
)
from pipelines.communitylab.generadores.prompts.faq_prompt import FAQ_TIP_SYSTEM_PROMPT
from pipelines.communitylab.generadores.prompts.highlights_prompt import HIGHLIGHTS_SYSTEM_PROMPT
from pipelines.communitylab.generadores.prompts.post_linkedin_prompt import POST_LINKEDIN_SYSTEM_PROMPT

BASE = Path(__file__).resolve().parents[1]
RAIZ = Path(__file__).resolve().parents[3]
PETICIONES = json.loads((BASE / "ejemplos" / "peticiones_generadores.json").read_text(encoding="utf-8"))
GENERADORES = {
    "post_linkedin_x": (generar_post, POST_LINKEDIN_SYSTEM_PROMPT),
    "faq_tip_tecnico": (generar_faq, FAQ_TIP_SYSTEM_PROMPT),
    "community_highlights": (generar_highlights, HIGHLIGHTS_SYSTEM_PROMPT),
}


def peticion(formato):
    return deepcopy(next(p for p in PETICIONES if p["formato"] == formato))


class PruebasGeneradores(unittest.TestCase):
    def ejecutar(self, formato, guion, p=None):
        self.falso = GeminiFalso(guion)
        funcion = GENERADORES[formato][0]
        return funcion(p or peticion(formato), ClienteGemini(configuracion(), transporte=self.falso.transporte))

    def test_exito_de_los_tres_generadores(self):
        for formato, (_, sistema) in GENERADORES.items():
            with self.subTest(formato=formato):
                p = peticion(formato)
                salida = self.ejecutar(formato, [ok({"copy": "  Texto final del activo.  "})], p)
                self.assertEqual(salida, {"copy": "Texto final del activo.", "fuentes": p["fuentes"]})
                cuerpo = self.falso.peticiones[0]["cuerpo"]
                self.assertTrue(cuerpo["systemInstruction"]["parts"][0]["text"].startswith(sistema))
                usuario = cuerpo["contents"][0]["parts"][0]["text"]
                self.assertTrue(all(m["texto"].strip() in usuario for m in p["interacciones"]))
                self.assertIn("copy", cuerpo["generationConfig"]["responseJsonSchema"]["properties"])

    def test_limpia_envolturas_markdown(self):
        salida = self.ejecutar("post_linkedin_x", [ok({"copy": "```\nTexto en bloque\n```"})])
        self.assertEqual(salida["copy"], "Texto en bloque")

    def test_vacio_tipo_incorrecto_y_truncado_escalan_y_luego_fallan(self):
        casos = {"vacio": ok({"copy": "   "}), "tipo": ok({"copy": 5}), "claves": ok({"texto": "x"}),
                 "truncado": ok({"copy": "Texto"}, finish="MAX_TOKENS"),
                 "no_json": (200, cuerpo_ok(None, texto="Texto suelto"), {})}
        for formato in GENERADORES:
            for motivo, paso in casos.items():
                with self.subTest(formato=formato, motivo=motivo):
                    with self.assertRaises(RespuestaInvalidaIA):
                        self.ejecutar(formato, [paso, paso])
                    self.assertEqual(self.falso.modelos, ["gemini-rapido", "gemini-escalado"])
                    self.assertEqual(self.ejecutar(formato, [paso, ok({"copy": "Bien"})])["copy"], "Bien")

    def test_entradas_invalidas_no_llaman_al_modelo(self):
        def cambiar(f):
            p = peticion("faq_tip_tecnico")
            f(p)
            return p
        casos = {
            "fuente_inventada": cambiar(lambda p: p["fuentes"].append("ajena")),
            "fuente_omitida": cambiar(lambda p: p["fuentes"].pop()),
            "fuente_duplicada": cambiar(lambda p: p["fuentes"].append(p["fuentes"][0])),
            "interaccion_extra": cambiar(lambda p: p["interacciones"].append(
                {**p["interacciones"][0], "id": "otra"})),
            "id_duplicado": cambiar(lambda p: p["interacciones"].append(dict(p["interacciones"][0]))),
            "texto_vacio": cambiar(lambda p: p["interacciones"][0].update(texto="  ")),
            "autor_faltante": cambiar(lambda p: p["interacciones"][0].pop("autor")),
            "sin_fuentes": cambiar(lambda p: p.update(fuentes=[])),
            "otro_formato": cambiar(lambda p: p.update(formato="post_linkedin_x")),
            "formato_desconocido": cambiar(lambda p: p.update(formato="tiktok")),
            "periodo_vacio": cambiar(lambda p: p.update(periodo_referencia="")),
            "campo_faltante": cambiar(lambda p: p.pop("ruta")),
        }
        for motivo, p in casos.items():
            with self.subTest(motivo=motivo):
                with self.assertRaises(ValueError):
                    self.ejecutar("faq_tip_tecnico", [], p)
                self.assertEqual(self.falso.peticiones, [])

    def test_salida_rechaza_fuentes_alteradas_y_copy_invalido(self):
        p = peticion("faq_tip_tecnico")
        for salida in ({"copy": "x", "fuentes": p["fuentes"] + ["ajena"]},
                       {"copy": "x", "fuentes": p["fuentes"][:1]},
                       {"copy": "x", "fuentes": p["fuentes"] + p["fuentes"][:1]},
                       {"copy": "", "fuentes": p["fuentes"]},
                       {"copy": "x", "fuentes": p["fuentes"], "extra": 1}):
            with self.subTest(salida=salida), self.assertRaises(ValueError):
                validar_contrato_salida(salida, p)
        reordenada = {"copy": "x", "fuentes": list(reversed(p["fuentes"]))}
        self.assertIs(validar_contrato_salida(reordenada, p), reordenada)

    def test_dispatch_generator(self):
        p = peticion("post_linkedin_x")
        salida = dispatch_generator(p, {"post_linkedin_x": lambda c: {"copy": "ok", "fuentes": c["fuentes"]}})
        self.assertEqual(salida["fuentes"], p["fuentes"])
        with self.assertRaises(ValueError):
            dispatch_generator(p, {"post_linkedin_x": lambda c: {"copy": "ok", "fuentes": ["inventada"]}})
        with self.assertRaises(KeyError):
            dispatch_generator(p, {})

    def test_peticiones_de_ejemplo_cumplen_el_contrato(self):
        self.assertEqual({p["formato"] for p in PETICIONES}, set(GENERADORES))
        for p in PETICIONES:
            validar_contrato_entrada(p)


class PruebasImportacion(unittest.TestCase):
    def test_importa_como_paquete_desde_la_raiz_sin_depender_del_directorio(self):
        codigo = ("import pipelines.communitylab.generadores as g, pipelines.communitylab.componentes_gemini as c; "
                  "assert callable(g.generar_post) and callable(c.crear_componentes_gemini)")
        for cwd in (RAIZ, BASE):
            with self.subTest(cwd=cwd.name):
                p = subprocess.run([sys.executable, "-c", codigo], cwd=cwd, capture_output=True, text=True,
                                   env={**os.environ, "PYTHONPATH": str(RAIZ)}, timeout=60)
                self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()
