"""Envía al análisis (cola del worker) los mensajes de una importación histórica.

Cada mensaje se convierte EXACTAMENTE como lo hace el lector en vivo (normalizar_evento): mismo id
`discord-<message_id>`, autor = id del autor, canal = `discord_<canal_id>`, fecha UTC y texto sin
espacios exteriores. Así un mensaje que también llegue en vivo es el mismo registro, no un conflicto.

Los lotes van con origen propio (`discord-historico`) y un período por semana ISO, para no mezclarse
con los períodos que cierra el puente en vivo. El último lote de cada semana cierra ese período.
Sin Idempotency-Key explícita: la cola deriva la clave del contenido, así repetir el envío con los
mismos mensajes reutiliza los mismos trabajos.
"""
from pipelines.communitylab.fechas import fecha_utc
from pipelines.communitylab.normalizador_discord import LIMITE_AUTOR, LIMITE_CANAL, construir_lotes
from pipelines.communitylab.puente_discord import periodo_de

ORIGEN = "discord-historico"


def interaccion(fila):
    return {
        "id": fila["id_mensaje"],
        "autor": str(fila["autor_id"] or "discord_user")[:LIMITE_AUTOR],
        "canal": f"discord_{fila['canal_id'] or 'general'}"[:LIMITE_CANAL],
        "fecha": fecha_utc(fila["fecha"].isoformat()),
        "texto": fila["texto"].strip(),
        **({"autor_nombre": fila["autor_nombre"]} if fila.get("autor_nombre") else {}),
    }


def lotes(candidatos):
    """Lotes para POST /api/v1/trabajos agrupados por semana ISO (máximo 500 por lote)."""
    por_semana = {}
    for fila in candidatos:
        m = interaccion(fila)
        por_semana.setdefault(periodo_de(m["fecha"], "semana"), []).append(m)
    return [lote for periodo in sorted(por_semana)
            for lote in construir_lotes(por_semana[periodo], ORIGEN, periodo, True)]
