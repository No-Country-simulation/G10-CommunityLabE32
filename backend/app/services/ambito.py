"""Ámbito de métricas: qué mensajes, activos y alertas pertenecen a un origen y período.

Los mensajes y activos no guardan su origen; se reconstruye desde trabajos_worker:
- mensajes: IDs de las interacciones de los trabajos del ámbito (se guardan al encolar);
- activos: el worker los identifica como "act-" + sha256(id_trabajo + id_activo_del_grafo)[:40];
- alertas: alertas_internas de los trabajos terminados, contadas por mensaje fuente.

Sin filtro, el ámbito es toda la base. Adecuado para el volumen del hackathon (cientos de
trabajos); con más volumen convendría guardar el origen en las tablas.
"""
from dataclasses import dataclass, field
from hashlib import sha256
import json

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


def _json(valor):
    if isinstance(valor, (str, bytes)):
        try:
            return json.loads(valor)
        except ValueError:
            return None
    return valor


def id_activo_curaduria(id_trabajo, id_activo_grafo):
    # Debe coincidir con worker/store_postgres.py (ColaPostgres.terminar).
    return "act-" + sha256((id_trabajo + id_activo_grafo).encode()).hexdigest()[:40]


@dataclass
class Ambito:
    filtrado: bool
    ids_mensajes: set = field(default_factory=set)
    ids_activos: set = field(default_factory=set)
    alertas_por_fuente: set = field(default_factory=set)
    alertas_registradas: int = 0
    trabajos_por_estado: dict = field(default_factory=dict)


async def leer_trabajos(db: AsyncSession):
    try:
        filas = (await db.execute(text(
            "SELECT id, estado, entrada, resultado, actualizado FROM trabajos_worker"))).all()
    except ProgrammingError:
        await db.rollback()  # Instalación sin la tabla de la cola del worker: no hay trabajos.
        return []
    return [(f[0], f[1], _json(f[2]) or {}, _json(f[3]) or {}, f[4]) for f in filas]


async def calcular_ambito(db: AsyncSession, origen: str | None = None, periodo: str | None = None) -> Ambito:
    ambito = Ambito(filtrado=bool(origen or periodo))
    for id_trabajo, estado, entrada, resultado, _ in await leer_trabajos(db):
        if origen and entrada.get("origen_comunidad") != origen:
            continue
        if periodo and entrada.get("periodo_referencia") != periodo:
            continue
        ambito.trabajos_por_estado[estado] = ambito.trabajos_por_estado.get(estado, 0) + 1
        for m in entrada.get("interacciones") or []:
            if isinstance(m, dict) and isinstance(m.get("id"), str):
                ambito.ids_mensajes.add(m["id"])
        if estado != "terminado":
            continue
        for activo in resultado.get("activos_distribucion_generados") or []:
            if isinstance(activo, dict) and isinstance(activo.get("id_activo"), str):
                ambito.ids_activos.add(id_activo_curaduria(id_trabajo, activo["id_activo"]))
        for alerta in resultado.get("alertas_internas") or []:
            if isinstance(alerta, dict):
                ambito.alertas_registradas += 1
                if isinstance(alerta.get("fuente"), str):
                    ambito.alertas_por_fuente.add(alerta["fuente"])
    return ambito


async def alertas_internas(db: AsyncSession, origen: str | None = None, periodo: str | None = None):
    """Una alerta por mensaje fuente (el mismo conjunto que cuenta el KPI `alertas_internas`).

    Si el mismo mensaje se alertó en varios trabajos (reenvío o cierre), queda una sola entrada con la
    primera detección y `veces` = cuántas alertas lo citan. Solo trabajos terminados del ámbito.
    """
    por_fuente = {}
    for id_trabajo, estado, entrada, resultado, actualizado in await leer_trabajos(db):
        if (origen and entrada.get("origen_comunidad") != origen) or \
                (periodo and entrada.get("periodo_referencia") != periodo) or estado != "terminado":
            continue
        marca = actualizado.isoformat() if hasattr(actualizado, "isoformat") else str(actualizado)
        for alerta in resultado.get("alertas_internas") or []:
            if not isinstance(alerta, dict) or not isinstance(alerta.get("fuente"), str):
                continue
            previa = por_fuente.get(alerta["fuente"])
            if previa is not None:
                previa["veces"] += 1
                if marca < previa["detectada"]:
                    previa.update(detectada=marca, trabajo=id_trabajo, origen=entrada.get("origen_comunidad"),
                                  periodo=entrada.get("periodo_referencia"))
                continue
            por_fuente[alerta["fuente"]] = {
                "id_alerta": alerta.get("id_alerta"), "id_mensaje": alerta["fuente"],
                "nivel": alerta.get("nivel"), "motivo": alerta.get("mensaje"), "trabajo": id_trabajo,
                "origen": entrada.get("origen_comunidad"), "periodo": entrada.get("periodo_referencia"),
                "detectada": marca, "veces": 1}
    return por_fuente


async def estados_borrador(db: AsyncSession, ids_mensajes) -> dict:
    """Estado del borrador más avanzado que cita cada mensaje: aprobado > pendiente > rechazado."""
    if not ids_mensajes:
        return {}
    filas = (await db.execute(text(
        "SELECT estado, fuentes FROM activos WHERE jsonb_exists_any(CAST(fuentes AS jsonb), CAST(:ids AS text[]))"),
        {"ids": list(ids_mensajes)})).all()
    prioridad = {"aprobado": 3, "pendiente": 2, "rechazado": 1}
    resultado = {}
    for estado, fuentes in filas:
        valor = "pendiente" if estado in ("generado", "revisado") else estado
        for fuente in _json(fuentes) or []:
            if fuente in ids_mensajes and prioridad.get(valor, 0) > prioridad.get(resultado.get(fuente), 0):
                resultado[fuente] = valor
    return resultado


async def listar_ambitos(db: AsyncSession):
    grupos = {}
    for _, estado, entrada, _, actualizado in await leer_trabajos(db):
        clave = (entrada.get("origen_comunidad"), entrada.get("periodo_referencia"))
        if not all(isinstance(v, str) for v in clave):
            continue
        g = grupos.setdefault(clave, {"origen": clave[0], "periodo": clave[1], "trabajos": 0,
                                      "terminados": 0, "ultimo": None})
        g["trabajos"] += 1
        g["terminados"] += estado == "terminado"
        marca = actualizado.isoformat() if hasattr(actualizado, "isoformat") else str(actualizado)
        g["ultimo"] = max(g["ultimo"] or marca, marca)
    return sorted(grupos.values(), key=lambda g: g["ultimo"] or "", reverse=True)


async def ids_activos_de_trabajo(db: AsyncSession, id_trabajo: str) -> set:
    """IDs de curaduría de los activos que generó un trabajo terminado (vacío si no existe)."""
    for identificador, estado, _, resultado, _ in await leer_trabajos(db):
        if identificador == id_trabajo and estado == "terminado":
            return {id_activo_curaduria(identificador, a["id_activo"])
                    for a in resultado.get("activos_distribucion_generados") or []
                    if isinstance(a, dict) and isinstance(a.get("id_activo"), str)}
    return set()
