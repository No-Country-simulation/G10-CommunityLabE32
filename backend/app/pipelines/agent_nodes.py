import os
import json
import requests


# ==========================================
# MOTOR LLM CON FALLBACK (OPENROUTER)
# ==========================================
def llamar_llm_openrouter(prompt: str) -> dict:
    """Llama a OpenRouter y devuelve un objeto JSON validado."""
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

    payload = {
        "models": [
            "meta-llama/llama-3-8b-instruct",
            "deepseek/deepseek-chat",
        ],
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": (
                    "https://github.com/No-Country-simulation/"
                    "G10-CommunityLabE32"
                ),
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValueError(
            "Respuesta de OpenRouter no disponible o inválida"
        ) from exc

    if not isinstance(data, dict) or not data.get("choices"):
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

    try:
        contenido_str = data["choices"][0]["message"].get("content", "")
    except (KeyError, AttributeError, TypeError) as exc:
        raise ValueError(
            "Respuesta de OpenRouter no disponible o inválida"
        ) from exc

    contenido_str = (
        contenido_str.replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        resultado = json.loads(contenido_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Respuesta de OpenRouter no disponible o inválida"
        ) from exc

    if not isinstance(resultado, dict):
        raise ValueError("OpenRouter debe devolver un objeto JSON")

    return resultado

# ==========================================
# VALIDACIONES COMUNES
# ==========================================
def _ids_interacciones(interacciones: list[dict]) -> set:
    """Obtiene los IDs esperados y rechaza interacciones sin ID."""
    ids = set()

    for mensaje in interacciones:
        msg_id = mensaje.get("id")

        if not msg_id:
            raise ValueError("Interacción sin ID")

        if msg_id in ids:
            raise ValueError(f"ID de interacción duplicado: {msg_id}")

        ids.add(msg_id)

    return ids


# ==========================================
# NODO DE CLASIFICACIÓN
# ==========================================
def analizar_real(lote: dict) -> dict:
    """Devuelve un mapa por ID con clasificación y tema."""
    interacciones = lote.get("interacciones", [])
    ids_esperados = _ids_interacciones(interacciones)

    contexto = [
        {"id": m.get("id"), "texto": m.get("texto")}
        for m in interacciones
    ]

    prompt = f"""
    Siempre responde en español.
    Evalúa estos mensajes y devuelve un JSON estricto con una clave
    'resultados' que contenga una lista de objetos.

    Cada objeto DEBE tener exactamente estas claves:
    - 'id': mantener el ID original.
    - 'es_logro': bool (True si comparte un hito o éxito).
    - 'es_duda': bool (True si es consulta técnica).
    - 'es_bloqueo': bool (True si expresa frustración o no puede avanzar).
    - 'tema': string breve (normaliza temas similares bajo la misma cadena).

    Mensajes: {json.dumps(contexto, ensure_ascii=False)}
    """

    respuesta = llamar_llm_openrouter(prompt)
    lista_resultados = respuesta.get("resultados", [])

    if not isinstance(lista_resultados, list):
        raise ValueError("Resultados de análisis inválidos")

    mapa = {}

    for resultado in lista_resultados:
        if not isinstance(resultado, dict):
            raise ValueError("Resultado de análisis inválido")

        msg_id = resultado.get("id", resultado.get("id_mensaje"))

        if not msg_id:
            raise ValueError("Resultado de análisis sin ID")

        if msg_id not in ids_esperados:
            raise ValueError(f"ID de análisis no solicitado: {msg_id}")

        if msg_id in mapa:
            raise ValueError(f"ID de análisis duplicado: {msg_id}")

        if not isinstance(resultado.get("es_logro"), bool):
            raise ValueError("es_logro debe ser booleano")

        if not isinstance(resultado.get("es_duda"), bool):
            raise ValueError("es_duda debe ser booleano")

        if not isinstance(resultado.get("es_bloqueo"), bool):
            raise ValueError("es_bloqueo debe ser booleano")

        mapa[msg_id] = {
            "es_logro": resultado["es_logro"],
            "es_duda": resultado["es_duda"],
            "es_bloqueo": resultado["es_bloqueo"],
            "tema": resultado.get("tema", "General"),
        }

    if set(mapa) != ids_esperados:
        raise ValueError("Análisis incompleto")

    return mapa

# ==========================================
# NODO DE PUNTUACIÓN
# ==========================================
def puntuar_real(peticion: dict) -> dict:
    """Devuelve un mapa por ID con relevancia entre 0.0 y 1.0."""
    lote = peticion.get("lote", {})
    interacciones = lote.get("interacciones", [])
    ids_esperados = _ids_interacciones(interacciones)

    contexto = [
        {"id": m.get("id"), "texto": m.get("texto")}
        for m in interacciones
    ]

    prompt = f"""
    Evalúa la relevancia de estos mensajes y devuelve un JSON con una
    clave 'resultados' que contenga una lista de objetos.

    Cada objeto DEBE tener:
    - 'id': mantener el ID original.
    - 'relevancia': float entre 0.0 y 1.0.
      Asigna > 0.60 solo a mensajes muy útiles, hitos o problemas graves.

    Mensajes: {json.dumps(contexto, ensure_ascii=False)}
    """

    respuesta = llamar_llm_openrouter(prompt)
    lista_resultados = respuesta.get("resultados", [])

    if not isinstance(lista_resultados, list):
        raise ValueError("Resultados de puntuación inválidos")

    mapa_puntos = {}

    for resultado in lista_resultados:
        if not isinstance(resultado, dict):
            raise ValueError("Resultado de puntuación inválido")

        msg_id = resultado.get("id", resultado.get("id_mensaje"))

        if not msg_id:
            raise ValueError("Resultado de puntuación sin ID")

        if msg_id not in ids_esperados:
            raise ValueError(f"ID de puntuación no solicitado: {msg_id}")

        if msg_id in mapa_puntos:
            raise ValueError(f"ID de puntuación duplicado: {msg_id}")

        try:
            relevancia = float(resultado["relevancia"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Puntuación inválida") from exc

        if not 0.0 <= relevancia <= 1.0:
            raise ValueError("Puntuación fuera de rango 0.0-1.0")

        mapa_puntos[msg_id] = relevancia

    if set(mapa_puntos) != ids_esperados:
        raise ValueError("Puntuación incompleta")

    return mapa_puntos

# ==========================================
# NODOS GENERADORES DE CONTENIDO
# ==========================================
def post_real(peticion: dict) -> dict:
    """Genera un copy para LinkedIn."""
    interacciones = (
        peticion.get("interacciones_seleccionadas", [])
        or peticion.get("interacciones", [])
    )
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = (
        "Crea un copy inspirador para LinkedIn en español usando estos "
        f"mensajes: {json.dumps(interacciones, ensure_ascii=False)}. "
        "Devuelve un JSON con la clave 'copy'."
    )

    respuesta = llamar_llm_openrouter(prompt)

    return {
        "copy": respuesta.get("copy", ""),
        "fuentes": fuentes_recibidas,
    }


def faq_real(peticion: dict) -> dict:
    """Genera un FAQ o tip educativo técnico."""
    interacciones = (
        peticion.get("interacciones_seleccionadas", [])
        or peticion.get("interacciones", [])
    )
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = (
        "Crea un FAQ o Tip educativo técnico en español resolviendo estas "
        f"dudas: {json.dumps(interacciones, ensure_ascii=False)}. "
        "Devuelve un JSON con la clave 'copy'."
    )

    respuesta = llamar_llm_openrouter(prompt)

    return {
        "copy": respuesta.get("copy", ""),
        "fuentes": fuentes_recibidas,
    }


def highlights_real(peticion: dict) -> dict:
    """Genera un resumen semanal de la comunidad."""
    interacciones = (
        peticion.get("interacciones_seleccionadas", [])
        or peticion.get("interacciones", [])
    )
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = (
        "Redacta un resumen semanal (Community Highlights) cohesionado "
        "en español con estos eventos: "
        f"{json.dumps(interacciones, ensure_ascii=False)}. "
        "Devuelve un JSON con la clave 'copy'."
    )

    respuesta = llamar_llm_openrouter(prompt)

    return {
        "copy": respuesta.get("copy", ""),
        "fuentes": fuentes_recibidas,
    }
