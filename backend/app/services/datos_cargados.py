"""«Datos cargados»: qué lotes hay en CommunityLab y cómo ocultarlos o eliminarlos.

Un lote es (origen, período, vía de entrada), como en el selector de lotes (ver services/ambito.py).
Sus datos se reconstruyen desde trabajos_worker:
- mensajes: los IDs de las interacciones de sus trabajos;
- activos: los generados por sus trabajos terminados (y con ellos sus banners e historial).

Ocultar marca los trabajos como de prueba (`es_prueba`): el lote deja de contar en el panel y se
puede volver a mostrar. Eliminar borra trabajos, activos, banners e historial del lote y solo los
mensajes que ningún otro lote usa. No toca la copia importada del historial de Discord (es la caché
de la importación del canal, ligada a la importación y no al lote) ni lo ya copiado en OCI.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.ambito import _ids_activos, _ids_mensajes, leer_trabajos

logger = logging.getLogger(__name__)
EN_PROCESO = ("recibido", "procesando")


def clave(origen, periodo, fuente):
    return (origen, periodo, fuente)


async def _agrupar(db: AsyncSession):
    """{clave: {trabajos, estados, mensajes, activos, es_prueba[], primero, ultimo}} de todos los lotes."""
    grupos = {}
    for id_trabajo, estado, entrada, resultado, actualizado, fuente, es_prueba in await leer_trabajos(db):
        k = clave(entrada.get("origen_comunidad"), entrada.get("periodo_referencia"), fuente)
        if not all(isinstance(v, str) for v in k):
            continue
        g = grupos.setdefault(k, {"trabajos": [], "estados": [], "mensajes": set(), "activos": set(),
                                  "pruebas": [], "fechas": []})
        g["trabajos"].append(id_trabajo)
        g["estados"].append(estado)
        g["pruebas"].append(es_prueba)
        g["mensajes"] |= _ids_mensajes(entrada)
        if estado == "terminado":
            g["activos"] |= _ids_activos(id_trabajo, resultado)
        if actualizado is not None:
            g["fechas"].append(actualizado)
    return grupos


async def _existentes(db, tabla, columna, ids, extra=""):
    if not ids:
        return {}
    filas = (await db.execute(text(f"SELECT {columna}{extra} FROM {tabla} WHERE {columna} = ANY(:ids)"),
                              {"ids": list(ids)})).all()
    return {f[0]: (f[1] if len(f) > 1 else None) for f in filas}


async def listar_lotes(db: AsyncSession) -> list[dict]:
    grupos = await _agrupar(db)
    todos_m = set().union(*(g["mensajes"] for g in grupos.values())) if grupos else set()
    todos_a = set().union(*(g["activos"] for g in grupos.values())) if grupos else set()
    mensajes = await _existentes(db, "mensajes", "id_mensaje", todos_m)
    activos = await _existentes(db, "activos", "id_activo", todos_a, ", estado")
    items = []
    for (origen, periodo, fuente), g in grupos.items():
        otros = set().union(*(o["mensajes"] for k, o in grupos.items() if k != (origen, periodo, fuente)))
        propios = [a for a in g["activos"] if a in activos]
        items.append({
            "origen": origen, "periodo": periodo, "fuente_ingesta": fuente,
            "oculto": all(g["pruebas"]),
            "trabajos": len(g["trabajos"]),
            "en_proceso": sum(e in EN_PROCESO for e in g["estados"]),
            "mensajes": sum(m in mensajes for m in g["mensajes"]),
            "mensajes_compartidos": sum(m in mensajes and m in otros for m in g["mensajes"]),
            "activos": len(propios),
            "aprobados": sum(activos[a] == "aprobado" for a in propios),
            "primero": min(g["fechas"]) if g["fechas"] else None,
            "ultimo": max(g["fechas"]) if g["fechas"] else None,
        })
    items.sort(key=lambda i: (i["ultimo"] is None, i["ultimo"]), reverse=True)
    return items


class LoteInexistente(Exception):
    pass


async def _seleccion(db, lotes):
    grupos = await _agrupar(db)
    pedidos = {clave(l["origen"], l["periodo"], l["fuente_ingesta"]) for l in lotes}
    faltan = pedidos - grupos.keys()
    if faltan:
        raise LoteInexistente(sorted(faltan)[0])
    return grupos, pedidos


async def cambiar_visibilidad(db: AsyncSession, lotes: list[dict], oculto: bool) -> int:
    grupos, pedidos = await _seleccion(db, lotes)
    ids = [t for k in pedidos for t in grupos[k]["trabajos"]]
    resultado = await db.execute(text("UPDATE trabajos_worker SET es_prueba = :v WHERE id = ANY(:ids)"),
                                 {"v": oculto, "ids": ids})
    await db.commit()
    return resultado.rowcount


async def plan_eliminacion(db: AsyncSession, lotes: list[dict]) -> dict:
    """Qué se borraría (conteos e IDs). Los mensajes que otro lote también usa se conservan."""
    grupos, pedidos = await _seleccion(db, lotes)
    trabajos = [t for k in pedidos for t in grupos[k]["trabajos"]]
    en_proceso = sum(e in EN_PROCESO for k in pedidos for e in grupos[k]["estados"])
    candidatos = set().union(*(grupos[k]["mensajes"] for k in pedidos))
    de_otros = set().union(*(g["mensajes"] for k, g in grupos.items() if k not in pedidos))
    mensajes = list(await _existentes(db, "mensajes", "id_mensaje", candidatos - de_otros))
    activos = await _existentes(db, "activos", "id_activo", set().union(*(grupos[k]["activos"] for k in pedidos)), ", estado")
    banners = (await db.execute(text("SELECT count(*) FROM banners WHERE id_activo = ANY(:ids)"),
                                {"ids": list(activos)})).scalar_one() if activos else 0
    return {"lotes": len(pedidos), "trabajos": trabajos, "en_proceso": en_proceso, "mensajes": mensajes,
            "mensajes_conservados": len(candidatos & de_otros), "activos": list(activos),
            "aprobados": sum(e == "aprobado" for e in activos.values()), "banners": banners}


def conteos(plan: dict) -> dict:
    return {"lotes": plan["lotes"], "trabajos": len(plan["trabajos"]), "en_proceso": plan["en_proceso"],
            "mensajes": len(plan["mensajes"]), "mensajes_conservados": plan["mensajes_conservados"],
            "activos": len(plan["activos"]), "aprobados": plan["aprobados"], "banners": plan["banners"]}


class EliminacionBloqueada(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


async def eliminar(db: AsyncSession, lotes: list[dict], incluir_aprobados: bool, actor: str) -> dict:
    plan = await plan_eliminacion(db, lotes)
    # Bloquea los trabajos del lote y vuelve a comprobar que ninguno se esté procesando ahora mismo.
    estados = (await db.execute(text("SELECT estado FROM trabajos_worker WHERE id = ANY(:ids) FOR UPDATE"),
                                {"ids": plan["trabajos"]})).scalars().all()
    if any(e in EN_PROCESO for e in estados):
        await db.rollback()
        raise EliminacionBloqueada("lote_en_proceso", "Hay trabajos de estos lotes en proceso; espera a que terminen.")
    if plan["aprobados"] and not incluir_aprobados:
        await db.rollback()
        raise EliminacionBloqueada("aprobados_afectados",
                                   f"{plan['aprobados']} contenido(s) aprobado(s) se borrarían; confirma que los incluyes.")
    activos, ids = plan["activos"], {"a": plan["activos"], "m": plan["mensajes"], "t": plan["trabajos"]}
    if activos:
        await db.execute(text("DELETE FROM banners WHERE id_activo = ANY(:a)"), ids)
        await db.execute(text("DELETE FROM activos_historial WHERE id_activo = ANY(:a)"), ids)
        await db.execute(text("DELETE FROM activos WHERE id_activo = ANY(:a)"), ids)
    if plan["mensajes"]:
        await db.execute(text("DELETE FROM mensajes WHERE id_mensaje = ANY(:m)"), ids)
    await db.execute(text("DELETE FROM trabajos_worker WHERE id = ANY(:t)"), ids)
    await db.commit()
    resumen = conteos(plan)
    logger.info("Datos eliminados por %s: %s", actor, resumen)
    return resumen
