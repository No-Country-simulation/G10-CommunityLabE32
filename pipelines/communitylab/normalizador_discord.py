import json
import os

def normalizar_discord_jsonl(ruta_archivo: str, historial_ids: set = None) -> dict:
    """
    Lee un archivo JSONL exportado por el lector de Discord, valida los campos,
    aplica deduplicación y formatea los mensajes al esquema Interaccion.
    """
    if historial_ids is None:
        historial_ids = set()
        
    mensajes_normalizados = []
    estadisticas = {"aceptados": 0, "rechazados": 0, "duplicados": 0}
    
    if not os.path.exists(ruta_archivo):
        print(f"❌ Error: No se encontró el archivo {ruta_archivo}")
        return {"lote": [], "estadisticas": estadisticas}

    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        for linea in f:
            if not linea.strip():
                continue
            
            try:
                raw = json.loads(linea)
            except json.JSONDecodeError:
                estadisticas["rechazados"] += 1
                continue
                
            # 1. Validar el contrato de Paulo (schema_version)
            if raw.get("schema_version") != "discord-source-v1":
                estadisticas["rechazados"] += 1
                continue
                
            # 2. Deduplicación estricta por servidor e ID
            guild_id = str(raw.get("guild_id", "")).strip()
            message_id = str(raw.get("message_id", "")).strip()
            clave_unica = f"{guild_id}-{message_id}"
            
            if not guild_id or not message_id:
                estadisticas["rechazados"] += 1
                continue
                
            if clave_unica in historial_ids:
                estadisticas["duplicados"] += 1
                continue
                
            # 3. Validar contenido (rechazar nulos o vacíos)
            texto = str(raw.get("content", "")).strip()
            if not texto:
                estadisticas["rechazados"] += 1
                continue
                
            # 4. Normalización y blindaje (Protección contra F14)
            interaccion = {
                # Prefijo 'discord-' para evitar colisiones con otras fuentes
                "id": f"discord-{message_id}",
                
                # Límite estricto de 150 caracteres para el autor
                "autor": str(raw.get("author_id", "discord_user"))[:150],
                
                # Límite estricto de 50 caracteres para el canal
                "canal": f"discord_{raw.get('channel_id', 'general')}"[:50],
                
                # Tipo por defecto (Límite 50 caracteres)
                "tipo": "mensaje_discord", 
                
                "fecha": str(raw.get("created_at", "")),
                "texto": texto
            }
            
            mensajes_normalizados.append(interaccion)
            historial_ids.add(clave_unica)
            estadisticas["aceptados"] += 1
            
    print(f"📊 Resumen de Normalización:")
    print(f"  ✅ Aceptados:  {estadisticas['aceptados']}")
    print(f"  🔁 Duplicados: {estadisticas['duplicados']}")
    print(f"  ❌ Rechazados: {estadisticas['rechazados']}")
    
    return {
        "interacciones": mensajes_normalizados,
        "historial_ids": historial_ids
    }

# ==========================================
# BLOQUE DE PRUEBA LOCAL
# ==========================================
if __name__ == "__main__":
    # Simula la creación de un archivo de prueba con el formato de Paulo
    archivo_prueba = "prueba_discord.jsonl"
    mensaje_ficticio = {
        "schema_version": "discord-source-v1",
        "message_id": "333333333333333333",
        "guild_id": "111111111111111111",
        "channel_id": "222222222222222222",
        "author_id": "444444444444444444",
        "created_at": "2026-10-07T18:00:00+00:00",
        "content": "Mensaje ficticio: terminé mi primer proyecto con Python."
    }
    
    with open(archivo_prueba, "w", encoding="utf-8") as f:
        # Escribimos el mensaje original
        f.write(json.dumps(mensaje_ficticio) + "\n")
        # Lo escribimos de nuevo para probar que la deduplicación funciona
        f.write(json.dumps(mensaje_ficticio) + "\n")
        # Escribimos un mensaje roto para probar el rechazo
        f.write(json.dumps({"schema_version": "roto"}) + "\n")

    # Ejecutar el normalizador
    print("Iniciando prueba del adaptador...")
    resultado = normalizar_discord_jsonl(archivo_prueba)
    
    print("\n📦 Lote resultante para enviar al backend:")
    print(json.dumps(resultado["interacciones"], indent=2, ensure_ascii=False))
    
    # Limpieza del archivo de prueba
    if os.path.exists(archivo_prueba):
        os.remove(archivo_prueba)