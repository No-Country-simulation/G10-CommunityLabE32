"""Versiones LinkedIn y X de un logro, a pedido desde Curaduría (una sola llamada a Gemini).

Reutiliza las reglas editoriales del generador de posts (mismo prompt de sistema y mismo contrato de
entrada): solo cambia el formato de salida, que pide las dos versiones a la vez. La versión X se limita
a 280 caracteres; si el modelo la excede, el validador falla y el cliente escala de modelo.
"""
from typing import Any, Dict

from ._comun import limpiar_salida_copy
from .contrato import MAX_COPY, validar_contrato_entrada
from .prompts.post_linkedin_prompt import POST_LINKEDIN_SYSTEM_PROMPT, format_post_user_prompt

MAX_X = 280
INSTRUCCION_SALIDA = (
    "\n\nFORMATO DE RESPUESTA\n"
    "Devuelve únicamente un objeto JSON con dos claves:\n"
    "- \"linkedin\": la publicación completa para LinkedIn, aplicando todas las reglas anteriores.\n"
    f"- \"x\": una versión para X (Twitter) de como máximo {MAX_X} caracteres, contando hashtags y emojis, "
    "con los mismos hechos y sin agregar datos nuevos.\n"
    "No incluyas otras claves, comentarios ni bloques de código."
)
ESQUEMA_POSTS = {
    "type": "object",
    "properties": {
        "linkedin": {"type": "string", "description": "Publicación para LinkedIn."},
        "x": {"type": "string", "description": f"Publicación para X, máximo {MAX_X} caracteres."},
    },
    "required": ["linkedin", "x"],
    "additionalProperties": False,
}


def validar_posts(objeto):
    """Validador local de la respuesta; un fallo habilita el escalamiento de modelo."""
    if not isinstance(objeto, dict) or set(objeto) != {"linkedin", "x"}:
        raise ValueError("Respuesta sin 'linkedin' y 'x'")
    linkedin, x = (limpiar_salida_copy(objeto[k]) if isinstance(objeto[k], str) else "" for k in ("linkedin", "x"))
    if not linkedin or len(linkedin) > MAX_COPY:
        raise ValueError("'linkedin' vacío o demasiado largo")
    if not x or len(x) > MAX_X:
        raise ValueError(f"'x' vacío o con más de {MAX_X} caracteres")
    return {"linkedin": linkedin, "x": x}


def generar_posts_redes(peticion: Dict[str, Any], cliente) -> Dict[str, str]:
    """Devuelve {'linkedin', 'x'} para una petición con el contrato de 'post_linkedin_x'."""
    validar_contrato_entrada(peticion, "post_linkedin_x")
    usuario = format_post_user_prompt(
        interacciones=peticion["interacciones"],
        periodo_referencia=peticion["periodo_referencia"],
        origen_comunidad=peticion["origen_comunidad"],
    )
    return cliente.generar_json("post_linkedin_x", POST_LINKEDIN_SYSTEM_PROMPT + INSTRUCCION_SALIDA, usuario,
                                ESQUEMA_POSTS, validar_posts)
