"""«Procesar pendientes»: solicitud de lotes parciales de Discord sin cerrar el período.

Flujo: la interfaz crea la solicitud (operador) -> el puente la toma en su ciclo normal
(PUENTE_TOKEN), fija los mensajes nuevos de cada período abierto y los envía como
trabajos con cierre_periodo=false -> el puente informa el avance -> la interfaz muestra el
progreso cruzando cada lote con su trabajo en trabajos_worker.

Doble clic o pestañas concurrentes: un índice único deja una sola solicitud abierta por
origen; crear otra devuelve la existente. Si el puente cae después de tomarla y antes de
planificarla, la reserva vence y se vuelve a ofrecer con el MISMO id (la planificación del
puente es idempotente por id).
"""
import json
import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.acceso import requiere_operador, requiere_puente
from backend.app.core.dependencias import get_db

router = APIRouter(tags=["Procesamiento de pendientes"])
ABIERTAS = ("pendiente", "tomada", "en_curso")
RESERVA_SEGUNDOS = 600
PUENTE_ACTIVO_SEGUNDOS = 180


def origen_por_defecto():
    return os.environ.get("PUENTE_ORIGEN", "discord")


def _json(valor):
    return json.loads(valor) if isinstance(valor, (str, bytes)) else valor


class CrearSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: str | None = Field(default=None, min_length=1, max_length=200)


