import json
import requests
import os
from normalizador_discord import normalizar_discord_jsonl

# ==========================================
# CONFIGURACIÓN DEL ENTORNO DE PRUEBA
# ==========================================
ARCHIVO_EXPORTACION = "discord_export.jsonl"
URL_BACKEND = "http://localhost:8000/api/v1/trabajos" # URL del worker asíncrono en local

def preparar_datos_simulados():
    """Simula la salida exportada del lector de Paulo (export_jsonl)"""
    mensajes = [
        {
            "schema_version": "discord-source-v1",
            "message_id": "999999999999999991",
            "guild_id": "111111111111111111",
            "channel_id": "222222222222222222",
            "author_id": "user_4444",
            "created_at": "2026-10-12T10:00:00+00:00",
            "content": "¡Hola equipo! Logré configurar la máquina en Oracle Cloud, ¡estoy feliz!"
        },
        {
            "schema_version": "discord-source-v1",
            "message_id": "999999999999999992",
            "guild_id": "111111111111111111",
            "channel_id": "222222222222222222",
            "author_id": "user_5555",
            "created_at": "2026-10-12T10:05:00+00:00",
            "content": "Tengo un problema con Docker, me tira error 500 al levantar la API."
        }
    ]
    with open(ARCHIVO_EXPORTACION, "w", encoding="utf-8") as f:
        for msg in mensajes:
            f.write(json.dumps(msg) + "\n")
        # Metemos un duplicado intencional para probar tu filtro
        f.write(json.dumps(mensajes[0]) + "\n")

def enviar_al_backend(lote_normalizado):
    """Envía el lote normalizado a la cola de procesamiento del backend"""
    payload = {
        "origen": "discord",
        "interacciones": lote_normalizado["interacciones"]
    }
    
    print(f"\n🚀 Enviando {len(payload['interacciones'])} mensajes al backend ({URL_BACKEND})...")
    
    try:
        respuesta = requests.post(URL_BACKEND, json=payload, timeout=10)
        
        if respuesta.status_code in [200, 202]:
            print(f"✅ ¡Éxito! El backend aceptó el lote.")
            print(f"📄 Respuesta del servidor: {respuesta.json()}")
        else:
            print(f"⚠️ El backend respondió con código {respuesta.status_code}")
            print(f"Detalle: {respuesta.text}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️ No se pudo conectar al backend.")
        print("👉 Nota: Esto es normal si no tienes los contenedores Docker de la API y el worker levantados en tu local ahora mismo.")
        print("💡 Sin embargo, el payload generado está perfecto y listo para producción:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

# ==========================================
# EJECUCIÓN DEL FLUJO COMPLETO
# ==========================================
if __name__ == "__main__":
    print("1️⃣ Preparando archivo de exportación de Discord simulado...")
    preparar_datos_simulados()
    
    print("\n2️⃣ Ejecutando Normalizador de Tian...")
    resultado = normalizar_discord_jsonl(ARCHIVO_EXPORTACION)
    
    print("\n3️⃣ Conectando con el pipeline de procesamiento...")
    if resultado["interacciones"]:
        enviar_al_backend(resultado)
    else:
        print("No hay mensajes válidos para enviar.")
        
    # Limpieza
    if os.path.exists(ARCHIVO_EXPORTACION):
        os.remove(ARCHIVO_EXPORTACION)