import os
import json
import requests
from typing import TypedDict, List, Dict, Any

# ==========================================
# 1. EL ESTADO DEL GRAFO (GraphState)
# ==========================================
class GraphState(TypedDict):
    lote_mensajes: List[Dict[str, Any]]        # Viene del módulo de ingesta de José
    analisis_resultados: List[Dict[str, Any]]  # Salida de análisis
    puntuaciones: Dict[str, int]               # Scores de relevancia
    rutas_elegidas: List[str]                  # Decisiones del router
    borradores_generados: List[Dict[str, Any]] # Los posts finales

# ==========================================
# 2. MOTOR LLM CON FALLBACK (OPENROUTER)
# ==========================================
def llamar_llm_openrouter(prompt: str) -> dict:
    """Llama a Gemini gratuito. Si falla, salta a Llama 3 automáticamente."""
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
# 3. NODO DE ANÁLISIS Y PUNTUACIÓN
# ==========================================
def nodo_analisis(state: GraphState) -> GraphState:
    mensajes = state.get("lote_mensajes", [])
    
    # Recortamos a los primeros 10 para probar sin gastar cuota de golpe
    contexto = [{"id": m.get("id_mensaje"), "texto": m.get("texto")} for m in mensajes[:10]]
    
    prompt = f"""
    Analiza estos mensajes. Devuelve un JSON con una clave 'resultados' que contenga una lista de objetos.
    Cada objeto debe tener: 'id_mensaje', 'sentimiento', 'tema', y 'score_relevancia' (1 al 10).
    Mensajes: {json.dumps(contexto)}
    """
    
    respuesta_llm = llamar_llm_openrouter(prompt)
    resultados = respuesta_llm.get("resultados", [])
    
    # Extraer puntuaciones para el router
    puntuaciones = {m["id_mensaje"]: m["score_relevancia"] for m in resultados}
    
    return {"analisis_resultados": resultados, "puntuaciones": puntuaciones}

# ==========================================
# 4. NODO GENERADOR (CONSERVANDO FUENTES)
# ==========================================
def nodo_generador(state: GraphState) -> GraphState:
    mensajes = state.get("lote_mensajes", [])
    puntuaciones = state.get("puntuaciones", {})
    
    # Filtramos solo los mensajes más relevantes (Score > 7)
    mensajes_top = [m for m in mensajes if puntuaciones.get(m.get("id_mensaje"), 0) > 7]
    fuentes_ids = [m.get("id_mensaje") for m in mensajes_top]
    
    prompt = f"""
    Crea un post para LinkedIn inspirador usando esta información base. 
    Devuelve un JSON con la clave 'contenido_post'.
    Información: {json.dumps([m.get('texto') for m in mensajes_top])}
    """
    
    respuesta_llm = llamar_llm_openrouter(prompt)
    
    borrador = {
        "tipo_activo": "Post LinkedIn",
        "contenido": respuesta_llm.get("contenido_post", "Error al generar"),
        "fuentes_utilizadas": fuentes_ids # <- Trazabilidad exigida en el MVP
    }
    
    return {"borradores_generados": [borrador]}
