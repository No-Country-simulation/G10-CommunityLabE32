from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Literal, Optional

# Importamos tu inyector de dependencias
from backend.app.core.acceso import requiere_operador, requiere_usuario
from backend.app.core.dependencias import get_db
from backend.app.models.mensaje import Mensaje
from backend.app.services.ambito import calcular_ambito
# IMPORTAMOS EL NUEVO ESQUEMA PAGINADO
from backend.app.schemas.mensaje import MensajeResponse, PaginatedMensajesResponse

router = APIRouter(prefix="/api/mensajes", tags=["Mensajes"])
SENTIMIENTOS = ("positivo", "negativo", "neutral", "indeterminado")
FiltroSentimiento = Literal["positivo", "negativo", "neutral", "indeterminado", "sin_analizar"]


async def _filtros(db, query, canal, origen, periodo):
    """Mismos filtros para la tabla y para el resumen (canal y ámbito de lotes)."""
    if canal:
        query = query.where(Mensaje.canal == canal)
    if origen or periodo:
        ambito = await calcular_ambito(db, origen, periodo)
        query = query.where(Mensaje.id_mensaje.in_(sorted(ambito.ids_mensajes) or [""]))
    return query


def _por_sentimiento(query, sentimiento):
    if sentimiento == "sin_analizar":
        # Vacío o fuera del contrato cuenta como sin analizar; nunca como neutral.
        return query.where((Mensaje.sentimiento_ref.is_(None)) | (Mensaje.sentimiento_ref.not_in(SENTIMIENTOS)))
    if sentimiento:
        return query.where(Mensaje.sentimiento_ref == sentimiento)
    return query


# Agregado sin textos ni autores: cualquier cuenta con sesión.
@router.get("/sentimiento/resumen", dependencies=[Depends(requiere_usuario)])
async def resumen_sentimiento(
    canal: str = Query(None, description="Filtrar por canal"),
    origen: str = Query(None, max_length=200),
    periodo: str = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """Conteos sobre TODO el filtro (no solo la página). Los porcentajes usan como denominador
    los mensajes analizados; los sin analizar se informan aparte."""
    query = await _filtros(db, select(Mensaje.sentimiento_ref, func.count(Mensaje.id_mensaje)),
                           canal, origen, periodo)
    filas = (await db.execute(query.group_by(Mensaje.sentimiento_ref))).all()
    por_valor = dict.fromkeys(SENTIMIENTOS, 0)
    total = 0
    for valor, n in filas:
        total += n
        if valor in por_valor:
            por_valor[valor] += n
    analizados = sum(por_valor.values())
    return {"filtro": {"canal": canal, "origen": origen, "periodo": periodo},
            "total": total, "analizados": analizados, "sin_analizar": total - analizados,
            "por_valor": por_valor,
            "porcentaje_sobre_analizados": {k: (round(100 * v / analizados, 1) if analizados else None)
                                            for k, v in por_valor.items()},
            "denominador": "analizados",
            "estado": "sin_datos" if analizados == 0 else ("parcial" if analizados < total else "completo")}

# AÑADIMOS EL RESPONSE_MODEL CORRECTO AQUÍ
# Textos y autores: datos comunitarios privados, solo operadores.
@router.get("", response_model=PaginatedMensajesResponse, dependencies=[Depends(requiere_operador)])
async def obtener_mensajes(
    canal: str = Query(None, description="Filtrar por canal"),
    origen: str = Query(None, max_length=200, description="origen_comunidad de los lotes"),
    periodo: str = Query(None, max_length=100, description="periodo_referencia de los lotes"),
    sentimiento: Optional[FiltroSentimiento] = Query(None, description="Filtro en servidor"),
    skip: int = Query(0, ge=0, description="Registros a saltar (offset)"),
    limit: int = Query(10, ge=1, le=100, description="Registros por página"),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene listado de interacciones con paginación real en Base de Datos (O(1) en RAM).
    Con origen/período, solo los mensajes de los lotes de ese ámbito; más recientes primero.
    """
    query = _por_sentimiento(await _filtros(db, select(Mensaje), canal, origen, periodo), sentimiento)
    count_query = _por_sentimiento(
        await _filtros(db, select(func.count(Mensaje.id_mensaje)), canal, origen, periodo), sentimiento)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.order_by(Mensaje.fecha.desc(), Mensaje.id_mensaje).offset(skip).limit(limit)
    
    try:
        result = await db.execute(query)
        mensajes = result.scalars().all()
        
        return {
            "items": mensajes,
            "total": total
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno en la base de datos")


    
@router.post("/procesamientos", status_code=202, dependencies=[Depends(requiere_operador)])
async def procesar_lote_nuevo(
    file: UploadFile = File(...),
    origen_comunidad: str = Form(...),
    periodo_referencia: str = Form(...),
    cierre_periodo: bool = Form(False),
):
    from backend.app.api.routes.trabajos import encolar_archivo
    return await encolar_archivo(file, origen_comunidad, periodo_referencia, cierre_periodo)
