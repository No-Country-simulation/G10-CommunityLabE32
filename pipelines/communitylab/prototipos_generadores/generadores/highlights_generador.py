"""
Generador de activos para el formato 'community_highlights'.
Integra logros de múltiples autores en una narrativa colectiva cohesiva.
"""

from typing import Dict, Any, List
from config import get_llm_client, DEFAULT_MODEL, TEMPERATURE, MAX_OUTPUT_TOKENS
from prompts.highlights_prompt import (
    HIGHLIGHTS_SYSTEM_PROMPT,
    format_highlights_user_prompt,
)

def limpiar_salida_highlights(texto_generado: str) -> str:
    """
    Limpia cualquier preámbulo o delimitador residual generado por el LLM.
    """
    if not texto_generado:
        return ""

    limpio = texto_generado.strip()

    # Remover envolturas de bloques markdown
    if limpio.startswith("```") and limpio.endswith("```"):
        lineas = limpio.splitlines()
        if len(lineas) >= 2:
            limpio = "\n".join(lineas[1:-1]).strip()

    return limpio

def generar_highlights(contrato: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el flujo generativo para sintetizar los hitos del periodo.
    
    :param contrato: Diccionario de entrada con múltiples interacciones y fuentes.
    :return: Diccionario estricto {'copy': str, 'fuentes': List[str]}.
    """
    interacciones: List[Dict[str, Any]] = contrato.get("interacciones", [])
    fuentes_entrada: List[str] = list(contrato.get("fuentes", []))
    periodo: str = contrato.get("periodo_referencia", "")
    comunidad: str = contrato.get("origen_comunidad", "")

    # Serializar las contribuciones de los autores
    contenido_usuario = format_highlights_user_prompt(
        interacciones=interacciones,
        periodo_referencia=periodo,
        origen_comunidad=comunidad
    )

    try:
        from google.genai import types
        client = get_llm_client()

        configuracion = types.GenerateContentConfig(
            system_instruction=HIGHLIGHTS_SYSTEM_PROMPT,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        respuesta = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=contenido_usuario,
            config=configuracion,
        )

        texto_crudo = respuesta.text or ""
        copy_final = limpiar_salida_highlights(texto_crudo)

    except Exception as error_highlights:
        raise RuntimeError(
            f"Fallo durante la invocación del modelo Gemini para 'community_highlights': {error_highlights}"
        ) from error_highlights

    if not copy_final:
        raise ValueError("El modelo Gemini devolvió una respuesta vacía para 'community_highlights'.")

    return {
        "copy": copy_final,
        "fuentes": fuentes_entrada,
    }