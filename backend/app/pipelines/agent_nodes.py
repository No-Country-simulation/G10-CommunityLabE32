import os
import json
import requests

# ==========================================
# MOTOR LLM CON FALLBACK (OPENROUTER)
# ==========================================
def llamar_llm_openrouter(prompt: str) -> dict:
    """Llama a OpenRouter y devuelve un JSON seguro."""
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

    payload = {
        "models": ["meta-llama/llama-3-8b-instruct", "deepseek/deepseek-chat"],
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/No-Country-simulation/G10-CommunityLabE32"
            },
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

    if not isinstance(data, dict) or not data.get("choices"):
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

    contenido_str = data["choices"][0]["message"].get("content", "")
    contenido_str = contenido_str.replace("```json", "").replace("```", "").strip()

    try:
        resultado = json.loads(contenido_str)
        if not isinstance(resultado, dict):
            raise ValueError("OpenRouter debe devolver un objeto JSON")
        return resultado
    except json.JSONDecodeError:
        raise ValueError("Respuesta de OpenRouter no disponible o inválida")

# ==========================================
# NODOS DE CLASIFICACIÓN Y PUNTUACIÓN
# ==========================================
def analizar_real(lote: dict) -> dict:
    """Devuelve un mapa por ID con los booleanos de ruta y el tema."""
    interacciones = lote.get("interacciones", [])
    contexto = [{"id": m.get("id"), "texto": m.get("texto")} for m in interacciones]

    prompt = f"""
    Evalúa estos mensajes y devuelve un JSON estricto con una clave 'resultados' que contenga una lista de objetos.
    Cada objeto DEBE tener exactamente estas claves:
    - 'id': (mantener original)
    - 'es_logro': bool (True si comparte un hito o éxito)
    - 'es_duda': bool (True si es consulta técnica)
    - 'es_bloqueo': bool (True si expresa frustración o no puede avanzar)
    - 'tema': string breve (normaliza temas similares bajo la misma cadena)
    Mensajes: {json.dumps(contexto)}
    """

    respuesta = llamar_llm_openrouter(prompt)

    mapa = {}
    lista_resultados = respuesta.get("resultados", [])
    if not lista_resultados and isinstance(respuesta, list):
        lista_resultados = respuesta

    for res in lista_resultados:
        msg_id = res.get("id", res.get("id_mensaje"))
        if msg_id:
            mapa[msg_id] = {
                "es_logro": res["es_logro"],
                "es_duda": res["es_duda"],
                "es_bloqueo": res["es_bloqueo"],
                "tema": res.get("tema", "General")
            }

    if set(mapa) != {m["id"] for m in interacciones}:
        raise ValueError("Análisis incompleto")

    return mapa

def puntuar_real(peticion: dict) -> dict:
    """Devuelve un mapa por ID con un float de relevancia entre 0.0 y 1.0."""
    lote = peticion.get("lote", {})
    interacciones = lote.get("interacciones", [])
    contexto = [{"id": m.get("id"), "texto": m.get("texto")} for m in interacciones]

    prompt = f"""
    Evalúa la relevancia de estos mensajes. Devuelve un JSON con una clave 'resultados' conteniendo una lista de objetos.
    Cada objeto DEBE tener:
    - 'id': (mantener original)
    - 'relevancia': float entre 0.0 y 1.0 (Asigna > 0.60 solo a mensajes muy útiles, hitos o problemas graves)
    Mensajes: {json.dumps(contexto)}
    """

    respuesta = llamar_llm_openrouter(prompt)

    mapa_puntos = {}
    lista_resultados = respuesta.get("resultados", [])
    if not lista_resultados and isinstance(respuesta, list):
        lista_resultados = respuesta

    for res in lista_resultados:
        msg_id = res.get("id", res.get("id_mensaje"))
        if msg_id:
            try:
                mapa_puntos[msg_id] = res["relevancia"]
            except (ValueError, TypeError):
                raise ValueError("Puntuación inválida") from None

    if set(mapa_puntos) != {m["id"] for m in interacciones}:
        raise ValueError("Puntuación incompleta")

    return mapa_puntos

# ==========================================
# NODOS GENERADORES DE CONTENIDO CORREGIDOS
# ==========================================
def post_real(peticion: dict) -> dict:
    # Usamos interacciones_seleccionadas o caemos en interacciones si viene plano
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = f"Crea un copy inspirador para LinkedIn usando estos mensajes: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)

    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}

def faq_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = f"Crea un FAQ o Tip educativo técnico resolviendo estas dudas: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)

    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}

def highlights_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])

    prompt = f"Redacta un resumen semanal (Community Highlights) cohesionado con estos eventos: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)

    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}
