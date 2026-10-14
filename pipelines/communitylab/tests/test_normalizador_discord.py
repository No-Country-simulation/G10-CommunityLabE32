import json
from pathlib import Path
import tempfile
import unittest

from pipelines.communitylab.normalizador_discord import (
    MAX_INTERACCIONES_POR_LOTE,
    construir_lotes,
    normalizar_discord_jsonl,
    normalizar_eventos,
)

CAMPOS_LOTE = {"origen_comunidad", "periodo_referencia", "cierre_periodo", "interacciones"}
CAMPOS_INTERACCION = {"id", "autor", "canal", "fecha", "texto", "tipo"}


def evento(message_id="1", **cambios):
    base = {
        "schema_version": "discord-source-v1",
        "message_id": message_id,
        "guild_id": "100",
        "channel_id": "200",
        "author_id": "300",
        "created_at": "2026-10-14T18:00:00+00:00",
        "content": "Terminé mi primer proyecto con Python.",
    }
    base.update(cambios)
    return base


class PruebasNormalizadorDiscord(unittest.TestCase):
    def test_acepta_evento_valido_sin_forzar_tipo(self):
        resultado = normalizar_eventos([evento()])
        self.assertEqual(resultado["estadisticas"], {"aceptados": 1, "rechazados": 0, "duplicados": 0})
        interaccion = resultado["interacciones"][0]
        self.assertEqual(interaccion["id"], "discord-1")
        self.assertEqual(interaccion["canal"], "discord_200")
        self.assertNotIn("tipo", interaccion)

    def test_rechaza_duplicados_y_eventos_invalidos(self):
        eventos = [evento(), evento(), {"schema_version": "roto"}, evento("2", content="   "), "texto"]
        resultado = normalizar_eventos(eventos)
        self.assertEqual(resultado["estadisticas"], {"aceptados": 1, "rechazados": 3, "duplicados": 1})

    def test_respeta_historial_previo_y_es_serializable(self):
        resultado = normalizar_eventos([evento("1"), evento("2")], historial_ids=["100-1"])
        self.assertEqual([i["id"] for i in resultado["interacciones"]], ["discord-2"])
        self.assertEqual(resultado["historial_ids"], ["100-1", "100-2"])
        json.dumps(resultado)

    def test_respeta_limites_de_autor_y_canal(self):
        interaccion = normalizar_eventos([evento(author_id="a" * 300, channel_id="c" * 300)])["interacciones"][0]
        self.assertLessEqual(len(interaccion["autor"]), 150)
        self.assertLessEqual(len(interaccion["canal"]), 50)

    def test_jsonl_devuelve_siempre_las_mismas_claves(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "export.jsonl"
            ruta.write_text(json.dumps(evento()) + "\n{roto\n\n", encoding="utf-8")
            leido = normalizar_discord_jsonl(str(ruta))
            faltante = normalizar_discord_jsonl(str(Path(carpeta) / "no_existe.jsonl"))
        self.assertEqual(set(leido), {"interacciones", "historial_ids", "estadisticas"})
        self.assertEqual(set(faltante), set(leido))
        self.assertEqual(leido["estadisticas"]["rechazados"], 1)
        self.assertEqual(faltante["interacciones"], [])

    def test_lote_cumple_contrato_de_trabajos(self):
        interacciones = normalizar_eventos([evento("1"), evento("2")])["interacciones"]
        lote = construir_lotes(interacciones, "discord", "S3")[0]
        self.assertEqual(set(lote), CAMPOS_LOTE)
        for interaccion in lote["interacciones"]:
            self.assertTrue(set(interaccion) <= CAMPOS_INTERACCION)
            for campo in ("id", "autor", "canal", "fecha", "texto"):
                self.assertTrue(interaccion[campo])

    def test_divide_en_lotes_de_500_y_solo_el_ultimo_cierra(self):
        interacciones = normalizar_eventos([evento(str(n)) for n in range(1201)])["interacciones"]
        lotes = construir_lotes(interacciones, "discord", "S3", cierre_periodo=True)
        self.assertEqual([len(l["interacciones"]) for l in lotes], [MAX_INTERACCIONES_POR_LOTE, MAX_INTERACCIONES_POR_LOTE, 201])
        self.assertEqual([l["cierre_periodo"] for l in lotes], [False, False, True])

    def test_exige_metadata_del_lote(self):
        with self.assertRaises(ValueError):
            construir_lotes([], "", "S3")


if __name__ == "__main__":
    unittest.main()
