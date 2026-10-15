"""
Generador de activos para el formato 'post_linkedin_x'.
Consume el cliente Gemini y retorna estrictamente el contrato {'copy', 'fuentes'}.
"""

from typing import Dict, Any, List
from config import get_llm_client, DEFAULT_MODEL, TEMPERATURE, MAX_OUTPUT_TOKENS
from prompts.post_linkedin_prompt import (
    POST_LINKEDIN_SYSTEM_PROMPT,
    format_post_user_prompt,
)

def limpiar_salida_copy(texto_generado: str) -> str:
    """
    Elimina preámbulos, comillas envolventes innecesarias o bloques de código markdown
    que pudieran ser insertados por el modelo de lenguaje.
    """
    if not texto_generado:
        return ""

    limpio = texto_generado.strip()

    # Remover bloques de código markdown si el LLM envolvió la respuesta en ```
    if limpio.startswith("```") and limpio.endswith("```"):
        lineas = limpio.splitlines()
        if len(lineas) >= 2:
            limpio = "\n".join(lineas[1:-1]).strip()

    # Remover comillas dobles externas si el modelo encerró todo en comillas
    if limpio.startswith('"') and limpio.endswith('"') and len(limpio) >= 2:
        limpio = limpio[1:-1].strip()

    return limpio

def generar_post(contrato: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el flujo generativo para publicaciones de logros en LinkedIn/X.
    
    :param contrato: Diccionario validado por el router con los campos del evento.
    :return: Diccionario estricto {'copy': str, 'fuentes': List[str]}.
    """
    interacciones: List[Dict[str, Any]] = contrato.get("interacciones", [])
    fuentes_entrada: List[str] = list(contrato.get("fuentes", []))
    periodo: str = contrato.get("periodo_referencia", "")
    comunidad: str = contrato.get("origen_comunidad", "")

    # Construir el contenido contextual del usuario
    contenido_usuario = format_post_user_prompt(
        interacciones=interacciones,
        periodo_referencia=periodo,
        origen_comunidad=comunidad
    )

    try:
        from google.genai import types
        client = get_llm_client()

        configuracion_llamada = types.GenerateContentConfig(
            system_instruction=POST_LINKEDIN_SYSTEM_PROMPT,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        respuesta = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=contenido_usuario,
            config=configuracion_llamada,
        )

        texto_crudo = respuesta.text or ""
        copy_final = limpiar_salida_copy(texto_crudo)

    except Exception as error_generacion:
        raise RuntimeError(
            f"Fallo durante la invocación del modelo Gemini para 'post_linkedin_x': {error_generacion}"
        ) from error_generacion

    if not copy_final:
        raise ValueError("El modelo Gemini devolvió una respuesta vacía para 'post_linkedin_x'.")

    return {
        "copy": copy_final,
        "fuentes": fuentes_entrada,
    }