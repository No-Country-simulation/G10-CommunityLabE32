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
from backend.app.services.autores import visible
from pipelines.communitylab.temas import agrupar_temas

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
    incluir_pruebas: bool = Query(False, description="Incluir lotes marcados como de prueba"),
    db: AsyncSession = Depends(get_db),
):
    """Indicadores sin doble conteo; con origen/período se limitan a los lotes de ese ámbito."""
    seleccion = lotes_o_422(lotes)
    try:
        ambito = await calcular_ambito(db, origen, periodo, fuente_ingesta, seleccion, incluir_pruebas)

        consulta_mensajes = select(Mensaje.tipo, Mensaje.sentimiento_ref, func.count(Mensaje.id_mensaje))
        consulta_activos = select(Activo.estado, func.count(Activo.id_activo))
        if ambito.filtrado:
            consulta_mensajes = consulta_mensajes.where(Mensaje.id_mensaje.in_(sorted(ambito.ids_mensajes) or [""]))
            consulta_activos = consulta_activos.where(Activo.id_activo.in_(sorted(ambito.ids_activos) or [""]))
        else:   # vista global: sin lo que solo existe en lotes de prueba
            if ambito.excluidos_mensajes:
                consulta_mensajes = consulta_mensajes.where(Mensaje.id_mensaje.not_in(sorted(ambito.excluidos_mensajes)))
            if ambito.excluidos_activos:
                consulta_activos = consulta_activos.where(Activo.id_activo.not_in(sorted(ambito.excluidos_activos)))
        filas_mensajes = (await db.execute(consulta_mensajes.group_by(Mensaje.tipo, Mensaje.sentimiento_ref))).all()
        # Temas: mismo conjunto de mensajes que los demás indicadores (ámbito o vista global sin pruebas).
        tema = func.lower(func.trim(Mensaje.tema_ref))
        consulta_temas = select(tema, func.count(Mensaje.id_mensaje)).where(Mensaje.tema_ref.is_not(None),
                                                                           func.trim(Mensaje.tema_ref) != "")
        if ambito.filtrado:
            consulta_temas = consulta_temas.where(Mensaje.id_mensaje.in_(sorted(ambito.ids_mensajes) or [""]))
        elif ambito.excluidos_mensajes:
            consulta_temas = consulta_temas.where(Mensaje.id_mensaje.not_in(sorted(ambito.excluidos_mensajes)))
        # Variantes del mismo tema (tildes, artículos, plural) se suman y se muestra la mejor escrita.
        filas_temas = agrupar_temas((await db.execute(consulta_temas.group_by(tema))).all(), limite=10)
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
            # Temas que la IA asignó a los mensajes, con sus variantes agrupadas, del más frecuente al menos.
            "temas_principales": [{"tema": t, "cantidad": n} for t, n in filas_temas],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Error al calcular los indicadores.")


@router.get("/ambitos", dependencies=[Depends(requiere_usuario)])
async def obtener_ambitos(incluir_pruebas: bool = Query(False), db: AsyncSession = Depends(get_db)):
    """Pares origen/período con lotes registrados, del más reciente al más antiguo."""
    return {"items": await listar_ambitos(db, incluir_pruebas)}


@router.get("/alertas", dependencies=[Depends(requiere_operador)])
async def listar_alertas(
    skip: int = Query(0, ge=0),
    limit: int = Query(9, ge=1, le=100),
    origen: Optional[str] = Query(None, max_length=200),
    periodo: Optional[str] = Query(None, max_length=100),
    fuente_ingesta: Optional[FuenteIngesta] = Query(None),
    lotes: Optional[str] = Query(None, max_length=8000, description=DESCRIPCION_LOTES),
    incluir_pruebas: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de las alertas internas: mismo conjunto y total que el KPI `alertas_internas`.

    Incluye el mensaje que la originó (texto y autor: solo operadores), el motivo, el lote y el trabajo.
    Ordenadas por fecha del mensaje, de la más reciente a la más antigua.
    """
    por_fuente = await alertas_internas(db, origen, periodo, fuente_ingesta, lotes_o_422(lotes), incluir_pruebas)
    mensajes = {}
    if por_fuente:
        filas = (await db.execute(select(Mensaje).where(Mensaje.id_mensaje.in_(sorted(por_fuente))))).scalars().all()
        mensajes = {m.id_mensaje: m for m in filas}
    items = []
    for id_mensaje, alerta in por_fuente.items():
        m = mensajes.get(id_mensaje)
        items.append({**alerta, "autor": visible(m.autor, m.autor_nombre) if m else None,
                      "autor_id": m.autor if m else None, "canal": m.canal if m else None,
                      "fecha": m.fecha if m else None, "texto": m.texto if m else None,
                      "sentimiento_ref": m.sentimiento_ref if m else None})
    items.sort(key=lambda a: (a["fecha"] or "", a["id_mensaje"]), reverse=True)
    return {"items": items[skip:skip + limit], "total": len(items)}
