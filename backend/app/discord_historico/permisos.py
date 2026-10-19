"""Permisos efectivos del bot en un canal, con el algoritmo de la documentación oficial de Discord.

Base: dueño → todo; @everyone (id = id del servidor) | roles del miembro; ADMINISTRATOR → todo.
Sobrescrituras: @everyone (deny, allow) → roles agregados (deny, allow) → miembro (deny, allow).
"""
ADMINISTRATOR = 1 << 3
VIEW_CHANNEL = 1 << 10
READ_MESSAGE_HISTORY = 1 << 16
TODOS = (1 << 64) - 1


def _bits(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def permisos_base(guild, roles, miembro_id, roles_miembro):
    if str(guild.get("owner_id")) == str(miembro_id):
        return TODOS
    por_id = {str(r["id"]): _bits(r.get("permissions")) for r in roles}
    permisos = por_id.get(str(guild["id"]), 0)
    for rol in roles_miembro:
        permisos |= por_id.get(str(rol), 0)
    return TODOS if permisos & ADMINISTRATOR else permisos


def permisos_en_canal(base, guild_id, miembro_id, roles_miembro, sobrescrituras):
    if base & ADMINISTRATOR:
        return TODOS
    permisos = base
    por_id = {str(o["id"]): o for o in sobrescrituras or []}
    todos = por_id.get(str(guild_id))
    if todos:
        permisos &= ~_bits(todos.get("deny"))
        permisos |= _bits(todos.get("allow"))
    allow = deny = 0
    for rol in roles_miembro:
        o = por_id.get(str(rol))
        if o and o.get("type", 0) == 0:
            allow |= _bits(o.get("allow"))
            deny |= _bits(o.get("deny"))
    permisos &= ~deny
    permisos |= allow
    miembro = por_id.get(str(miembro_id))
    if miembro and miembro.get("type", 1) == 1:
        permisos &= ~_bits(miembro.get("deny"))
        permisos |= _bits(miembro.get("allow"))
    return permisos
