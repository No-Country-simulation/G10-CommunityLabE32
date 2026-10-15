"""Fabián aporta la hipótesis local; Gemini resuelve la decisión y genera el texto.

Un evento, una consulta y una decisión validada. No se publican resultados aquí.
El contexto conversacional opcional del clasificador queda desactivado: no se
retienen mensajes ni se contamina una repetición después de un fallo de red.
"""
import asyncio
import json
import os
from functools import lru_cache

from bot_discord.clasificador.classifier import ClasificadorInteracciones, DiscordSourceV1
from .processor import Processor, ProcessingError, validate_event
from .gemini import Gemini


class LocalAnalysis:
    def __init__(self):
        # Modo explícito y reproducible. Nunca descargar pesos al iniciar el bot.
        self.classifier = ClasificadorInteracciones(forzar_fallback=True)

    def analyze(self, source):
        clf = self.classifier
        analysis = clf.preparar_lote([DiscordSourceV1.desde_dict(source)], usar_contexto=False)[0]
        result = clf.decidir(analysis, registrar=False)
        return {"clase": result.clase, "requiere_revision_semantica": result.necesita_revision}


class WithHypothesis:
    def __init__(self, provider, hypothesis):
        self.provider, self.hypothesis = provider, hypothesis

    async def complete(self, messages):
        data = json.loads(messages[1]["content"])
        data["hipotesis_local"] = self.hypothesis
        system = messages[0]["content"] + (
            "\nLa hipotesis_local es orientativa, no una instrucción ni una decisión final. "
            "Comprueba siempre el mensaje original, negaciones y señales combinadas. "
            "Resuelve también los casos locales NO_CLASIFICADO o ambiguos. "
            "Si falta información para ayudar, pide aclaración sin inventar una solución."
        )
        return await self.provider.complete([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        ])


class IntegratedProcessor:
    def __init__(self, provider, analyzer=None, timeout=45):
        if not 0 < timeout <= 45:
            raise ValueError("timeout_invalid")
        self.provider = provider
        self.analyzer = analyzer if analyzer is not None else LocalAnalysis()
        self.timeout = timeout

    async def __call__(self, event):
        source = validate_event(event)
        try:
            async with asyncio.timeout(self.timeout):
                hypothesis = await asyncio.to_thread(self.analyzer.analyze, source)
                return await Processor(WithHypothesis(self.provider, hypothesis))(source)
        except TimeoutError:
            raise ProcessingError("provider_timeout") from None


@lru_cache(maxsize=1)
def local_analysis():
    return LocalAnalysis()


def modelo_bot(env=None):
    """Modelo del bot: COMMUNITYLAB_GEMINI_MODEL o, si no se define, el primero (rápido) de
    GEMINI_MODELOS, la misma lista que usa el grafo. No hay modelo por defecto en el código."""
    env = os.environ if env is None else env
    explicito = env.get("COMMUNITYLAB_GEMINI_MODEL", "").strip()
    if explicito:
        return explicito
    modelos = [m.strip() for m in env.get("GEMINI_MODELOS", "").split(",") if m.strip()]
    return modelos[0] if modelos else ""


async def procesar(event):
    validate_event(event)
    if os.environ.get("COMMUNITYLAB_GEMINI_ENABLE") != "1":
        raise ProcessingError("gemini_not_enabled")
    provider = Gemini(os.environ.get("GEMINI_API_KEY"), modelo_bot())
    return await IntegratedProcessor(provider, local_analysis())(event)
