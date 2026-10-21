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
import os

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
    # Lo que solo aparece en lotes de prueba (se oculta en las vistas sin filtro de lotes).
    excluidos_mensajes: set = field(default_factory=set)
    excluidos_activos: set = field(default_factory=set)


FUENTES = ("discord", "manual")
MAX_LOTES = 50


def fuente_de(fuente, entrada) -> str:
    """Vía de entrada guardada; en trabajos anteriores a la columna, se deduce del origen del lote."""
    if fuente in FUENTES:
        return fuente
    origen = entrada.get("origen_comunidad")
    return "discord" if origen in {"discord", "discord-historico", os.environ.get("PUENTE_ORIGEN") or "discord"} else "manual"


def parsear_lotes(valor: str | None):
    """`lotes` = JSON [{origen, periodo, fuente_ingesta?}]. None = sin selección (todo); [] = ningún lote."""
    if valor is None:
        return None
    try:
        lotes = json.loads(valor)
    except ValueError:
        raise ValueError("`lotes` no es JSON válido.") from None
    if not isinstance(lotes, list) or len(lotes) > MAX_LOTES:
        raise ValueError(f"`lotes` debe ser una lista de hasta {MAX_LOTES} lotes.")
    for lote in lotes:
        if (not isinstance(lote, dict) or not isinstance(lote.get("origen"), str)
                or not isinstance(lote.get("periodo"), str)
                or lote.get("fuente_ingesta") not in (None, *FUENTES)):
            raise ValueError("Cada lote necesita origen y periodo (texto) y fuente_ingesta discord, manual o null.")
    return lotes


def en_ambito(entrada, fuente, origen=None, periodo=None, fuente_ingesta=None, lotes=None) -> bool:
    """¿El trabajo pertenece a la selección? Con `lotes` manda la lista (unión de lotes)."""
    o, p = entrada.get("origen_comunidad"), entrada.get("periodo_referencia")
    if lotes is not None:
        return any(lote["origen"] == o and lote["periodo"] == p
                   and lote.get("fuente_ingesta") in (None, fuente) for lote in lotes)
    return ((not origen or o == origen) and (not periodo or p == periodo)
            and (not fuente_ingesta or fuente == fuente_ingesta))


async def leer_trabajos(db: AsyncSession):
    """(id, estado, entrada, resultado, actualizado, fuente, es_prueba) de cada trabajo; fuente siempre resuelta."""
    try:
        filas = (await db.execute(text(
            "SELECT id, estado, entrada, resultado, actualizado, fuente, es_prueba FROM trabajos_worker"))).all()
    except ProgrammingError:
        await db.rollback()  # Instalación sin la tabla de la cola del worker: no hay trabajos.
        return []
    return [(f[0], f[1], _json(f[2]) or {}, _json(f[3]) or {}, f[4], fuente_de(f[5], _json(f[2]) or {}), bool(f[6]))
            for f in filas]


def _ids_mensajes(entrada):
    return {m["id"] for m in entrada.get("interacciones") or [] if isinstance(m, dict) and isinstance(m.get("id"), str)}


def _ids_activos(id_trabajo, resultado):
    return {id_activo_curaduria(id_trabajo, a["id_activo"]) for a in resultado.get("activos_distribucion_generados") or []
            if isinstance(a, dict) and isinstance(a.get("id_activo"), str)}


async def calcular_ambito(db: AsyncSession, origen: str | None = None, periodo: str | None = None,
                          fuente_ingesta: str | None = None, lotes: list | None = None,
                          incluir_pruebas: bool = False) -> Ambito:
    ambito = Ambito(filtrado=bool(origen or periodo or fuente_ingesta) or lotes is not None)
    de_prueba, de_reales = set(), set()
    for id_trabajo, estado, entrada, resultado, _, fuente, es_prueba in await leer_trabajos(db):
        if es_prueba and not incluir_pruebas:
            de_prueba |= _ids_mensajes(entrada)
            if estado == "terminado":
                ambito.excluidos_activos |= _ids_activos(id_trabajo, resultado)
            continue
        de_reales |= _ids_mensajes(entrada)
        if not en_ambito(entrada, fuente, origen, periodo, fuente_ingesta, lotes):
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
    ambito.excluidos_mensajes = de_prueba - de_reales   # un mensaje también presente en un lote real se muestra
    return ambito


async def alertas_internas(db: AsyncSession, origen: str | None = None, periodo: str | None = None,
                           fuente_ingesta: str | None = None, lotes: list | None = None, incluir_pruebas: bool = False):
    """Una alerta por mensaje fuente (el mismo conjunto que cuenta el KPI `alertas_internas`).

    Si el mismo mensaje se alertó en varios trabajos (reenvío o cierre), queda una sola entrada con la
    primera detección y `veces` = cuántas alertas lo citan. Solo trabajos terminados del ámbito.
    """
    por_fuente = {}
    for id_trabajo, estado, entrada, resultado, actualizado, fuente, es_prueba in await leer_trabajos(db):
        if (es_prueba and not incluir_pruebas) or estado != "terminado" \
                or not en_ambito(entrada, fuente, origen, periodo, fuente_ingesta, lotes):
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


async def listar_ambitos(db: AsyncSession, incluir_pruebas: bool = False):
    grupos = {}
    for _, estado, entrada, _, actualizado, fuente, es_prueba in await leer_trabajos(db):
        clave = (entrada.get("origen_comunidad"), entrada.get("periodo_referencia"), fuente)
        if not all(isinstance(v, str) for v in clave) or (es_prueba and not incluir_pruebas):
            continue
        # Mismo origen y período por vías distintas = lotes distintos.
        g = grupos.setdefault(clave, {"origen": clave[0], "periodo": clave[1], "fuente_ingesta": fuente,
                                      "es_prueba": False, "trabajos": 0, "terminados": 0, "ultimo": None})
        g["es_prueba"] = g["es_prueba"] or es_prueba
        g["trabajos"] += 1
        g["terminados"] += estado == "terminado"
        marca = actualizado.isoformat() if hasattr(actualizado, "isoformat") else str(actualizado)
        g["ultimo"] = max(g["ultimo"] or marca, marca)
    return sorted(grupos.values(), key=lambda g: g["ultimo"] or "", reverse=True)


async def ids_activos_de_trabajo(db: AsyncSession, id_trabajo: str) -> set:
    """IDs de curaduría de los activos que generó un trabajo terminado (vacío si no existe)."""
    for identificador, estado, _, resultado, _, _, _ in await leer_trabajos(db):
        if identificador == id_trabajo and estado == "terminado":
            return {id_activo_curaduria(identificador, a["id_activo"])
                    for a in resultado.get("activos_distribucion_generados") or []
                    if isinstance(a, dict) and isinstance(a.get("id_activo"), str)}
    return set()


async def ids_excluidos(db: AsyncSession):
    """(mensajes, activos) que solo pertenecen a lotes de prueba: lo que se oculta sin incluir_pruebas."""
    ambito = await calcular_ambito(db)
    return ambito.excluidos_mensajes, ambito.excluidos_activos
