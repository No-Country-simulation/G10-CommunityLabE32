"""«Datos cargados» (Ingesta): listar lotes, ocultarlos del panel o eliminarlos. Solo administradores.

  GET   /api/v1/datos/lotes                              lotes con sus conteos
  PATCH /api/v1/datos/lotes/visibilidad                  {"lotes": [...], "oculto": true|false}
  POST  /api/v1/datos/lotes/eliminacion/vista-previa     {"lotes": [...]} -> qué se borraría
  POST  /api/v1/datos/lotes/eliminacion                  {"lotes": [...], "confirmacion": "ELIMINAR",
                                                          "incluir_aprobados": false}

Cada lote es {origen, periodo, fuente_ingesta} (discord o manual). Eliminar es irreversible: exige la
confirmación literal, se niega si algún trabajo del lote está en proceso (409 lote_en_proceso) y, si
borraría contenidos aprobados, pide incluirlos explícitamente (409 aprobados_afectados).
Detalle de qué se borra y qué se conserva en services/datos_cargados.py.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.acceso import Administrador
from backend.app.core.database import get_db
from backend.app.services import datos_cargados as datos

router = APIRouter(prefix="/api/v1/datos", tags=["Datos cargados"])


class Lote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: str = Field(min_length=1, max_length=200)
    periodo: str = Field(min_length=1, max_length=200)
    fuente_ingesta: Literal["discord", "manual"]


class Seleccion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lotes: list[Lote] = Field(min_length=1, max_length=50)


class CambioVisibilidad(Seleccion):
    oculto: bool


class Eliminacion(Seleccion):
    confirmacion: Literal["ELIMINAR"]
    incluir_aprobados: bool = False


def _lotes(sel: Seleccion):
    return [l.model_dump() for l in sel.lotes]


def _no_existe(error):
    origen, periodo, fuente = error.args[0]
    return HTTPException(404, {"codigo": "lote_inexistente",
                               "mensaje": f"No hay datos del lote {origen} · {periodo} ({fuente})."})


@router.get("/lotes")
async def listar(_: Administrador, db: AsyncSession = Depends(get_db)):
    return {"items": await datos.listar_lotes(db)}


@router.patch("/lotes/visibilidad")
async def visibilidad(dto: CambioVisibilidad, _: Administrador, db: AsyncSession = Depends(get_db)):
    try:
        return {"trabajos_actualizados": await datos.cambiar_visibilidad(db, _lotes(dto), dto.oculto)}
    except datos.LoteInexistente as e:
        raise _no_existe(e) from None


@router.post("/lotes/eliminacion/vista-previa")
async def vista_previa(dto: Seleccion, _: Administrador, db: AsyncSession = Depends(get_db)):
    try:
        return datos.conteos(await datos.plan_eliminacion(db, _lotes(dto)))
    except datos.LoteInexistente as e:
        raise _no_existe(e) from None


@router.post("/lotes/eliminacion")
async def eliminar(dto: Eliminacion, admin: Administrador, db: AsyncSession = Depends(get_db)):
    try:
        return await datos.eliminar(db, _lotes(dto), dto.incluir_aprobados, admin.solicitante)
    except datos.LoteInexistente as e:
        raise _no_existe(e) from None
    except datos.EliminacionBloqueada as e:
        raise HTTPException(409, {"codigo": e.codigo, "mensaje": e.mensaje}) from None
