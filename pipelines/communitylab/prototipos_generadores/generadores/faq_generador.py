"""
Generador de activos para el formato 'faq_tip_tecnico'.
Consolida múltiples interacciones de dudas en una estructura única de FAQ.
"""

from typing import Dict, Any, List
from config import get_llm_client, DEFAULT_MODEL, TEMPERATURE, MAX_OUTPUT_TOKENS
from prompts.fag_prompt import (
    FAQ_TIP_SYSTEM_PROMPT,
    format_faq_user_prompt,
)

def limpiar_salida_faq(texto_generado: str) -> str:
    """
    Limpia y valida que la salida del modelo para FAQ conserve la estructura esperada.
    """
    if not texto_generado:
        return ""

    limpio = texto_generado.strip()

    # Remover envolturas en bloques de código markdown
    if limpio.startswith("```") and limpio.endswith("```"):
        lineas = limpio.splitlines()
        if len(lineas) >= 2:
            limpio = "\n".join(lineas[1:-1]).strip()

    return limpio

def generar_faq(contrato: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el flujo generativo para crear una entrada de FAQ técnica consolidada.
    
    :param contrato: Diccionario de entrada verificado por el router.
    :return: Diccionario con formato {'copy': str, 'fuentes': List[str]}.
    """
    interacciones: List[Dict[str, Any]] = contrato.get("interacciones", [])
    fuentes_entrada: List[str] = list(contrato.get("fuentes", []))
    periodo: str = contrato.get("periodo_referencia", "")
    comunidad: str = contrato.get("origen_comunidad", "")

    # Construir el contenido de usuario estructurado
    contenido_usuario = format_faq_user_prompt(
        interacciones=interacciones,
        periodo_referencia=periodo,
        origen_comunidad=comunidad
    )

    try:
        from google.genai import types
        client = get_llm_client()

        configuracion = types.GenerateContentConfig(
            system_instruction=FAQ_TIP_SYSTEM_PROMPT,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        respuesta = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=contenido_usuario,
            config=configuracion,
        )

        texto_crudo = respuesta.text or ""
        copy_final = limpiar_salida_faq(texto_crudo)

    except Exception as error_faq:
        raise RuntimeError(
            f"Fallo durante la invocación del modelo Gemini para 'faq_tip_tecnico': {error_faq}"
        ) from error_faq

    if not copy_final:
        raise ValueError("El modelo Gemini devolvió una respuesta vacía para 'faq_tip_tecnico'.")

    return {
        "copy": copy_final,
        "fuentes": fuentes_entrada,
    }
