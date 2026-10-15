import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo local .env
load_dotenv()

# Constantes de configuración operativa del modelo
DEFAULT_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
MAX_OUTPUT_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "1024"))

def get_api_key() -> str:
    """
    Recupera y valida la API Key de Gemini desde las variables de entorno.
    Soporta 'GEMINI_API_KEY' como nombre primario y 'LLM_API_KEY' como alternativa.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError(
            "No se encontró la clave de API para Gemini. "
            "Asegúrate de definir 'GEMINI_API_KEY' o 'LLM_API_KEY' en tu archivo .env"
        )
    return api_key

def get_llm_client():
    """
    Instancia y retorna el cliente configurado del SDK oficial de Google GenAI.
    Utiliza google-genai para la comunicación con la API.
    """
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError(
            "El paquete 'google-genai' no está instalado. "
            "Instálalo ejecutando: pip install google-genai"
        ) from exc

    api_key = get_api_key()
    
    # Inicialización del cliente oficial con la API Key configurada
    client = genai.Client(api_key=api_key)
    return client

def get_generation_config() -> dict:
    """
    Retorna un diccionario con los hiperparámetros estándar de generación.
    """
    return {
        "temperature": TEMPERATURE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }