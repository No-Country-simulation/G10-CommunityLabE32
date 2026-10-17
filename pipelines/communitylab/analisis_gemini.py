"""Análisis y puntuación reales con Gemini (contrato de Santiago, ver CONTRATO_PARA_SANTIAGO.md).

Reemplazan a analizar_real/puntuar_real de OpenRouter. Procesan el lote por bloques
(GEMINI_TAMANO_BLOQUE) y exigen exactamente un resultado por ID del bloque.
"""
import json
import math

SISTEMA_ANALISIS = (
    "Eres analista de una comunidad tecnológica. Clasifica cada mensaje en español.\n"
    "- es_logro: comparte un hito, certificación, empleo o avance concreto.\n"
    "- es_duda: plantea una consulta técnica o pide ayuda para resolver algo.\n"
    "- es_bloqueo: expresa que no puede avanzar o una frustración que requiere apoyo.\n"
    "- tema: 1 a 4 palabras en minúsculas. Usa exactamente la misma cadena para mensajes "
    "sobre el mismo asunto. Si es una duda, el tema no puede quedar vacío.\n"
    "- sentimiento: tono expresado en el propio mensaje: positivo, negativo, neutral o "
    "indeterminado (si el tono no se puede determinar con el texto). Es independiente de la "
    "intención: una duda o un bloqueo no son negativos por sí mismos; una pregunta neutral es "
    "neutral. No infieras estados psicológicos ni rasgos de la persona.\n"
    "Devuelve un resultado por cada id recibido, sin omitir ni inventar ids."
)
SENTIMIENTOS = ("positivo", "negativo", "neutral", "indeterminado")
VERSION_SENTIMIENTO = "gemini-analizar-v1"
SISTEMA_PUNTUACION = (
    "Evalúa la relevancia comunitaria de cada mensaje entre 0.0 y 1.0. Asigna más de 0.60 "
    "solo a hitos concretos, dudas útiles para otros o problemas graves; saludos y mensajes "
    "sin contenido van por debajo de 0.30. Una duda que repite o confirma otra duda del mismo "
    "tema en el lote es útil: indica recurrencia y debe puntuarse igual que la original. "
    "Devuelve un resultado por cada id recibido, sin "
    "omitir ni inventar ids."
)
MAX_TEMA = 80
ENUM_IDS_MAXIMO = 50  # Esquemas muy grandes pueden ser rechazados; la validación local es la garantía.


def _bloques(interacciones, tamano):
    for inicio in range(0, len(interacciones), tamano):
        yield interacciones[inicio:inicio + tamano]


def _ids(bloque):
    ids = [m["id"] for m in bloque]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("IDs de interacción inválidos o duplicados")
    return ids


def _esquema(ids, propiedades):
    id_esquema = {"type": "string"}
    if len(ids) <= ENUM_IDS_MAXIMO:
        id_esquema["enum"] = list(ids)
    item = {"type": "object", "properties": {"id": id_esquema, **propiedades},
            "required": ["id", *propiedades], "additionalProperties": False}
    return {"type": "object", "properties": {"resultados": {"type": "array", "items": item,
            "minItems": len(ids), "maxItems": len(ids)}},
            "required": ["resultados"], "additionalProperties": False}


def _por_id(objeto, ids, campos, opcionales=()):
    if not isinstance(objeto, dict) or set(objeto) != {"resultados"} or not isinstance(objeto["resultados"], list):
        raise ValueError("Se esperaba {'resultados': [...]}")
    mapa = {}
    for r in objeto["resultados"]:
        if not isinstance(r, dict) or not {"id", *campos} <= set(r) <= {"id", *campos, *opcionales}:
            raise ValueError("Campos de resultado inválidos")
        if r["id"] not in ids or r["id"] in mapa:
            raise ValueError("ID inventado o duplicado")
        mapa[r["id"]] = r
    if set(mapa) != set(ids):
        raise ValueError("Faltan resultados para algunos IDs")
    return mapa


def analizar(lote, cliente):
    """Mapa por ID con es_logro, es_duda, es_bloqueo (bool), tema (str) y, si es válido, sentimiento."""
    salida = {}
    for bloque in _bloques(lote["interacciones"], cliente.cfg.tamano_bloque):
        ids = _ids(bloque)
        contexto = [{"id": m["id"], "canal": m["canal"], "texto": m["texto"],
                     **({"tipo_sugerido": m["tipo"]} if m.get("tipo") else {})} for m in bloque]
        esquema = _esquema(ids, {"es_logro": {"type": "boolean"}, "es_duda": {"type": "boolean"},
                                 "es_bloqueo": {"type": "boolean"}, "tema": {"type": "string"},
                                 "sentimiento": {"type": "string", "enum": list(SENTIMIENTOS)}})

        def validar(objeto, ids=ids):
            resultado = {}
            # El sentimiento es secundario: si falta o sale del contrato, ese mensaje queda
            # "sin analizar" (nunca neutral) y el lote sigue; las señales sí son obligatorias.
            for i, r in _por_id(objeto, ids, ("es_logro", "es_duda", "es_bloqueo", "tema"),
                                ("sentimiento",)).items():
                if any(type(r[k]) is not bool for k in ("es_logro", "es_duda", "es_bloqueo")):
                    raise ValueError("Las señales deben ser booleanos")
                if not isinstance(r["tema"], str) or len(r["tema"]) > MAX_TEMA:
                    raise ValueError("Tema inválido")
                tema = " ".join(r["tema"].lower().split())
                if r["es_duda"] and not tema:
                    raise ValueError("Una duda requiere tema")
                resultado[i] = {"es_logro": r["es_logro"], "es_duda": r["es_duda"],
                                "es_bloqueo": r["es_bloqueo"], "tema": tema}
                if r.get("sentimiento") in SENTIMIENTOS:
                    resultado[i]["sentimiento"] = r["sentimiento"]
            return resultado

        salida.update(cliente.generar_json("analizar", SISTEMA_ANALISIS,
                                           json.dumps(contexto, ensure_ascii=False), esquema, validar))
    return salida


def puntuar(peticion, cliente):
    """Mapa por ID con relevancia finita entre 0 y 1."""
    salida = {}
    analisis = peticion["analisis"]
    for bloque in _bloques(peticion["lote"]["interacciones"], cliente.cfg.tamano_bloque):
        ids = _ids(bloque)
        contexto = [{"id": m["id"], "texto": m["texto"], "senales": analisis.get(m["id"], {})} for m in bloque]
        esquema = _esquema(ids, {"relevancia": {"type": "number", "minimum": 0, "maximum": 1}})

        def validar(objeto, ids=ids):
            resultado = {}
            for i, r in _por_id(objeto, ids, ("relevancia",)).items():
                valor = r["relevancia"]
                if type(valor) not in (int, float) or not math.isfinite(valor) or not 0 <= valor <= 1:
                    raise ValueError("Relevancia fuera de rango")
                resultado[i] = float(valor)
            return resultado

        salida.update(cliente.generar_json("puntuar", SISTEMA_PUNTUACION,
                                           json.dumps(contexto, ensure_ascii=False), esquema, validar))
    return salida
