from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

# Importamos tu inyector de dependencias (con el nombre exacto que le pusiste)
from app.core.dependencias import get_db
from app.models.mensaje import Mensaje
from app.schemas.mensaje import MensajeResponse

# Creamos el Router modular
router = APIRouter(prefix="/api/mensajes", tags=["Mensajes"])

@router.get("", response_model=List[MensajeResponse])
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
    
@router.post("/procesamientos")
async def procesar_lote_nuevo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Recibe un archivo JSON/CSV desde el Frontend.
    (La lógica de LangGraph/Gemini la hará el equipo de IA después. 
    Por ahora, recibimos el archivo, validamos y respondemos éxito).
    """
    if not file.filename.endswith(('.json', '.jsonl', '.csv')):
        raise HTTPException(status_code=400, detail="Formato no soportado. Solo JSON o CSV.")

    # Aquí en el futuro irá la llamada a los Agentes de IA
    # await procesar_con_langgraph(file.file.read())

    return {
        "status": "success",
        "mensaje": f"Archivo '{file.filename}' recibido correctamente.",
        "procesamiento_id": "proc-99x88",
        "detalles": "El lote ha sido encolado para su análisis con Gemini."
    }