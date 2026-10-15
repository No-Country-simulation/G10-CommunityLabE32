"""Generador de FAQ o tip técnico que consolida dudas recurrentes (formato 'faq_tip_tecnico')."""
from typing import Any, Dict

from ._comun import generar
from .prompts.faq_prompt import FAQ_TIP_SYSTEM_PROMPT, format_faq_user_prompt


def generar_faq(peticion: Dict[str, Any], cliente) -> Dict[str, Any]:
    """Devuelve {'copy', 'fuentes'} para la petición del grafo usando Gemini."""
    return generar(peticion, cliente, formato="faq_tip_tecnico", sistema=FAQ_TIP_SYSTEM_PROMPT, formatear_usuario=format_faq_user_prompt)
