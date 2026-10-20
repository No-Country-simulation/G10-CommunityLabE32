"""Fase 2: ejecuta una importación reservada, página a página, hacia atrás en el tiempo.

Paginación (documentación oficial): GET /channels/{id}/messages?before=<cursor>&limit=100 devuelve
del más nuevo al más antiguo. El primer cursor es el snowflake del FIN exclusivo, así que nada
posterior (ni mensajes que lleguen durante la importación) puede entrar: el rango queda congelado.
Se avanza con el ID más antiguo de cada página y se detiene al cruzar el inicio, con una página
incompleta o vacía. Si el cursor no retrocede, se detiene con error (sin bucles).

Antes de la primera página de cada ejecución se vuelve a verificar el acceso (lista autorizada y
permisos), porque pueden haber cambiado desde la previsualización.
"""
from datetime import datetime

from .cliente import ErrorDiscord, NoEncontrado, SinPermiso
from .fechas import fecha_de_snowflake, snowflake_de
from .servicio import AccesoDenegado, clasificar, verificar_acceso

TAM_PAGINA = 100
CAMPOS_ADJUNTO = ("id", "filename", "content_type", "size")


def _fecha(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00")) if valor else None


def _normalizar(m):
    texto = m.get("content") or ""
    adjuntos = [{k: a.get(k) for k in CAMPOS_ADJUNTO} for a in m.get("attachments") or []]
    return {
        "id_mensaje": f"discord-{m['id']}",          # misma identidad que el lector en vivo
        "message_id": m["id"],
        "autor_id": str((m.get("author") or {}).get("id") or "desconocido"),
        "fecha": fecha_de_snowflake(m["id"]),
        "editado_en": _fecha(m.get("edited_timestamp")),
        "texto": texto,
        "contenido_disponible": bool(texto or adjuntos or m.get("embeds") or m.get("sticker_items")),
        "tipo_discord": m.get("type", 0),
        "adjuntos": adjuntos,
        "referencia": (m.get("message_reference") or {}).get("message_id"),
    }


def ejecutar(trabajo, cliente, store, config):
    """Procesa la importación hasta terminarla, cancelarla o fallar. Devuelve el estado final."""
    try:
        verificar_acceso(cliente, config, trabajo["canal_id"])
    except AccesoDenegado as e:
        store.finalizar(trabajo, "error", {"codigo": e.codigo, "reanudable": False})
        return "error"
    except ErrorDiscord as e:
        store.finalizar(trabajo, "error", e.como_dict())
        return "error"
    inicio, fin = trabajo["desde_utc"], trabajo["hasta_utc"]
    cursor = trabajo.get("cursor_before") or snowflake_de(fin)
    importados = trabajo.get("insertados", 0) + trabajo.get("existentes", 0) \
        + trabajo.get("existentes_en_vivo", 0) + trabajo.get("editados", 0)
    while True:
        mio, cancelar = store.estado_control(trabajo)
        if not mio:
            return "perdida"   # otra ejecución la tomó (reserva vencida); no escribir más
        if cancelar:
            store.finalizar(trabajo, "cancelada")
            return "cancelada"
        try:
            pagina = cliente.mensajes(trabajo["canal_id"], cursor, TAM_PAGINA)
        except (SinPermiso, NoEncontrado) as e:
            store.finalizar(trabajo, "error", {**e.como_dict(), "detalle": "permiso_revocado_o_canal_eliminado"})
            return "error"
        except ErrorDiscord as e:
            store.finalizar(trabajo, "error", e.como_dict())   # reanudable si es límite o red
            return "error"
        if not pagina:
            return store.finalizar(trabajo, "completada") or "perdida"
        nuevo_cursor = min(pagina, key=lambda m: int(m["id"]))["id"]
        if int(nuevo_cursor) >= int(cursor):
            store.finalizar(trabajo, "error", {"codigo": "cursor_sin_avance", "reanudable": False})
            return "error"
        aceptados, descartes, hilos, en_rango, cruzo = [], {}, 0, 0, False
        limite = False
        for m in sorted(pagina, key=lambda m: int(m["id"]), reverse=True):
            fecha = fecha_de_snowflake(m["id"])
            if fecha >= fin:
                descartes["fuera_de_rango"] = descartes.get("fuera_de_rango", 0) + 1
                continue
            if fecha < inicio:
                cruzo = True
                continue
            en_rango += 1
            if m.get("thread"):
                hilos += 1
            motivo = clasificar(m)
            if motivo:
                descartes[motivo] = descartes.get(motivo, 0) + 1
                continue
            if importados + len(aceptados) >= trabajo["max_mensajes"]:
                limite = True
                break
            aceptados.append(_normalizar(m))
        if limite:
            # El cursor se deja justo después del último aceptado: una reanudación con más límite seguiría ahí.
            cursor_guardar = aceptados[-1]["message_id"] if aceptados else cursor
        else:
            cursor_guardar = nuevo_cursor
        fila = store.guardar_pagina(trabajo, aceptados, descartes, cursor_guardar, len(pagina), hilos, en_rango)
        if fila is None:
            return "perdida"
        importados += len(aceptados)
        if limite:
            return store.finalizar(trabajo, "completada_con_limite", limite=True) or "perdida"
        if cruzo or len(pagina) < TAM_PAGINA:
            return store.finalizar(trabajo, "completada") or "perdida"
        cursor = nuevo_cursor
