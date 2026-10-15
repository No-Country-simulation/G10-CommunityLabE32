"""Compatibilidad con fuentes reales; IA, normalizador y Discord simulados.

La conversión fixture a Interaccion NO reemplaza el normalizador de Santiago.
El adaptador fixture de los nodos NO es la implementación de Fabián.
"""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from bot_discord.contracts import capture, validate_decision
from bot_discord.engine import Engine
from bot_discord.store import Store
from tests.helpers import config, source, decision, channels, message
from backend.app.schemas.procesamientos import Interaccion, IngestaRequest
from backend.app.pipelines import agent_nodes
from pipelines.communitylab import ejecutar_lote
from pipelines.communitylab.simulados import crear_componentes


def interaction(event):
    return Interaccion(id=event["message_id"], autor=event["author_id"], canal=event["channel_id"],
                       tipo="discord", fecha=event["created_at"], texto=event["content"]).model_dump()


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_matches_previous_reader_exactly(self):
        from discord_reader.core import capture as previous_capture
        with TemporaryDirectory() as tmp:
            cfg = config(Path(tmp) / "inbox.sqlite3")
            m = message(channels()[200])
            self.assertEqual(capture(m, cfg), previous_capture(m, cfg)[0])

    async def test_source_can_satisfy_current_repository_schema(self):
        request = IngestaRequest(origen_comunidad="discord_prueba", periodo_referencia="2026-W41",
                                interacciones=[interaction(source())])
        self.assertEqual(request.interacciones[0].id, "600")
        self.assertEqual(request.interacciones[0].texto, source()["content"])

    async def test_repository_analysis_and_faq_nodes_to_bot_transport(self):
        # Las funciones reales del repositorio se ejecutan, su llamada LLM se sustituye.
        event = source()
        lote = {"interacciones": [interaction(event)]}
        with patch.object(agent_nodes, "llamar_llm_openrouter", side_effect=[
            {"resultados": [{"id": "600", "es_logro": False, "es_duda": True,
                             "es_bloqueo": False, "tema": "python"}]},
            {"copy": "Respuesta técnica simulada"},
        ]) as llm:
            analysis = agent_nodes.analizar_real(lote)["600"]
            faq = agent_nodes.faq_real({"interacciones_seleccionadas": lote["interacciones"], "fuentes": ["600"]})
        output = {**decision(), **analysis, "respuesta": faq["copy"]}
        self.assertEqual(faq["fuentes"], ["600"])
        self.assertEqual(llm.call_count, 2)
        with TemporaryDirectory() as tmp:
            cfg = config(Path(tmp) / "bot.sqlite3")
            transport = NS(prepare=AsyncMock(return_value=object()), send=AsyncMock(return_value="800"))
            engine = Engine(cfg, Store(cfg.database), AsyncMock(return_value=output), transport)
            await engine.submit(event)
            while await engine.step():
                pass
            self.assertEqual(transport.send.call_args.args[1]["content"], faq["copy"])
            self.assertEqual(transport.send.call_args.args[1]["channel_id"], 200)

    async def test_current_graph_four_routes_keep_block_out_of_public_assets(self):
        events = [source(str(mid)) for mid in range(600, 604)]
        signals = {
            e["message_id"]: {"es_logro": i == 0, "es_duda": i in (1, 2), "es_bloqueo": i == 3,
                              "tema": "python", "relevancia": 0.9}
            for i, e in enumerate(events)
        }
        events[2]["author_id"] = "701"
        request = IngestaRequest(origen_comunidad="discord_prueba", periodo_referencia="2026-W41",
                                interacciones=[interaction(e) for e in events]).model_dump()
        request["cierre_periodo"] = True
        result = ejecutar_lote(request, crear_componentes(signals))
        self.assertEqual(result["errores"], [])
        self.assertTrue(result["simulado"])
        self.assertEqual({d["ruta"] for d in result["enrutamiento"]["decisiones"]},
                         {"logro", "dudas", "periodo", "bloqueo"})
        self.assertEqual(result["alertas_internas"][0]["fuente"], "603")
        self.assertTrue(all("603" not in a["fuentes"] for a in result["activos_distribucion_generados"]))

    async def test_generated_assets_are_not_accepted_as_bot_replies(self):
        # El grafo genera borradores para curaduría; no son respuestas autorizadas al canal.
        with self.assertRaises(ValueError):
            validate_decision({"id_activo": "x", "formato": "faq", "copy": "borrador",
                               "fuentes": ["600"], "estado": "borrador"}, source())
