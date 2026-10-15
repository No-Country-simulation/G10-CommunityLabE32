"""Contrato de entrada/salida de los generadores (petición que arma el grafo).

Basado en el router de Fabián. La relación fuentes/interacciones es exacta:
cada fuente tiene su interacción y no hay interacciones ajenas a las fuentes.
"""
from typing import Any, Callable, Dict, List

FORMATOS_SOPORTADOS = {"post_linkedin_x", "faq_tip_tecnico", "community_highlights"}
CAMPOS_PETICION = {"ruta", "formato", "origen_comunidad", "periodo_referencia", "fuentes", "interacciones"}
CAMPOS_INTERACCION = ("id", "autor", "canal", "fecha", "texto")
MAX_INTERACCIONES = 200
MAX_TEXTO = 4000
MAX_COPY = 6000


def _texto(valor, nombre, maximo=None):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"'{nombre}' debe ser texto no vacío.")
    if maximo is not None and len(valor) > maximo:
        raise ValueError(f"'{nombre}' supera {maximo} caracteres.")
    return valor


def validar_contrato_entrada(contrato: Dict[str, Any], formato: str | None = None) -> None:
    """Valida la petición del grafo antes de gastar presupuesto de IA."""
    if not isinstance(contrato, dict):
        raise ValueError("El contrato de entrada debe ser un diccionario.")
    faltantes = CAMPOS_PETICION - set(contrato)
    if faltantes:
        raise ValueError(f"Faltan campos requeridos: {sorted(faltantes)}")
    if contrato["formato"] not in FORMATOS_SOPORTADOS:
        raise ValueError("Formato no soportado.")
    if formato is not None and contrato["formato"] != formato:
        raise ValueError("La petición corresponde a otro generador.")
    for campo in ("ruta", "origen_comunidad", "periodo_referencia"):
        _texto(contrato[campo], campo, 200)

    fuentes = contrato["fuentes"]
    if not isinstance(fuentes, list) or not fuentes:
        raise ValueError("'fuentes' debe ser una lista no vacía.")
    for fuente in fuentes:
        _texto(fuente, "fuentes", 200)
    if len(fuentes) != len(set(fuentes)):
        raise ValueError("'fuentes' contiene identificadores duplicados.")

    interacciones = contrato["interacciones"]
    if not isinstance(interacciones, list) or not interacciones:
        raise ValueError("'interacciones' debe ser una lista no vacía.")
    if len(interacciones) > MAX_INTERACCIONES:
        raise ValueError(f"Máximo {MAX_INTERACCIONES} interacciones por petición.")
    ids: List[str] = []
    for item in interacciones:
        if not isinstance(item, dict):
            raise ValueError("Cada interacción debe ser un diccionario.")
        for campo in CAMPOS_INTERACCION:
            _texto(item.get(campo), campo, MAX_TEXTO if campo == "texto" else 200)
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("'interacciones' contiene IDs duplicados.")
    if set(ids) != set(fuentes):
        raise ValueError("'fuentes' e 'interacciones' deben referirse exactamente a los mismos IDs.")


def validar_contrato_salida(resultado: Any, contrato: Dict[str, Any]) -> Dict[str, Any]:
    """Salida estricta {'copy', 'fuentes'}: copy no vacío y exactamente las fuentes recibidas."""
    if not isinstance(resultado, dict) or set(resultado) != {"copy", "fuentes"}:
        raise ValueError("El generador debe devolver exactamente 'copy' y 'fuentes'.")
    _texto(resultado["copy"], "copy", MAX_COPY)
    fuentes = resultado["fuentes"]
    if (not isinstance(fuentes, list) or any(not isinstance(f, str) for f in fuentes)
            or len(fuentes) != len(set(fuentes)) or set(fuentes) != set(contrato["fuentes"])):
        raise ValueError("El generador cambió, omitió, duplicó o inventó fuentes.")
    return resultado


def dispatch_generator(
    contrato: Dict[str, Any],
    generadores: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]],
) -> Dict[str, Any]:
    """Valida la petición, ejecuta el generador de su formato y valida la salida."""
    validar_contrato_entrada(contrato)
    funcion = generadores.get(contrato["formato"])
    if not callable(funcion):
        raise KeyError("No hay un generador ejecutable para el formato solicitado.")
    return validar_contrato_salida(funcion(contrato), contrato)
