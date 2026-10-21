from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from typing import Optional
import asyncio
import math
import os

from backend.app.core.acceso import requiere_operador
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
    FuenteMensajeDetalle,
    SolicitudPosts,
)
from backend.app.services.ambito import ids_activos_de_trabajo
from backend.app.services.oci import subir_activo_aprobado_oci

router = APIRouter(prefix="/api/curaduria", tags=["Curaduría de Activos"])

# Reglas de la máquina de estados según la propuesta (Slide 8). Aprobar desde «generado» es revisar y
# aprobar en la misma acción: la interfaz de Curaduría solo tiene Pendientes, Denegados y Aprobados.
TRANSICIONES_VALIDAS = {
    "generado": {"revisado", "aprobado", "rechazado"},
    "revisado": {"aprobado", "rechazado", "generado"},
    "aprobado": {"revisado"},
    "rechazado": {"revisado"}
}

@router.get("/activos", response_model=PaginatedActivosResponse, dependencies=[Depends(requiere_operador)])
async def listar_activos(
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(15, ge=1, le=100, description="Cantidad de registros por página"),
    estado: Optional[EstadoActivoEnum] = Query(None),
    formato: Optional[FormatoActivoEnum] = Query(None),
    trabajo: Optional[str] = Query(None, max_length=64, description="Solo activos de este trabajo"),
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
    if trabajo:
        ids = sorted(await ids_activos_de_trabajo(db, trabajo)) or [""]
        query = query.where(Activo.id_activo.in_(ids))
        count_query = count_query.where(Activo.id_activo.in_(ids))

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

@router.get("/activos/{id_activo}", response_model=ActivoDetalleResponse, dependencies=[Depends(requiere_operador)])
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
        advertencias_fidelidad=activo.advertencias_fidelidad,
        posts_redes=activo.posts_redes,
        fecha_creacion=activo.fecha_creacion,
        fecha_actualizacion=activo.fecha_actualizacion,
        fuentes_detalle=fuentes_detalle,
        historial=await _historial(db, activo.id_activo),
        generaciones_restantes=max(0, _max_generaciones() - (activo.generaciones_ia or 0))
                               if activo.formato == "linkedin" else None,
    )

@router.patch("/activos/{id_activo}", response_model=ActivoResponse)
async def actualizar_activo(
    id_activo: str,
    dto: ActivoUpdateDTO,
    db: AsyncSession = Depends(get_db),
    operador=Depends(requiere_operador),
):
    """
    Permite editar el copy, versionar los cambios y transicionar estados de curaduría.
    Toda modificación (editar, revisar, aprobar) requiere rol operador. Editar el texto de un activo aprobado invalida la
    aprobación (vuelve a «revisado») y deja desactualizado cualquier banner anterior.
    """
    query = select(Activo).where(Activo.id_activo == id_activo)
    result = await db.execute(query)
    activo = result.scalar_one_or_none()

    if not activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado.")
    if dto.posts_redes is not None and dto.copy is not None and dto.copy != dto.posts_redes.linkedin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="copy y posts_redes.linkedin deben coincidir.")
    nuevo_copy = dto.posts_redes.linkedin if dto.posts_redes is not None else dto.copy
    estado_anterior = activo.estado

    # 1. Validar máquina de estados
    if dto.estado and dto.estado.value != activo.estado:
        permitidos = TRANSICIONES_VALIDAS.get(activo.estado, set())
        if dto.estado.value not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Transición inválida: no se puede pasar de '{activo.estado}' a '{dto.estado.value}'."
            )
        activo.estado = dto.estado.value
        
        # Si se aprueba, lo subimos a OCI en /aprobados
        if dto.estado.value == "aprobado":
            await subir_activo_aprobado_oci(
                id_activo=activo.id_activo,
                formato=activo.formato,
                copy=nuevo_copy if nuevo_copy else activo.copy
            )

    # 2. Control de cambios y versionado (LinkedIn o X: cualquiera de las dos es una versión nueva)
    redes_actuales = activo.posts_redes or {"linkedin": activo.copy, "x": ""}
    cambia_redes = dto.posts_redes is not None and dto.posts_redes.model_dump() != redes_actuales
    cambia_texto = (nuevo_copy is not None and nuevo_copy != activo.copy) or cambia_redes
    if cambia_texto:
        activo.copy = nuevo_copy if nuevo_copy is not None else activo.copy
        if dto.posts_redes is not None:
            activo.posts_redes = dto.posts_redes.model_dump()
        activo.version += 1
        # Un texto aprobado que cambia sin aprobarse de nuevo en la misma acción deja de estar aprobado.
        if activo.estado == "aprobado" and not (dto.estado and dto.estado.value == "aprobado"):
            activo.estado = "revisado"

    if dto.comentario_curador is not None:
        activo.comentario_curador = dto.comentario_curador

    actor = getattr(operador, "solicitante", None)
    if cambia_texto:
        await _registrar(db, activo, "edicion", actor, f"Texto editado (versión {activo.version}).")
    if activo.estado != estado_anterior and not (cambia_texto and dto.estado is None):
        await _registrar(db, activo, "estado", actor, dto.comentario_curador)
    await db.commit()
    await db.refresh(activo)
    return activo


# --- Historial de Curaduría -------------------------------------------------------------------
ACTORES = {"ia": "IA", "operador:token-compartido": "Token de operador", "puente": "Puente de Discord"}


async def _registrar(db, activo, evento, actor, comentario=None):
    await db.execute(text("""INSERT INTO activos_historial (id_activo, evento, estado, version, actor, comentario)
        VALUES (:id, :evento, :estado, :version, :actor, :comentario)"""),
        {"id": activo.id_activo, "evento": evento, "estado": activo.estado, "version": activo.version,
         "actor": actor, "comentario": comentario})


