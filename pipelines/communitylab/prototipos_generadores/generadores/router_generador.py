from typing import Callable, Dict, Any, List

FORMATOS_SOPORTADOS = {
    "post_linkedin_x",
    "faq_tip_tecnico",
    "community_highlights",
}

CAMPOS_REQUERIDOS = [
    "ruta",
    "formato",
    "origen_comunidad",
    "periodo_referencia",
    "fuentes",
    "interacciones",
]

def validar_contrato_entrada(contrato: Dict[str, Any]) -> None:
    """
    Verifica que el contrato de entrada cumpla estrictamente con la estructura
    y tipos de datos requeridos por la arquitectura del sistema.
    """
    if not isinstance(contrato, dict):
        raise ValueError("El contrato de entrada debe ser un diccionario.")

    # 1. Comprobar presencia de campos requeridos
    for campo in CAMPOS_REQUERIDOS:
        if campo not in contrato:
            raise ValueError(f"Falta campo requerido en el contrato: '{campo}'")

    # 2. Validar formato soportado
    formato = contrato.get("formato")
    if formato not in FORMATOS_SOPORTADOS:
        raise ValueError(
            f"Formato no soportado: '{formato}'. "
            f"Formatos válidos: {list(FORMATOS_SOPORTADOS)}"
        )

    # 3. Validar estructura de fuentes
    fuentes = contrato.get("fuentes")
    if not isinstance(fuentes, list) or len(fuentes) == 0:
        raise ValueError("El campo 'fuentes' debe ser una lista no vacía de identificadores.")
    
    if not all(isinstance(f, str) and f.strip() for f in fuentes):
        raise ValueError("Todos los elementos en 'fuentes' deben ser cadenas de texto no vacías.")

    if len(fuentes) != len(set(fuentes)):
        raise ValueError("El campo 'fuentes' contiene identificadores duplicados.")

    # 4. Validar estructura de interacciones
    interacciones = contrato.get("interacciones")
    if not isinstance(interacciones, list) or len(interacciones) == 0:
        raise ValueError("El campo 'interacciones' debe ser una lista no vacía.")

    ids_interacciones = set()
    for item in interacciones:
        if not isinstance(item, dict):
            raise ValueError("Cada interacción debe ser un diccionario.")
        if "id" not in item or "texto" not in item:
            raise ValueError("Cada interacción debe incluir al menos las claves 'id' y 'texto'.")
        ids_interacciones.add(item["id"])

    # 5. Asegurar correspondencia entre fuentes e interacciones
    fuentes_set = set(fuentes)
    if not fuentes_set.issubset(ids_interacciones):
        faltantes = fuentes_set - ids_interacciones
        raise ValueError(
            f"Existen identificadores en 'fuentes' que no están en 'interacciones': {faltantes}"
        )

def dispatch_generator(
    contrato: Dict[str, Any],
    generadores: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Valida el contrato de entrada y ejecuta la función generadora correspondiente
    según el valor del campo 'formato'.
    
    :param contrato: Diccionario de entrada recibido desde el grafo orquestador.
    :param generadores: Diccionario de funciones {nombre_formato: funcion_generadora}.
    :return: Diccionario estrictamente con las claves {'copy', 'fuentes'}.
    """
    # Validar el contrato de entrada
    validar_contrato_entrada(contrato)

    formato = contrato["formato"]
    if formato not in generadores:
        raise KeyError(
            f"No se ha inyectado una función generadora para el formato '{formato}'."
        )

    funcion_generadora = generadores[formato]
    if not callable(funcion_generadora):
        raise TypeError(
            f"El generador registrado para '{formato}' no es una función ejecutable."
        )

    # Invocación de la función generadora
    resultado = funcion_generadora(contrato)

    # Validación defensiva del contrato de salida
    if not isinstance(resultado, dict) or set(resultado.keys()) != {"copy", "fuentes"}:
        raise ValueError(
            "El generador debe devolver un diccionario estrictamente con las claves 'copy' y 'fuentes'."
        )

    return resultado