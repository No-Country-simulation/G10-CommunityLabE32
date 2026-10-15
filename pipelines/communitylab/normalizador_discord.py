"""Normalizador de eventos de Discord (discord-source-v1) al lote de POST /api/v1/trabajos."""
import json
import os
try:
    from .fechas import fecha_utc
except ImportError:
    from fechas import fecha_utc

ESQUEMA_FUENTE = "discord-source-v1"
MAX_INTERACCIONES_POR_LOTE = 500
LIMITE_AUTOR = 150
LIMITE_CANAL = 50


def _estadisticas_vacias() -> dict:
    return {"aceptados": 0, "rechazados": 0, "duplicados": 0}


def normalizar_evento(raw: dict) -> dict | None:
    """Convierte un evento discord-source-v1 en una Interaccion; devuelve None si no es válido."""
    if not isinstance(raw, dict) or raw.get("schema_version") != ESQUEMA_FUENTE:
        return None

    message_id = str(raw.get("message_id") or "").strip()
    guild_id = str(raw.get("guild_id") or "").strip()
    texto = str(raw.get("content") or "").strip()
    fecha = str(raw.get("created_at") or "").strip()
    if not message_id or not guild_id or not texto or not fecha:
        return None
    try:
        fecha = fecha_utc(fecha)
    except ValueError:
        return None

    # Sin "tipo": el análisis de la IA decide la clasificación de cada mensaje.
    return {
        # Prefijo 'discord-' para evitar colisiones con otras fuentes
        "id": f"discord-{message_id}",
        "autor": str(raw.get("author_id") or "discord_user")[:LIMITE_AUTOR],
        "canal": f"discord_{raw.get('channel_id') or 'general'}"[:LIMITE_CANAL],
        "fecha": fecha,
        "texto": texto,
    }


def normalizar_eventos(eventos, historial_ids=None) -> dict:
    """Valida, deduplica (servidor + mensaje) y normaliza una secuencia de eventos ya decodificados."""
    vistos = set(historial_ids or ())
    contenidos = {}
    interacciones = []
    estadisticas = _estadisticas_vacias()

    for raw in eventos:
        interaccion = normalizar_evento(raw)
        if interaccion is None:
            estadisticas["rechazados"] += 1
            continue

        clave_unica = f"{str(raw['guild_id']).strip()}-{str(raw['message_id']).strip()}"
        if clave_unica in vistos:
            if clave_unica in contenidos and contenidos[clave_unica] != interaccion:
                estadisticas["rechazados"] += 1
                continue
            estadisticas["duplicados"] += 1
            continue

        vistos.add(clave_unica)
        contenidos[clave_unica] = interaccion
        interacciones.append(interaccion)
        estadisticas["aceptados"] += 1

    # Lista ordenada (no set) para que el historial se pueda guardar o enviar como JSON.
    return {"interacciones": interacciones, "historial_ids": sorted(vistos), "estadisticas": estadisticas}


def normalizar_discord_jsonl(ruta_archivo: str, historial_ids=None) -> dict:
    """
    Lee un archivo JSONL exportado por el lector de Discord, valida los campos,
    aplica deduplicación y formatea los mensajes al esquema Interaccion.
    Devuelve siempre las claves: interacciones, historial_ids y estadisticas.
    """
    if not os.path.exists(ruta_archivo):
        return {"interacciones": [], "historial_ids": sorted(set(historial_ids or ())),
                "estadisticas": _estadisticas_vacias()}

    eventos = []
    lineas_invalidas = 0
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                lineas_invalidas += 1

    resultado = normalizar_eventos(eventos, historial_ids)
    resultado["estadisticas"]["rechazados"] += lineas_invalidas
    return resultado


def construir_lotes(interacciones, origen_comunidad: str, periodo_referencia: str,
                    cierre_periodo: bool = False) -> list[dict]:
    """Arma los cuerpos para POST /api/v1/trabajos, con máximo 500 interacciones por lote."""
    if not origen_comunidad or not periodo_referencia:
        raise ValueError("origen_comunidad y periodo_referencia son obligatorios")
    lotes = []
    for inicio in range(0, len(interacciones), MAX_INTERACCIONES_POR_LOTE):
        bloque = interacciones[inicio:inicio + MAX_INTERACCIONES_POR_LOTE]
        lotes.append({
            "origen_comunidad": origen_comunidad,
            "periodo_referencia": periodo_referencia,
            # Solo el último lote puede cerrar el período
            "cierre_periodo": cierre_periodo and inicio + MAX_INTERACCIONES_POR_LOTE >= len(interacciones),
            "interacciones": bloque,
        })
    return lotes


# ==========================================
# BLOQUE DE PRUEBA LOCAL
# ==========================================
if __name__ == "__main__":
    mensaje_ficticio = {
        "schema_version": ESQUEMA_FUENTE,
        "message_id": "333333333333333333",
        "guild_id": "111111111111111111",
        "channel_id": "222222222222222222",
        "author_id": "444444444444444444",
        "created_at": "2026-10-07T18:00:00+00:00",
        "content": "Mensaje ficticio: terminé mi primer proyecto con Python.",
    }
    # Original, duplicado y mensaje roto
    resultado = normalizar_eventos([mensaje_ficticio, mensaje_ficticio, {"schema_version": "roto"}])
    print("Estadísticas:", resultado["estadisticas"])
    lotes = construir_lotes(resultado["interacciones"], "discord", "S3")
    print(json.dumps(lotes, indent=2, ensure_ascii=False))
