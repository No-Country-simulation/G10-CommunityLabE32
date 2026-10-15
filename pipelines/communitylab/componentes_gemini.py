"""Ensambla los Componentes canónicos del grafo con Gemini (simulado=False).

Los cinco componentes son reales y comparten un ClienteGemini, es decir, un único
presupuesto por trabajo. Para pruebas sin red se inyecta `transporte`; para
simulación explícita se usa simulados.crear_componentes (simulado=True).
"""
from functools import partial
import time

from .analisis_gemini import analizar, puntuar
from .gemini import ClienteGemini, ConfiguracionGemini
from .generadores import generar_faq, generar_highlights, generar_post
from .grafo import Componentes


def crear_componentes_gemini(configuracion=None, *, transporte=None, reloj=time.monotonic, dormir=time.sleep):
    cfg = ConfiguracionGemini.desde_entorno() if configuracion is None else configuracion
    cliente = ClienteGemini(cfg, transporte=transporte, reloj=reloj, dormir=dormir)
    return Componentes(
        analizar=partial(analizar, cliente=cliente),
        puntuar=partial(puntuar, cliente=cliente),
        generar_post=partial(generar_post, cliente=cliente),
        generar_faq=partial(generar_faq, cliente=cliente),
        generar_highlights=partial(generar_highlights, cliente=cliente),
        simulado=False,
    )
