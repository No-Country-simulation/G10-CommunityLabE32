"""Análisis y puntuación reales con Gemini (contrato de Santiago, ver docs/historial/contratos/CONTRATO_PARA_SANTIAGO.md).

Reemplazan a analizar_real/puntuar_real de OpenRouter. Procesan el lote por bloques
(GEMINI_TAMANO_BLOQUE) y exigen exactamente un resultado por ID del bloque.

Alias por bloque: Gemini nunca recibe los IDs originales (p. ej. «discord-<snowflake>», 27
caracteres). Cada bloque usa alias cortos «m01», «m02»… en el contexto y en el enum del esquema, y
la respuesta se traduce de vuelta con el mapa de ese bloque, por alias y nunca por posición. Un
esquema con muchos IDs largos en el enum y un array de longitud fija es rechazado por el proveedor
(HTTP 400 INVALID_ARGUMENT; trabajo 7e2f5d03 del 19-10-2026, reproducido con datos ficticios). Los
IDs originales no salen de la aplicación ni cambian: los alias solo existen dentro de una llamada.
"""
import json
import math
import re

from .gemini import RespuestaInvalidaIA, RespuestaTruncadaIA

SISTEMA_ANALISIS = (
    "Eres analista de una comunidad tecnológica. Clasifica cada mensaje en español.\n"
    "- es_logro: comparte un hito, certificación, empleo o avance concreto.\n"
    "- es_duda: plantea una consulta técnica o pide ayuda para resolver algo.\n"
    "- es_bloqueo: expresa que no puede avanzar o una frustración que requiere apoyo.\n"
    "- tema: 1 a 4 palabras en minúsculas, en español correcto y con sus tildes "
    "(«certificación», «sesión de práctica»). Usa exactamente la misma cadena para mensajes "
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
# Presupuesto de salida por bloque (ver _bloque_efectivo), calibrado con usageMetadata real del 19-10-2026
# (gemini-3.5-flash-lite, 19 mensajes, sin tokens de razonamiento informados): analizar ≈ 68 tokens por
# resultado y puntuar ≈ 19. Se estiman con margen (80 y 40) más una reserva fija por llamada. Con
# maxOutputTokens=2048 resultan bloques de 22 (analizar) y 40 (puntuar, acotado por GEMINI_TAMANO_BLOQUE).
TOKENS_POR_RESULTADO = {"analizar": 80, "puntuar": 40}
TOKENS_RESERVA = {"analizar": 256, "puntuar": 256}


def _bloques(interacciones, tamano):
    for inicio in range(0, len(interacciones), tamano):
        yield interacciones[inicio:inicio + tamano]


def _ids(bloque):
    ids = [m["id"] for m in bloque]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("IDs de interacción inválidos o duplicados")
    return ids


def _alias(ids):
    """(alias en el mismo orden que ids, mapa alias -> ID original). Cortos y únicos dentro del bloque."""
    ancho = max(2, len(str(len(ids))))
    alias = [f"m{n:0{ancho}d}" for n in range(1, len(ids) + 1)]
    return alias, dict(zip(alias, ids))


_FORMATO_ALIAS = re.compile(r"m\d{2,}")


def _restaurar(mapa_por_alias, originales):
    """Mapa por alias validado -> mapa por ID original. Rechaza cualquier clave que no sea un alias del bloque."""
    if any(not isinstance(a, str) or not _FORMATO_ALIAS.fullmatch(a) or a not in originales for a in mapa_por_alias):
        raise ValueError("Alias desconocido o con formato incorrecto")
    return {originales[a]: v for a, v in mapa_por_alias.items()}


def _esquema(ids, propiedades):
    """Esquema de respuesta por bloque. Sin minItems/maxItems: un array de longitud fija combinado con
    el enum de IDs volvió el esquema demasiado complejo para el proveedor (400 con 40 alias). La
    cardinalidad exacta (un resultado por ID, sin duplicados ni faltantes) la garantiza _por_id."""
    id_esquema = {"type": "string"}
    if len(ids) <= ENUM_IDS_MAXIMO:
        id_esquema["enum"] = list(ids)
    item = {"type": "object", "properties": {"id": id_esquema, **propiedades},
            "required": ["id", *propiedades], "additionalProperties": False}
    return {"type": "object", "properties": {"resultados": {"type": "array", "items": item}},
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


def _bloque_efectivo(cliente, tarea):
    """Tamaño de bloque que cabe en el límite de salida configurado (sin subirlo), acotado por GEMINI_TAMANO_BLOQUE.

    Con 40 resultados por bloque, analizar superó maxOutputTokens=2048 (MAX_TOKENS, 19-10-2026). El límite por
    llamada sigue siendo cliente.cfg.max_tokens_salida (máximo explícito); se reservan TOKENS_RESERVA para el
    razonamiento y el envoltorio JSON, y cada resultado se estima en TOKENS_POR_RESULTADO[tarea].
    """
    disponible = cliente.cfg.max_tokens_salida - TOKENS_RESERVA[tarea]
    return max(1, min(cliente.cfg.tamano_bloque, disponible // TOKENS_POR_RESULTADO[tarea]))


def _por_bloques(interacciones, cliente, tarea, llamar):
    """Ejecuta llamar(bloque) por bloques; si un bloque se trunca, lo divide en dos UNA sola vez.

    Sin recursión ni repetición de bloques completados: cada bloque original se divide como máximo una vez
    y una mitad truncada termina el trabajo con RespuestaInvalidaIA (sin resultados parciales, porque el
    nodo falla entero). Cada petición sigue pasando por el presupuesto de llamadas, tokens y tiempo.
    """
    salida = {}
    pendientes = [(b, False) for b in _bloques(interacciones, _bloque_efectivo(cliente, tarea))]
    while pendientes:
        bloque, ya_dividido = pendientes.pop(0)
        try:
            salida.update(llamar(bloque))
        except RespuestaTruncadaIA:
            if ya_dividido or len(bloque) < 2:
                raise RespuestaInvalidaIA("truncado") from None
            mitad = len(bloque) // 2
            pendientes[0:0] = [(bloque[:mitad], True), (bloque[mitad:], True)]
    return salida


def analizar(lote, cliente):
    """Mapa por ID con es_logro, es_duda, es_bloqueo (bool), tema (str) y, si es válido, sentimiento."""
    def llamar(bloque):
        alias, originales = _alias(_ids(bloque))
        contexto = [{"id": a, "canal": m["canal"], "texto": m["texto"],
                     **({"tipo_sugerido": m["tipo"]} if m.get("tipo") else {})} for a, m in zip(alias, bloque)]
        esquema = _esquema(alias, {"es_logro": {"type": "boolean"}, "es_duda": {"type": "boolean"},
                                   "es_bloqueo": {"type": "boolean"}, "tema": {"type": "string"},
                                   "sentimiento": {"type": "string", "enum": list(SENTIMIENTOS)}})

        def validar(objeto):
            resultado = {}
            # El sentimiento es secundario: si falta o sale del contrato, ese mensaje queda
            # "sin analizar" (nunca neutral) y el lote sigue; las señales sí son obligatorias.
            por_alias = _por_id(objeto, alias, ("es_logro", "es_duda", "es_bloqueo", "tema"), ("sentimiento",))
            for i, r in _restaurar(por_alias, originales).items():
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

        return cliente.generar_json("analizar", SISTEMA_ANALISIS, json.dumps(contexto, ensure_ascii=False),
                                    esquema, validar, escalar_si_trunca=False)
    return _por_bloques(lote["interacciones"], cliente, "analizar", llamar)


def puntuar(peticion, cliente):
    """Mapa por ID con relevancia finita entre 0 y 1."""
    analisis = peticion["analisis"]

    def llamar(bloque):
        alias, originales = _alias(_ids(bloque))
        contexto = [{"id": a, "texto": m["texto"], "senales": analisis.get(m["id"], {})}
                    for a, m in zip(alias, bloque)]
        esquema = _esquema(alias, {"relevancia": {"type": "number", "minimum": 0, "maximum": 1}})

        def validar(objeto):
            resultado = {}
            for i, r in _restaurar(_por_id(objeto, alias, ("relevancia",)), originales).items():
                valor = r["relevancia"]
                if type(valor) not in (int, float) or not math.isfinite(valor) or not 0 <= valor <= 1:
                    raise ValueError("Relevancia fuera de rango")
                resultado[i] = float(valor)
            return resultado

        return cliente.generar_json("puntuar", SISTEMA_PUNTUACION, json.dumps(contexto, ensure_ascii=False),
                                    esquema, validar, escalar_si_trunca=False)
    return _por_bloques(peticion["lote"]["interacciones"], cliente, "puntuar", llamar)