class Toma(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: str = Field(min_length=1, max_length=200)
    pendientes: dict[str, int] = Field(default_factory=dict, max_length=200)


class LoteInforme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    periodo: str = Field(min_length=1, max_length=100)
    nuevos: int = Field(ge=0, le=500)
    contexto: int = Field(ge=0, le=500)
    trabajo: str | None = Field(default=None, max_length=64)
    estado: str = Field(min_length=1, max_length=30)


class Informe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: str = Field(min_length=1, max_length=200)
    estado: Literal["en_curso", "finalizada", "sin_pendientes"]
    lotes: list[LoteInforme] = Field(default_factory=list, max_length=200)
    pendientes: dict[str, int] = Field(default_factory=dict, max_length=200)


async def _registrar_puente(db, origen, pendientes):
    await db.execute(text("""INSERT INTO estado_puente (origen, pendientes, visto)
        VALUES (:o, CAST(:p AS jsonb), clock_timestamp())
        ON CONFLICT (origen) DO UPDATE SET pendientes=EXCLUDED.pendientes, visto=EXCLUDED.visto"""),
        {"o": origen, "p": json.dumps(pendientes)})


async def _detalle(db, fila):
    """Solicitud con el avance real de cada lote (estado del trabajo y activos creados)."""
    lotes = _json(fila["lotes"]) or []
    ids = [l["trabajo"] for l in lotes if l.get("trabajo")]
    trabajos = {}
    if ids:
        for t in (await db.execute(text(
                "SELECT id, estado, resultado FROM trabajos_worker WHERE id = ANY(:ids)"), {"ids": ids})).mappings():
            resultado = _json(t["resultado"]) or {}
            trabajos[t["id"]] = {"estado": t["estado"],
                                 "activos": len(resultado.get("activos_distribucion_generados") or []),
                                 "alertas": len(resultado.get("alertas_internas") or [])}
    detalle = [{**l, "trabajo_estado": trabajos.get(l.get("trabajo"), {}).get("estado"),
                "activos": trabajos.get(l.get("trabajo"), {}).get("activos", 0),
                "alertas": trabajos.get(l.get("trabajo"), {}).get("alertas", 0)} for l in lotes]
    return {"id": fila["id"], "origen": fila["origen"], "estado": fila["estado"],
            "lotes": detalle,
            "mensajes_nuevos": sum(l["nuevos"] for l in lotes),
            "mensajes_contexto": sum(l["contexto"] for l in lotes),
            "trabajos_terminados": sum(1 for l in detalle if l["trabajo_estado"] == "terminado"),
            "trabajos_error": sum(1 for l in detalle if l["trabajo_estado"] == "error"
                                  or l["estado"] in ("error", "rechazado")),
            "activos_creados": sum(l["activos"] for l in detalle),
            "pendientes_al_informar": _json(fila["pendientes"]),
            "historial": _json(fila["historial"]),
            "creado": fila["creado"], "actualizado": fila["actualizado"]}


@router.post("/api/v1/procesamiento-pendientes", status_code=202)
async def crear_solicitud(
    cuerpo: CrearSolicitud | None = None, 
    db: AsyncSession = Depends(get_db),
    operador = Depends(requiere_operador) # Unificado con JWT
):
    origen = (cuerpo.origen if cuerpo else None) or origen_por_defecto()
    identificador = "sol-" + uuid4().hex
    try:
        nueva = (await db.execute(text("""INSERT INTO solicitudes_procesamiento (id, origen)
            VALUES (:id, :o) ON CONFLICT (origen) WHERE estado IN ('pendiente','tomada','en_curso')
            DO NOTHING RETURNING id"""), {"id": identificador, "o": origen})).scalar()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        nueva = None
    fila = (await db.execute(text("""SELECT * FROM solicitudes_procesamiento
        WHERE origen=:o AND estado IN ('pendiente','tomada','en_curso') ORDER BY creado DESC LIMIT 1"""),
        {"o": origen})).mappings().first()
    if fila is None:
        fila = (await db.execute(text("SELECT * FROM solicitudes_procesamiento WHERE id=:id"),
                                 {"id": identificador})).mappings().first()
    return {**await _detalle(db, fila), "reutilizada": nueva is None}


@router.get("/api/v1/procesamiento-pendientes/actual")
async def solicitud_actual(origen: str | None = None, db: AsyncSession = Depends(get_db)):
    origen = origen or origen_por_defecto()
    fila = (await db.execute(text("""SELECT * FROM solicitudes_procesamiento WHERE origen=:o
        ORDER BY creado DESC LIMIT 1"""), {"o": origen})).mappings().first()
    puente = (await db.execute(text("""SELECT pendientes, visto,
        visto > clock_timestamp() - make_interval(secs => :s) AS activo
        FROM estado_puente WHERE origen=:o"""), {"o": origen, "s": PUENTE_ACTIVO_SEGUNDOS})).mappings().first()
    pendientes = _json(puente["pendientes"]) if puente else None
    return {"origen": origen,
            "solicitud": await _detalle(db, fila) if fila else None,
            "puente": None if puente is None else {
                "activo": bool(puente["activo"]), "visto": puente["visto"],
                "pendientes_por_periodo": pendientes,
                "pendientes": sum(pendientes.values()) if pendientes else 0}}


@router.get("/api/v1/procesamiento-pendientes/{identificador}")
async def consultar_solicitud(identificador: str, db: AsyncSession = Depends(get_db)):
    fila = (await db.execute(text("SELECT * FROM solicitudes_procesamiento WHERE id=:id"),
                             {"id": identificador})).mappings().first()
    if fila is None:
        raise HTTPException(404, "Solicitud no encontrada")
    return await _detalle(db, fila)


@router.post("/api/v1/puente/solicitudes/tomar", dependencies=[Depends(requiere_puente)])
async def tomar_solicitud(toma: Toma, db: AsyncSession = Depends(get_db)):
    await _registrar_puente(db, toma.origen, toma.pendientes)
    fila = (await db.execute(text("""SELECT id FROM solicitudes_procesamiento
        WHERE origen=:o AND (estado='pendiente' OR (estado='tomada' AND vence <= clock_timestamp()))
        ORDER BY creado FOR UPDATE SKIP LOCKED LIMIT 1"""), {"o": toma.origen})).first()
    if fila:
        await db.execute(text("""UPDATE solicitudes_procesamiento SET estado='tomada',
            vence=clock_timestamp() + make_interval(secs => :s), pendientes=CAST(:p AS jsonb),
            historial=historial || '["tomada"]'::jsonb, actualizado=clock_timestamp() WHERE id=:id"""),
            {"id": fila[0], "s": RESERVA_SEGUNDOS, "p": json.dumps(toma.pendientes)})
    await db.commit()
    return {"id": fila[0] if fila else None}


@router.post("/api/v1/puente/solicitudes/{identificador}/informe", dependencies=[Depends(requiere_puente)])
async def informar_solicitud(identificador: str, informe: Informe, db: AsyncSession = Depends(get_db)):
    await _registrar_puente(db, informe.origen, informe.pendientes)
    if informe.estado == "finalizada":
        estado = ("completada" if all(l.estado == "terminado" for l in informe.lotes)
                  else "completada_con_errores")
    else:
        estado = informe.estado
    lotes = [l.model_dump() for l in informe.lotes]
    actualizada = (await db.execute(text("""UPDATE solicitudes_procesamiento SET estado=:e,
        lotes=CAST(:l AS jsonb), pendientes=CAST(:p AS jsonb), vence=NULL,
        historial=CASE WHEN estado=:e THEN historial ELSE historial || jsonb_build_array(CAST(:e AS text)) END,
        actualizado=clock_timestamp()
        WHERE id=:id AND origen=:o AND estado IN ('tomada','en_curso')"""),
        {"e": estado, "l": json.dumps(lotes), "p": json.dumps(informe.pendientes),
         "id": identificador, "o": informe.origen})).rowcount
    await db.commit()
    if not actualizada:
        # Ya cerrada o inexistente: se responde sin error para que el puente no reintente sin fin.
        return {"actualizada": False}
    return {"actualizada": True, "estado": estado}
