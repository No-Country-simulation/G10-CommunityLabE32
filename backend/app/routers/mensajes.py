from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

# Importamos tu inyector de dependencias
from backend.app.core.dependencias import get_db
from backend.app.models.mensaje import Mensaje
# IMPORTAMOS EL NUEVO ESQUEMA PAGINADO
from backend.app.schemas.mensaje import MensajeResponse, PaginatedMensajesResponse

router = APIRouter(prefix="/api/mensajes", tags=["Mensajes"])

# AÑADIMOS EL RESPONSE_MODEL CORRECTO AQUÍ
@router.get("", response_model=PaginatedMensajesResponse)
async def obtener_mensajes(
    canal: str = Query(None, description="Filtrar por canal"),
    skip: int = Query(0, ge=0, description="Registros a saltar (offset)"),
    limit: int = Query(10, ge=1, le=100, description="Registros por página"),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene listado de interacciones con paginación real en Base de Datos (O(1) en RAM).
    """
    query = select(Mensaje)
    count_query = select(func.count(Mensaje.id_mensaje))
    
    if canal:
        query = query.where(Mensaje.canal == canal)
        count_query = count_query.where(Mensaje.canal == canal)
        
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset(skip).limit(limit)
    
    try:
        result = await db.execute(query)
        mensajes = result.scalars().all()
        
        return {
            "items": mensajes,
            "total": total
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno en la base de datos")


    
@router.post("/procesamientos", status_code=202)
async def procesar_lote_nuevo(
    file: UploadFile = File(...),
    origen_comunidad: str = Form(...),
    periodo_referencia: str = Form(...),
    cierre_periodo: bool = Form(False),
):
    from backend.app.api.routes.trabajos import encolar_archivo
    return await encolar_archivo(file, origen_comunidad, periodo_referencia, cierre_periodo)
