from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional
import math

from backend.app.core.dependencias import get_db
from backend.app.models.activo import Activo
from backend.app.models.mensaje import Mensaje
from backend.app.schemas.curaduria import (
    ActivoResponse,
    ActivoDetalleResponse,
    ActivoUpdateDTO,
    PaginatedActivosResponse,
    EstadoActivoEnum,
    FormatoActivoEnum,
    FuenteMensajeDetalle
)

router = APIRouter(prefix="/api/curaduria", tags=["Curaduría de Activos"])

# Reglas de la máquina de estados según la propuesta (Slide 8)
TRANSICIONES_VALIDAS = {
    "generado": {"revisado", "rechazado"},
    "revisado": {"aprobado", "rechazado", "generado"},
    "aprobado": {"revisado"},
    "rechazado": {"revisado"}
}

@router.get("/activos", response_model=PaginatedActivosResponse)
async def listar_activos(
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(15, ge=1, le=100, description="Cantidad de registros por página"),
    estado: Optional[EstadoActivoEnum] = Query(None),
    formato: Optional[FormatoActivoEnum] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Paginación eficiente calculada en base de datos.
    Soporta 3,000+ registros sin cargar toda la tabla en memoria RAM.
    """
    query = select(Activo)
    count_query = select(func.count(Activo.id_activo))

    if estado:
        query = query.where(Activo.estado == estado.value)
        count_query = count_query.where(Activo.estado == estado.value)
    if formato:
        query = query.where(Activo.formato == formato.value)
        count_query = count_query.where(Activo.formato == formato.value)

    # 1. Total de registros para la paginación del frontend
    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0
    total_pages = math.ceil(total / limit) if total > 0 else 1

    # 2. Paginación en SQL (LIMIT / OFFSET)
    offset = (page - 1) * limit
    paginated_query = query.order_by(desc(Activo.fecha_actualizacion)).offset(offset).limit(limit)
    
    result = await db.execute(paginated_query)
    activos = result.scalars().all()

    return PaginatedActivosResponse(
        items=activos,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/activos/{id_activo}", response_model=ActivoDetalleResponse)
async def obtener_detalle_activo(id_activo: str, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el activo y recupera los mensajes fuente reales (Ground Truth) de la tabla mensajes.
    """
    query = select(Activo).where(Activo.id_activo == id_activo)
    result = await db.execute(query)
    activo = result.scalar_one_or_none()

    if not activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"El activo con ID {id_activo} no existe."
        )

    # Cargar los mensajes fuente cruzando activo.fuentes con mensaje.id_mensaje
    fuentes_detalle = []
    if activo.fuentes:
        query_fuentes = select(Mensaje).where(Mensaje.id_mensaje.in_(activo.fuentes))
        fuentes_res = await db.execute(query_fuentes)
        mensajes_db = fuentes_res.scalars().all()
        
        fuentes_detalle = [
            FuenteMensajeDetalle(
                id_mensaje=m.id_mensaje,
                autor=m.autor,
                canal=m.canal,
                fecha=m.fecha,
                texto=m.texto
            ) for m in mensajes_db
        ]

    return ActivoDetalleResponse(
        id_activo=activo.id_activo,
        formato=activo.formato,
        titulo=activo.titulo,
        copy=activo.copy,
        estado=activo.estado,
        fuentes=activo.fuentes,
        version=activo.version,
        comentario_curador=activo.comentario_curador,
        fecha_creacion=activo.fecha_creacion,
        fecha_actualizacion=activo.fecha_actualizacion,
        fuentes_detalle=fuentes_detalle
    )

@router.patch("/activos/{id_activo}", response_model=ActivoResponse)
async def actualizar_activo(
    id_activo: str,
    dto: ActivoUpdateDTO,
    db: AsyncSession = Depends(get_db)
):
    """
    Permite editar el copy, versionar los cambios y transicionar estados de curaduría.
    """
    query = select(Activo).where(Activo.id_activo == id_activo)
    result = await db.execute(query)
    activo = result.scalar_one_or_none()

    if not activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado.")

    # 1. Validar máquina de estados
    if dto.estado and dto.estado.value != activo.estado:
        permitidos = TRANSICIONES_VALIDAS.get(activo.estado, set())
        if dto.estado.value not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Transición inválida: no se puede pasar de '{activo.estado}' a '{dto.estado.value}'."
            )
        activo.estado = dto.estado.value

    # 2. Control de cambios y versionado
    if dto.copy is not None and dto.copy != activo.copy:
        activo.copy = dto.copy
        activo.version += 1

    if dto.comentario_curador is not None:
        activo.comentario_curador = dto.comentario_curador

    await db.commit()
    await db.refresh(activo)
    return activo