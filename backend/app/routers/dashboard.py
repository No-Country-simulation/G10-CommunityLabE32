"""Indicadores del panel. Semántica documentada en docs/metricas-panel.md."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.dependencias import get_db
from backend.app.models.activo import Activo
from backend.app.models.mensaje import Mensaje
from backend.app.services.ambito import calcular_ambito, listar_ambitos

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard KPIs"])

# "indeterminado" es un resultado explícito del análisis (tono no determinable), no una ausencia.
SENTIMIENTOS = ("positivo", "negativo", "neutral", "indeterminado")
PENDIENTES_REVISION = ("generado", "revisado")


@router.get("/kpis", response_model=Dict[str, Any])
async def obtener_kpis(
    origen: Optional[str] = Query(None, max_length=200, description="origen_comunidad de los lotes"),
    periodo: Optional[str] = Query(None, max_length=100, description="periodo_referencia de los lotes"),
    db: AsyncSession = Depends(get_db),
):
    """Indicadores sin doble conteo; con origen/período se limitan a los lotes de ese ámbito."""
    try:
        ambito = await calcular_ambito(db, origen, periodo)

        consulta_mensajes = select(Mensaje.tipo, Mensaje.sentimiento_ref, func.count(Mensaje.id_mensaje))
        consulta_activos = select(Activo.estado, func.count(Activo.id_activo))
        if ambito.filtrado:
            consulta_mensajes = consulta_mensajes.where(Mensaje.id_mensaje.in_(sorted(ambito.ids_mensajes) or [""]))
            consulta_activos = consulta_activos.where(Activo.id_activo.in_(sorted(ambito.ids_activos) or [""]))
        filas_mensajes = (await db.execute(consulta_mensajes.group_by(Mensaje.tipo, Mensaje.sentimiento_ref))).all()
        filas_activos = (await db.execute(consulta_activos.group_by(Activo.estado))).all()

        total_mensajes, por_tipo = 0, {}
        sentimiento = dict.fromkeys(SENTIMIENTOS, 0)
        clasificados = 0
        for tipo, sent, n in filas_mensajes:
            total_mensajes += n
            por_tipo[tipo] = por_tipo.get(tipo, 0) + n
            llave = (sent or "").strip().lower()
            if llave in sentimiento:
                sentimiento[llave] += n
                clasificados += n
        sin_clasificar = total_mensajes - clasificados
        estado_sentimiento = ("sin_datos" if clasificados == 0 else
                              "parcial" if sin_clasificar else "completo")

        por_estado = {estado: n for estado, n in filas_activos}
        return {
            "filtro": {"origen": origen, "periodo": periodo},
            "total_mensajes": total_mensajes,
            "mensajes_por_tipo": por_tipo,
            # Solo mensajes con sentimiento clasificado; los ceros no significan "analizado".
            "distribucion_sentimiento": sentimiento,
            "sentimiento": {"estado": estado_sentimiento, "clasificados": clasificados,
                            "sin_clasificar": sin_clasificar},
            "activos_generados": sum(por_estado.values()),
            "activos_por_estado": por_estado,
            "borradores_pendientes": sum(por_estado.get(e, 0) for e in PENDIENTES_REVISION),
            "activos_aprobados": por_estado.get("aprobado", 0),
            # Aprobado no es publicado: la publicación externa (OCI/redes) no está implementada.
            "publicados": None,
            "publicacion_externa": "no_implementada",
            # Mensajes con alerta interna real (resultado del grafo), sin repetir por reenvío.
            "alertas_internas": len(ambito.alertas_por_fuente),
            "alertas_registradas": ambito.alertas_registradas,
            "trabajos_por_estado": ambito.trabajos_por_estado,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Error al calcular los indicadores.")


@router.get("/ambitos")
async def obtener_ambitos(db: AsyncSession = Depends(get_db)):
    """Pares origen/período con lotes registrados, del más reciente al más antiguo."""
    return {"items": await listar_ambitos(db)}
