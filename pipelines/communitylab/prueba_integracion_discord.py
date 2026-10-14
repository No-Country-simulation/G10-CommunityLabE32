import json
import os
import urllib.error
import urllib.request

from normalizador_discord import construir_lotes, normalizar_discord_jsonl

# ==========================================
# CONFIGURACIÓN DEL ENTORNO DE PRUEBA
# ==========================================
ARCHIVO_EXPORTACION = "discord_export.jsonl"
URL_BACKEND = os.environ.get("URL_BACKEND", "http://localhost:8000/api/v1/trabajos")  # URL del worker asíncrono en local
ORIGEN_COMUNIDAD = "discord"
PERIODO_REFERENCIA = os.environ.get("PERIODO_REFERENCIA", "S3")

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

def enviar_al_backend(payload):
    """Envía un lote normalizado a la cola de procesamiento del backend"""
    print(f"
🚀 Enviando {len(payload['interacciones'])} mensajes al backend ({URL_BACKEND})...")
    peticion = urllib.request.Request(
        URL_BACKEND,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            print("✅ ¡Éxito! El backend aceptó el lote.")
            print(f"📄 Respuesta del servidor: {respuesta.read().decode('utf-8')}")
    except urllib.error.HTTPError as error:
        print(f"⚠️ El backend respondió con código {error.code}")
        print(f"Detalle: {error.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError:
        print("⚠️ No se pudo conectar al backend.")
        print("👉 Nota: Esto es normal si no tienes los contenedores Docker de la API y el worker levantados en tu local ahora mismo.")
        print("💡 Payload generado:")
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
    print("📊 Resumen de Normalización:", resultado["estadisticas"])
    if resultado["interacciones"]:
        for lote in construir_lotes(resultado["interacciones"], ORIGEN_COMUNIDAD, PERIODO_REFERENCIA):
            enviar_al_backend(lote)
    else:
        print("No hay mensajes válidos para enviar.")
        
    # Limpieza
    if os.path.exists(ARCHIVO_EXPORTACION):
        os.remove(ARCHIVO_EXPORTACION)