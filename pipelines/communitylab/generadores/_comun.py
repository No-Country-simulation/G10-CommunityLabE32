"""Pasos comunes de los tres generadores: contrato, llamada estructurada y limpieza."""
from .contrato import MAX_COPY, validar_contrato_entrada, validar_contrato_salida

INSTRUCCION_SALIDA = (
    "\n\nFORMATO DE RESPUESTA\n"
    "Devuelve únicamente un objeto JSON con la clave \"copy\", cuyo valor es el texto final "
    "listo para revisión editorial. No incluyas otras claves, comentarios ni bloques de código."
)
ESQUEMA_COPY = {
    "type": "object",
    "properties": {"copy": {"type": "string", "description": "Texto final del activo editorial."}},
    "required": ["copy"],
    "additionalProperties": False,
}


def limpiar_salida_copy(texto: str) -> str:
    """Quita envolturas markdown o comillas externas que el modelo pueda añadir."""
    limpio = texto.strip()
    if limpio.startswith("```") and limpio.endswith("```"):
        lineas = limpio.splitlines()
        limpio = "\n".join(lineas[1:-1]).strip() if len(lineas) >= 2 else ""
    if len(limpio) >= 2 and limpio.startswith('"') and limpio.endswith('"'):
        limpio = limpio[1:-1].strip()
    return limpio


def validar_copy(objeto):
    """Validador local de la respuesta del modelo; un fallo habilita el escalamiento."""
    if not isinstance(objeto, dict) or set(objeto) != {"copy"} or not isinstance(objeto["copy"], str):
        raise ValueError("Respuesta sin 'copy' válido")
    copy = limpiar_salida_copy(objeto["copy"])
    if not copy or len(copy) > MAX_COPY:
        raise ValueError("'copy' vacío o demasiado largo")
    return copy


def generar(peticion, cliente, *, formato, sistema, formatear_usuario):
    validar_contrato_entrada(peticion, formato)
    usuario = formatear_usuario(
        interacciones=peticion["interacciones"],
        periodo_referencia=peticion["periodo_referencia"],
        origen_comunidad=peticion["origen_comunidad"],
    )
    copy = cliente.generar_json(formato, sistema + INSTRUCCION_SALIDA, usuario, ESQUEMA_COPY, validar_copy)
    # Las fuentes nunca las decide el modelo: son exactamente las que seleccionó el router.
    return validar_contrato_salida({"copy": copy, "fuentes": list(peticion["fuentes"])}, peticion)
