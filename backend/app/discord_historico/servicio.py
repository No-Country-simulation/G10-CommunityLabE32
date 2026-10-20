"""Fase 1: verificar acceso y previsualizar el alcance. No guarda contenido.

Orden de comprobaciones (la primera no consulta a Discord):
  1. el ID tiene formato de snowflake y el canal está en la lista autorizada de esta herramienta;
  2. el canal existe y pertenece al servidor autorizado (GET /channels/{id});
  3. el bot es miembro del servidor (GET /users/@me, GET /guilds/{id}/members/{bot});
  4. permisos efectivos del bot: VIEW_CHANNEL y READ_MESSAGE_HISTORY (GET /guilds/{id}, /roles);
  5. tipo de canal soportado en esta versión (texto y anuncios).
La autorización de la persona en la web se comprueba aparte (token de operador en la API).
"""
from .cliente import NoEncontrado, SinPermiso
from .fechas import fecha_de_snowflake, iso, normalizar_rango, snowflake_de, es_snowflake
from .permisos import READ_MESSAGE_HISTORY, VIEW_CHANNEL, permisos_base, permisos_en_canal

TIPOS = {0: "texto", 2: "voz", 4: "categoria", 5: "anuncios", 10: "hilo_de_anuncio", 11: "hilo_publico",
         12: "hilo_privado", 13: "escenario", 15: "foro", 16: "medios"}
TIPOS_SOPORTADOS = {0, 5}
TIPOS_MENSAJE_HUMANO = {0, 19}  # DEFAULT y REPLY; el resto son mensajes de sistema o de comandos
MAX_MUESTRA = 5
LARGO_MUESTRA = 200


class AccesoDenegado(Exception):
    def __init__(self, codigo, mensaje, http=403):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.http = codigo, mensaje, http


def verificar_acceso(cliente, config, canal_id):
    """Devuelve el informe de acceso; lanza AccesoDenegado si no se puede usar el canal."""
    if not es_snowflake(canal_id):
        raise AccesoDenegado("canal_id_invalido", "El ID del canal debe ser un número de 17 a 20 dígitos.", 422)
    guild_autorizado = config.servidor_de(canal_id)
    if guild_autorizado is None:
        # Sin llamar a Discord: conocer un ID no basta para consultarlo.
        raise AccesoDenegado("canal_no_autorizado", "El canal no está en la lista autorizada de esta herramienta.")
    try:
        canal = cliente.canal(canal_id)
    except (NoEncontrado, SinPermiso):
        raise AccesoDenegado("canal_inaccesible", "El bot no puede ver ese canal o no existe.") from None
    if str(canal.get("guild_id")) != guild_autorizado:
        raise AccesoDenegado("servidor_no_coincide", "El canal no pertenece al servidor autorizado.")
    bot = cliente.usuario_actual()
    try:
        miembro = cliente.miembro(guild_autorizado, bot["id"])
    except (NoEncontrado, SinPermiso):
        raise AccesoDenegado("bot_fuera_del_servidor", "El bot no pertenece al servidor.") from None
    servidor = cliente.servidor(guild_autorizado)
    roles = cliente.roles(guild_autorizado)
    base = permisos_base(servidor, roles, bot["id"], miembro.get("roles", []))
    efectivos = permisos_en_canal(base, guild_autorizado, bot["id"], miembro.get("roles", []),
                                  canal.get("permission_overwrites"))
    tipo = canal.get("type")
    informe = {
        "canal": {"id": canal_id, "nombre": canal.get("name"), "tipo": tipo, "tipo_nombre": TIPOS.get(tipo, "otro")},
        "servidor": {"id": guild_autorizado, "nombre": servidor.get("name")},
        "autorizado_en_herramienta": True,
        "bot_en_servidor": True,
        "permisos": {"ver_canal": bool(efectivos & VIEW_CHANNEL),
                     "leer_historial": bool(efectivos & READ_MESSAGE_HISTORY)},
        "tipo_soportado": tipo in TIPOS_SOPORTADOS,
    }
    if not informe["permisos"]["ver_canal"] or not informe["permisos"]["leer_historial"]:
        raise AccesoDenegado("permisos_insuficientes",
                             "El bot necesita «Ver canal» y «Leer el historial de mensajes» en ese canal.")
    if not informe["tipo_soportado"]:
        raise AccesoDenegado("tipo_no_soportado",
                             f"Tipo de canal «{informe['canal']['tipo_nombre']}» no soportado en esta versión "
                             "(solo canales de texto y de anuncios; los hilos y foros no se importan).", 422)
    return informe


