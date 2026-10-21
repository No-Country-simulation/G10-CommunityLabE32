"""Advertencias de fidelidad del texto ACTUAL de un activo (las del grafo se calculan al generarlo).

Se recalculan al editar el texto y con `python -m backend.scripts.recalcular_fidelidad`, para que siempre
correspondan a la versión vigente. Sin IA: mismas reglas deterministas que usa el grafo.
"""
from pipelines.communitylab.generadores.fidelidad import revisar_fidelidad

# Formato del activo en curaduría -> formato del generador que lo produjo.
FORMATO_GENERADOR = {"linkedin": "post_linkedin_x", "faq": "faq_tip_tecnico", "newsletter": "community_highlights"}


def advertencias_de(copy, formato_activo, fuentes, origen=None, periodo=None):
    """`fuentes`: dicts con id, autor, canal, fecha y texto de los mensajes fuente."""
    formato = FORMATO_GENERADOR.get(formato_activo)
    if formato is None:
        return []
    contexto = tuple(v for v in (origen, periodo) if v)
    return revisar_fidelidad(copy, fuentes, formato, contexto=contexto)
