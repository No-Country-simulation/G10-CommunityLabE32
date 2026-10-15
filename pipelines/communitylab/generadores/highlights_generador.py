"""Generador de resumen Community Highlights del período (formato 'community_highlights')."""
from typing import Any, Dict

from ._comun import generar
from .prompts.highlights_prompt import HIGHLIGHTS_SYSTEM_PROMPT, format_highlights_user_prompt


def generar_highlights(peticion: Dict[str, Any], cliente) -> Dict[str, Any]:
    """Devuelve {'copy', 'fuentes'} para la petición del grafo usando Gemini."""
    return generar(peticion, cliente, formato="community_highlights", sistema=HIGHLIGHTS_SYSTEM_PROMPT, formatear_usuario=format_highlights_user_prompt)