def requiere_confirmacion(config, rango, max_mensajes):
    return rango.dias > config.confirmar_dias or max_mensajes > config.confirmar_mensajes


def clasificar(m):
    """Motivo de descarte o None si el mensaje se importa."""
    if m.get("webhook_id"):
        return "webhook"
    if (m.get("author") or {}).get("bot"):
        return "bot"
    if m.get("type") not in TIPOS_MENSAJE_HUMANO:
        return "sistema"
    return None


def previsualizar(cliente, config, canal_id, desde, hasta, zona, ahora, max_mensajes=None, incluir_muestra=False):
    max_mensajes = max_mensajes or config.max_mensajes
    if not 1 <= max_mensajes <= config.max_mensajes:
        raise AccesoDenegado("limite_invalido", f"max_mensajes debe estar entre 1 y {config.max_mensajes}.", 422)
    rango = normalizar_rango(desde, hasta, zona, ahora, config.max_dias)
    acceso = verificar_acceso(cliente, config, canal_id)
    pagina = cliente.mensajes(canal_id, snowflake_de(rango.fin_utc), 100)
    en_rango = [m for m in pagina if rango.inicio_utc <= fecha_de_snowflake(m["id"]) < rango.fin_utc]
    cruzo_inicio = any(fecha_de_snowflake(m["id"]) < rango.inicio_utc for m in pagina)
    completo = len(pagina) < 100 or cruzo_inicio
    if completo:
        conteo = {"tipo": "exacto", "mensajes_en_rango": len(en_rango),
                  "importables": sum(1 for m in en_rango if clasificar(m) is None)}
    else:
        # Página llena sin cruzar el inicio: el total real solo se sabe recorriendo todo el rango.
        mas_antiguo = fecha_de_snowflake(pagina[-1]["id"])
        cubierto = (rango.fin_utc - mas_antiguo).total_seconds()
        total = (rango.fin_utc - rango.inicio_utc).total_seconds()
        estimado = int(len(pagina) * total / cubierto) if cubierto > 0 else None
        conteo = {"tipo": "desconocido", "minimo": len(en_rango), "estimacion_aproximada": estimado,
                  "nota": "Estimación por densidad de la primera página; el total exacto se conoce al importar."}
    advertencias = list(rango.advertencias)
    hilos = sum(1 for m in en_rango if m.get("thread"))
    if hilos:
        advertencias.append(f"hilos_detectados_no_incluidos:{hilos}")
    vacios = sum(1 for m in en_rango if clasificar(m) is None and not m.get("content")
                 and not m.get("attachments") and not m.get("embeds") and not m.get("sticker_items"))
    if vacios:
        advertencias.append(f"contenido_vacio:{vacios} (posible falta de la intención MESSAGE_CONTENT del bot)")
    advertencias.append("se_excluyen_bots_webhooks_y_mensajes_de_sistema")
    resultado = {
        **acceso,
        "rango": rango.como_dict(),
        # Para crear EXACTAMENTE lo previsualizado (aunque el rango termine «hoy» y la creación ocurra
        # más tarde), envíe estos instantes UTC como desde/hasta: un instante con Z no se recorta de nuevo.
        "alcance_congelado": {"desde": iso(rango.inicio_utc), "hasta": iso(rango.fin_utc), "zona": rango.zona},
        "limites": {"max_mensajes": max_mensajes, "max_mensajes_configurado": config.max_mensajes,
                    "max_dias": config.max_dias, "requiere_confirmacion": requiere_confirmacion(config, rango, max_mensajes),
                    "umbral_confirmacion": {"dias": config.confirmar_dias, "mensajes": config.confirmar_mensajes}},
        "conteo": conteo,
        "alcance": "canal_sin_hilos",
        "advertencias": advertencias,
        "llamadas_discord": cliente.peticiones,
    }
    if incluir_muestra:
        resultado["muestra"] = [{"id_mensaje": f"discord-{m['id']}", "fecha": iso(fecha_de_snowflake(m["id"])),
                                 "autor_id": (m.get("author") or {}).get("id"),
                                 "texto": (m.get("content") or "")[:LARGO_MUESTRA]}
                                for m in en_rango if clasificar(m) is None][:MAX_MUESTRA]
    return resultado
