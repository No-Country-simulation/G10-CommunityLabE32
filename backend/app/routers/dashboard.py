"""Indicadores del panel. Semántica documentada en docs/metricas-panel.md."""
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.acceso import requiere_operador, requiere_usuario
from backend.app.core.dependencias import get_db
from backend.app.models.activo import Activo
from backend.app.models.mensaje import Mensaje
from backend.app.services.ambito import alertas_internas, calcular_ambito, listar_ambitos, parsear_lotes

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard KPIs"])

# "indeterminado" es un resultado explícito del análisis (tono no determinable), no una ausencia.
SENTIMIENTOS = ("positivo", "negativo", "neutral", "indeterminado")
PENDIENTES_REVISION = ("generado", "revisado")
FuenteIngesta = Literal["discord", "manual"]
DESCRIPCION_LOTES = ('JSON [{"origen","periodo","fuente_ingesta"}]: unión sin duplicados. '
                     '"[]" = ningún lote (todo en cero). Prevalece sobre origen/periodo/fuente_ingesta.')


def lotes_o_422(valor):
    try:
        return parsear_lotes(valor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/kpis", response_model=Dict[str, Any], dependencies=[Depends(requiere_usuario)])
async def obtener_kpis(
    origen: Optional[str] = Query(None, max_length=200, description="origen_comunidad de los lotes"),
    periodo: Optional[str] = Query(None, max_length=100, description="periodo_referencia de los lotes"),
    fuente_ingesta: Optional[FuenteIngesta] = Query(None, description="discord o manual"),
    lotes: Optional[str] = Query(None, max_length=8000, description=DESCRIPCION_LOTES),
    db: AsyncSession = Depends(get_db),
):
    """Indicadores sin doble conteo; con origen/período se limitan a los lotes de ese ámbito."""
    seleccion = lotes_o_422(lotes)
    try:
        ambito = await calcular_ambito(db, origen, periodo, fuente_ingesta, seleccion)

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
            "filtro": {"origen": origen, "periodo": periodo, "fuente_ingesta": fuente_ingesta, "lotes": seleccion},
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


@router.get("/ambitos", dependencies=[Depends(requiere_usuario)])
async def obtener_ambitos(db: AsyncSession = Depends(get_db)):
    """Pares origen/período con lotes registrados, del más reciente al más antiguo."""
    return {"items": await listar_ambitos(db)}


@router.get("/alertas", dependencies=[Depends(requiere_operador)])
async def listar_alertas(
    skip: int = Query(0, ge=0),
    limit: int = Query(9, ge=1, le=100),
    origen: Optional[str] = Query(None, max_length=200),
    periodo: Optional[str] = Query(None, max_length=100),
    fuente_ingesta: Optional[FuenteIngesta] = Query(None),
    lotes: Optional[str] = Query(None, max_length=8000, description=DESCRIPCION_LOTES),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de las alertas internas: mismo conjunto y total que el KPI `alertas_internas`.

    Incluye el mensaje que la originó (texto y autor: solo operadores), el motivo, el lote y el trabajo.
    Ordenadas por fecha del mensaje, de la más reciente a la más antigua.
    """
    por_fuente = await alertas_internas(db, origen, periodo, fuente_ingesta, lotes_o_422(lotes))
    mensajes = {}
    if por_fuente:
        filas = (await db.execute(select(Mensaje).where(Mensaje.id_mensaje.in_(sorted(por_fuente))))).scalars().all()
        mensajes = {m.id_mensaje: m for m in filas}
    items = []
    for id_mensaje, alerta in por_fuente.items():
        m = mensajes.get(id_mensaje)
        items.append({**alerta, "autor": m.autor if m else None, "canal": m.canal if m else None,
                      "fecha": m.fecha if m else None, "texto": m.texto if m else None,
                      "sentimiento_ref": m.sentimiento_ref if m else None})
    items.sort(key=lambda a: (a["fecha"] or "", a["id_mensaje"]), reverse=True)
    return {"items": items[skip:skip + limit], "total": len(items)}
