import os
import json
import requests

# ==========================================
# MOTOR LLM CON FALLBACK (OPENROUTER)
# ==========================================
def llamar_llm_openrouter(prompt: str) -> dict:
    """Llama a Gemini 2.5 Flash gratuito. Si falla, salta a Llama 3."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    payload = {
        "models": ["google/gemini-2.5-flash:free", "meta-llama/llama-3-8b-instruct:free"],
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }
    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}", 
            "HTTP-Referer": "https://github.com/No-Country-simulation/G10-CommunityLabE32"
        },
        json=payload
    )
    
    return json.loads(response.json()['choices'][0]['message']['content'])

# ==========================================
# NODOS DE CLASIFICACIÓN Y PUNTUACIÓN
# ==========================================
def analizar_real(lote: dict) -> dict:
    """Devuelve un mapa por ID con los booleanos de ruta y el tema."""
    interacciones = lote.get("interacciones", [])
    # Extraemos solo lo necesario para ahorrar tokens
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
    for res in respuesta.get("resultados", []):
        mapa[res["id"]] = {
            "es_logro": res.get("es_logro", False),
            "es_duda": res.get("es_duda", False),
            "es_bloqueo": res.get("es_bloqueo", False),
            "tema": res.get("tema", "General")
        }
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
    for res in respuesta.get("resultados", []):
        mapa_puntos[res["id"]] = res.get("relevancia", 0.0)
    return mapa_puntos

# ==========================================
# NODOS GENERADORES DE CONTENIDO
# ==========================================
# El contrato exige devolver exactamente las fuentes recibidas sin alterarlas

def post_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Crea un copy inspirador para LinkedIn usando estos mensajes: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}

def faq_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Crea un FAQ o Tip educativo técnico resolviendo estas dudas: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}

def highlights_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Redacta un resumen semanal (Community Highlights) cohesionado con estos eventos: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    return {"copy": respuesta.get("copy", ""), "fuentes": fuentes_recibidas}
