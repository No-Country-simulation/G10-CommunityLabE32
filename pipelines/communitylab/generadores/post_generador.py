"""Generador de publicaciones de logros en LinkedIn/X (formato 'post_linkedin_x')."""
from typing import Any, Dict

from ._comun import generar
from .prompts.post_linkedin_prompt import POST_LINKEDIN_SYSTEM_PROMPT, format_post_user_prompt


def generar_post(peticion: Dict[str, Any], cliente) -> Dict[str, Any]:
    """Devuelve {'copy', 'fuentes'} para la petición del grafo usando Gemini."""
    return generar(peticion, cliente, formato="post_linkedin_x", sistema=POST_LINKEDIN_SYSTEM_PROMPT, formatear_usuario=format_post_user_prompt)
