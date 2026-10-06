import os
import json
import math
import requests

# ==========================================
# MOTOR LLM CON FALLBACK (OPENROUTER)
# ==========================================
def llamar_llm_openrouter(prompt: str) -> dict:
    """Llama a OpenRouter con modelos gratuitos y manejo estricto de errores."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    payload = {
        "models": [
            "google/gemma-4-31b-it:free",
            "cohere/north-mini-code:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free"
        ],
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
            timeout=25
        )
    except requests.exceptions.RequestException as e:
        print(f"\n💥 ERROR CRÍTICO DE RED: {e}")
        raise Exception(f"Fallo de conexión HTTP con OpenRouter: {e}")
    
    if response.status_code != 200:
        print(f"\n💥 ERROR DE API OPENROUTER (Status {response.status_code}): {response.text}")
        raise Exception(f"Error API OpenRouter (Status {response.status_code}): {response.text}")
        
    data = response.json()
    if 'choices' not in data:
        print(f"\n💥 ERROR SIN CHOICES (Posible Rate Limit): {data}")
        raise Exception(f"Respuesta sin 'choices' (posible Rate Limit silencioso): {data}")
        
    contenido_str = data['choices'][0]['message']['content']
    contenido_str = contenido_str.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(contenido_str)
    except json.JSONDecodeError:
        print(f"\n💥 ERROR DE FORMATO JSON: {contenido_str}")
        raise Exception(f"El modelo no generó un JSON válido. Salida cruda: {contenido_str}")

# ==========================================
# NODOS DE CLASIFICACIÓN Y PUNTUACIÓN (BLINDADOS F09)
# ==========================================
def analizar_real(lote: dict) -> dict:
    """Devuelve un mapa por ID con los booleanos de ruta y el tema (Validación estricta)."""
    interacciones = lote.get("interacciones", [])
    esperados = {m.get("id") for m in interacciones if m.get("id") is not None}
    
    contexto = [{"id": m.get("id"), "texto": m.get("texto")} for m in interacciones]
    
    prompt = f"""
    Siempre responde en español. Evalúa estos mensajes y devuelve un JSON estricto con una clave 'resultados' que contenga una lista de objetos.
    Cada objeto DEBE tener exactamente estas claves:
    - 'id': (mantener original)
    - 'es_logro': bool (True si comparte un hito o éxito)
    - 'es_duda': bool (True si es consulta técnica)
    - 'es_bloqueo': bool (True si expresa frustración o no puede avanzar)
    - 'tema': string breve (normaliza temas similares bajo la misma cadena)
    Mensajes: {json.dumps(contexto)}
    """
    
    respuesta = llamar_llm_openrouter(prompt)
    
    lista_resultados = respuesta.get("resultados", [])
    if not lista_resultados and isinstance(respuesta, list):
        lista_resultados = respuesta
        
    mapa = {}
    for res in lista_resultados:
        msg_id = res.get("id", res.get("id_mensaje"))
        if msg_id in esperados:
            logro = res.get("es_logro")
            duda = res.get("es_duda")
            bloqueo = res.get("es_bloqueo")
            
            # Validación estricta F09: No aceptar no-booleanos de forma silenciosa
            if not all(isinstance(x, bool) for x in [logro, duda, bloqueo]):
                raise ValueError(f"El LLM devolvió valores no booleanos en los flags de análisis para el mensaje ID: {msg_id}")
                
            mapa[msg_id] = {
                "es_logro": logro,
                "es_duda": duda,
                "es_bloqueo": bloqueo,
                "tema": str(res.get("tema", "General"))
            }
            
    # Validación F09: Exigir todos los IDs obligatoriamente sin rellenar con Falsos por defecto
    faltantes = esperados - set(mapa.keys())
    if faltantes:
        raise ValueError(f"Análisis incompleto: faltan resultados del LLM para los IDs: {faltantes}")
            
    return mapa

def puntuar_real(peticion: dict) -> dict:
    """Devuelve un mapa por ID con un float de relevancia entre 0.0 y 1.0 (Validación estricta F09)."""
    lote = peticion.get("lote", {})
    interacciones = lote.get("interacciones", [])
    esperados = {m.get("id") for m in interacciones if m.get("id") is not None}
    
    contexto = [{"id": m.get("id"), "texto": m.get("texto")} for m in interacciones]
    
    prompt = f"""
    Evalúa la relevancia de estos mensajes. Devuelve un JSON con una clave 'resultados' conteniendo una lista de objetos.
    Cada objeto DEBE tener:
    - 'id': (mantener original)
    - 'relevancia': float entre 0.0 y 1.0 (Asigna > 0.60 solo a mensajes muy útiles, hitos o problemas graves)
    Mensajes: {json.dumps(contexto)}
    """
    
    respuesta = llamar_llm_openrouter(prompt)
    
    lista_resultados = respuesta.get("resultados", [])
    if not lista_resultados and isinstance(respuesta, list):
        lista_resultados = respuesta
        
    mapa_puntos = {}
    for res in lista_resultados:
        msg_id = res.get("id", res.get("id_mensaje"))
        if msg_id in esperados:
            val = res.get("relevancia")
            
            # Validación estricta F09: Rechazar booleanos explícitamente y asegurar tipos numéricos
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(f"Relevancia inválida (no numérica o booleana) para el mensaje ID {msg_id}: {val}")
                
            fval = float(val)
            # Validación estricta F09: Rango [0.0, 1.0] y números finitos
            if not math.isfinite(fval) or not (0.0 <= fval <= 1.0):
                raise ValueError(f"Relevancia fuera del rango válido [0.0, 1.0] o no finita para el mensaje ID {msg_id}: {val}")
                
            mapa_puntos[msg_id] = fval

    # Validación F09: Exigir todos los IDs obligatoriamente sin rellenar con 0.0 por defecto
    faltantes = esperados - set(mapa_puntos.keys())
    if faltantes:
        raise ValueError(f"Puntuación incompleta: faltan scores de relevancia del LLM para los IDs: {faltantes}")
            
    return mapa_puntos

# ==========================================
# NODOS GENERADORES DE CONTENIDO
# ==========================================
def post_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Crea un copy inspirador para LinkedIn en español usando estos mensajes: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    copy_text = respuesta.get("copy", "") if isinstance(respuesta, dict) else str(respuesta)
    return {"copy": copy_text, "fuentes": fuentes_recibidas}

def faq_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Crea un FAQ o Tip educativo técnico en español resolviendo estas dudas: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    copy_text = respuesta.get("copy", "") if isinstance(respuesta, dict) else str(respuesta)
    return {"copy": copy_text, "fuentes": fuentes_recibidas}

def highlights_real(peticion: dict) -> dict:
    interacciones = peticion.get("interacciones_seleccionadas", []) or peticion.get("interacciones", [])
    fuentes_recibidas = peticion.get("fuentes", [])
    
    prompt = f"Redacta un resumen semanal (Community Highlights) cohesionado en español con estos eventos: {json.dumps(interacciones)}. Devuelve un JSON con la clave 'copy'."
    respuesta = llamar_llm_openrouter(prompt)
    
    copy_text = respuesta.get("copy", "") if isinstance(respuesta, dict) else str(respuesta)
    return {"copy": copy_text, "fuentes": fuentes_recibidas}
    
    copy_text = respuesta.get("copy", "") if isinstance(respuesta, dict) else str(respuesta)
    return {"copy": copy_text, "fuentes": fuentes_recibidas}