async def _historial(db, id_activo):
    """Eventos en orden estable (fecha, id). El actor «usuario:<id>» se muestra con el nombre de la cuenta."""
    filas = (await db.execute(text("""SELECT h.evento, h.estado, h.version, h.fecha, h.comentario, h.actor,
            coalesce(u.full_name, u.email) AS nombre
        FROM activos_historial h LEFT JOIN usuarios u ON h.actor = 'usuario:' || u.id::text
        WHERE h.id_activo = :id ORDER BY h.fecha, h.id"""), {"id": id_activo})).mappings().all()
    return [{"evento": f["evento"], "estado": f["estado"], "version": f["version"], "fecha": f["fecha"],
             "comentario": f["comentario"], "actor": f["nombre"] or ACTORES.get(f["actor"], f["actor"])}
            for f in filas]


# --- «Generar post»: versiones LinkedIn y X con IA ---------------------------------------------
def _max_generaciones():
    try:
        return max(0, min(20, int(os.environ.get("CURADURIA_MAX_GENERACIONES", "3"))))
    except ValueError:
        return 3


def _cliente_ia():
    from pipelines.communitylab.gemini import ClienteGemini, ConfiguracionGemini
    return ClienteGemini(ConfiguracionGemini.desde_entorno())


def _generar_textos(peticion):
    from pipelines.communitylab.generadores.posts_redes import generar_posts_redes
    return generar_posts_redes(peticion, _cliente_ia())


async def _peticion_post(db, mensajes):
    """Misma petición que arma el grafo para un logro: las fuentes del activo y el ámbito de su lote."""
    ambito = (await db.execute(text("""SELECT entrada->>'origen_comunidad' AS origen,
            entrada->>'periodo_referencia' AS periodo
        FROM trabajos_worker
        WHERE entrada->'interacciones' @> jsonb_build_array(jsonb_build_object('id', CAST(:id AS text)))
        ORDER BY creado DESC LIMIT 1"""), {"id": mensajes[0].id_mensaje})).mappings().first()
    return {"ruta": "logro", "formato": "post_linkedin_x",
            "origen_comunidad": (ambito or {}).get("origen") or "comunidad",
            "periodo_referencia": (ambito or {}).get("periodo") or "sin período",
            "fuentes": [m.id_mensaje for m in mensajes],
            "interacciones": [{"id": m.id_mensaje, "autor": m.autor, "canal": m.canal, "fecha": str(m.fecha),
                               "texto": m.texto[:4000]} for m in mensajes]}


def _error_ia(http, codigo, mensaje):
    return HTTPException(http, {"codigo": codigo, "mensaje": mensaje})


@router.post("/activos/{id_activo}/posts/generar")
async def generar_posts(id_activo: str, solicitud: Optional[SolicitudPosts] = None,
                        db: AsyncSession = Depends(get_db), operador=Depends(requiere_operador)):
    """Genera las versiones LinkedIn y X desde las fuentes del logro. No guarda el texto ni aprueba:
    la persona lo revisa y lo guarda con PATCH. Cada borrador admite CURADURIA_MAX_GENERACIONES (3)."""
    from pipelines.communitylab.gemini import ErrorConfiguracionIA, ErrorCuotaIA, ErrorIA
    activo = (await db.execute(select(Activo).where(Activo.id_activo == id_activo).with_for_update())
              ).scalar_one_or_none()
    if not activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado.")
    if activo.formato != "linkedin":
        raise _error_ia(409, "formato_sin_posts", "Solo los logros (formato LinkedIn) admiten «Generar post».")
    limite = _max_generaciones()
    if (activo.generaciones_ia or 0) >= limite:
        raise _error_ia(429, "limite_generaciones", f"Este borrador ya usó sus {limite} generaciones con IA.")
    mensajes = (await db.execute(select(Mensaje).where(Mensaje.id_mensaje.in_(activo.fuentes or [])))).scalars().all()
    if not mensajes:
        raise _error_ia(409, "sin_fuentes", "El borrador no tiene mensajes fuente disponibles para generar.")
    peticion = await _peticion_post(db, sorted(mensajes, key=lambda m: m.id_mensaje))
    # Se reserva el intento antes de llamar a la IA: un doble clic espera el bloqueo y ve el contador ya sumado.
    activo.generaciones_ia = (activo.generaciones_ia or 0) + 1
    await db.commit()

    async def devolver_intento():
        await db.execute(text("UPDATE activos SET generaciones_ia = greatest(generaciones_ia - 1, 0) "
                              "WHERE id_activo = :id"), {"id": id_activo})
        await db.commit()

    try:
        textos = await asyncio.to_thread(_generar_textos, peticion)
    except ErrorConfiguracionIA:
        await devolver_intento()
        raise _error_ia(503, "ia_no_configurada", "La IA no está configurada en el servidor.") from None
    except ErrorCuotaIA:
        await devolver_intento()
        raise _error_ia(429, "cuota_ia", "Se agotó la cuota de la IA; inténtalo más tarde.") from None
    except (ErrorIA, ValueError):
        await devolver_intento()
        raise _error_ia(502, "ia_fallo", "La IA no devolvió textos válidos; inténtalo de nuevo.") from None

    activo = (await db.execute(select(Activo).where(Activo.id_activo == id_activo))).scalar_one()
    await db.refresh(activo)
    usadas = activo.generaciones_ia
    await _registrar(db, activo, "posts_generados", getattr(operador, "solicitante", None),
                     f"Textos LinkedIn y X generados con IA ({usadas} de {limite}); pendientes de guardar.")
    await db.commit()
    return {"linkedin": textos["linkedin"], "x": textos["x"], "generaciones_restantes": max(0, limite - usadas)}