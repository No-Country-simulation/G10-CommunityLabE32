from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any

from app.core.dependencias import get_db
from app.models.mensaje import Mensaje
from app.models.activo import Activo

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard KPIs"])

@router.get("/kpis", response_model=Dict[str, Any])
async def obtener_kpis(db: AsyncSession = Depends(get_db)):
    """
    Calcula las métricas principales ejecutando agregaciones directamente en Postgres/SQLite
    para garantizar O(1) en transferencia de red y máxima seguridad de memoria.
    """
    try:
        # 1. Total de mensajes ingeridos
        total_mensajes = await db.execute(select(func.count(Mensaje.id_mensaje)))
        total_mensajes = total_mensajes.scalar() or 0

        # 2. Distribución de sentimientos (Group By)
        sentimiento_query = select(Mensaje.sentimiento_ref, func.count(Mensaje.id_mensaje)).group_by(Mensaje.sentimiento_ref)
        sentimiento_result = await db.execute(sentimiento_query)
        
        # Mapeamos los resultados (ej: {"positivo": 150, "negativo": 20, None: 5})
        distribucion_sentimiento = {"positivo": 0, "negativo": 0, "neutral": 0}
        for sent, count in sentimiento_result.all():
            llave = sent.lower() if sent else "neutral"
            if llave in distribucion_sentimiento:
                distribucion_sentimiento[llave] += count
            else:
                distribucion_sentimiento["neutral"] += count

        # 3. Estado del embudo de Curaduría (Activos)
        activos_query = select(Activo.estado, func.count(Activo.id_activo)).group_by(Activo.estado)
        activos_result = await db.execute(activos_query)
        
        stats_activos = {estado: count for estado, count in activos_result.all()}
        activos_generados = sum(stats_activos.values())
        activos_aprobados = stats_activos.get("aprobado", 0)

        # 4. Alertas internas (Mensajes tipo 'bloqueo' o canal '#alertas')
        alertas_query = select(func.count(Mensaje.id_mensaje)).where(
            (Mensaje.tipo == 'bloqueo') | (Mensaje.texto.ilike('%bloqueo%')) | (Mensaje.texto.ilike('%error%'))
        )
        alertas_result = await db.execute(alertas_query)
        alertas_internas = alertas_result.scalar() or 0

        return {
            "total_mensajes": total_mensajes,
            "distribucion_sentimiento": distribucion_sentimiento,
            "activos_generados": activos_generados,
            "activos_aprobados": activos_aprobados,
            "alertas_internas": alertas_internas
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al calcular KPIs: {str(e)}")