from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

# Importamos tu inyector de dependencias (con el nombre exacto que le pusiste)
from app.core.dependencias import get_db
from app.models.mensaje import Mensaje
from app.schemas.mensaje import MensajeResponse

# Creamos el Router modular
router = APIRouter(prefix="/api/mensajes", tags=["Mensajes"])

@router.get("/", response_model=List[MensajeResponse])
async def obtener_mensajes(
    canal: str = Query(None, description="Filtrar por canal (ej. #dudas-tecnicas)"),
    limit: int = Query(50, ge=1, le=100, description="Protección: Límite máximo de 100"),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el listado de interacciones y repositorios.
    Implementa filtros dinámicos y protección de paginación.
    """
    query = select(Mensaje)
    
    # Filtro dinámico: Si el frontend pide un canal específico, lo filtramos
    if canal:
        query = query.where(Mensaje.canal == canal)
        
    query = query.limit(limit)
    
    try:
        result = await db.execute(query)
        mensajes = result.scalars().all()
        return mensajes
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno en la base de datos")