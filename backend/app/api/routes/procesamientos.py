from uuid import uuid4

from fastapi import APIRouter

from backend.app.schemas.procesamientos import (
    AlertaInterna,
    Almacenamiento,
    ActivoGenerado,
    IngestaRequest,
    IngestaResponse,
)

router = APIRouter(
    prefix="/api/v1/procesamientos",
    tags=["procesamientos"],
)


@router.post("", response_model=IngestaResponse)
async def crear_procesamiento(
    request: IngestaRequest,
) -> IngestaResponse:
    procesamiento_id = f"proc-{uuid4().hex[:12]}"

    cantidad_interacciones = len(request.interacciones)

    resumen = (
        f"Procesamiento recibido para {request.origen_comunidad}. "
        f"Período {request.periodo_referencia}: "
        f"{cantidad_interacciones} interacciones recibidas."
    )

    activos = [
        ActivoGenerado(
            id_activo=f"{procesamiento_id}-activo-001",
            formato="resumen",
            copy=resumen,
            fuentes=[interaccion.id for interaccion in request.interacciones],
            estado="generado",
        )
    ]

    alertas = []

    almacenamiento = Almacenamiento(
        proveedor="pendiente",
        bucket="pendiente",
        ruta=(
            f"{request.origen_comunidad}/"
            f"{request.periodo_referencia}/"
            f"procesamientos/{procesamiento_id}/"
        ),
        estado="pendiente",
    )

    return IngestaResponse(
        procesamiento_id=procesamiento_id,
        resumen_comunidad=resumen,
        activos_distribucion_generados=activos,
        alertas_internas=alertas,
        almacenamiento=almacenamiento,
    )
