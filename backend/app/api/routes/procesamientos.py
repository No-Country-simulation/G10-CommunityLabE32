from fastapi import APIRouter

from backend.app.schemas.procesamientos import (
    IngestaRequest,
    IngestaResponse,
    ActivoGenerado,
    AlertaInterna,
    AlmacenamientoOCI,
)
from fastapi import File, UploadFile, Form
from backend.app.services.ingestion import procesar_lote

router = APIRouter(
    prefix="/api/v1/procesamientos",
    tags=["Procesamientos"],
)


@router.post("", response_model=IngestaResponse)
def crear_procesamiento(lote: IngestaRequest):
    return IngestaResponse(
        procesamiento_id="proc-mock-2026-001",
        resumen_comunidad=(
            f"Procesadas {len(lote.interacciones)} interacciones "
            f"para el período {lote.periodo_referencia}."
        ),
        activos_distribucion_generados=[
            ActivoGenerado(
                id_activo="act-01",
                formato="linkedin",
                copy=(
                    "¡Orgullo en la comunidad! Uno de nuestros miembros "
                    "consiguió su primer empleo Dev Jr. tras mostrar su "
                    "portafolio de IA. #CommunityHighlights"
                ),
                fuentes=["m-01"],
                estado="generado",
            ),
            ActivoGenerado(
                id_activo="act-02",
                formato="faq",
                copy=(
                    "FAQ Técnico: ¿Cómo manejar reintentos en LangGraph? "
                    "Configura una condición de fallback y limita "
                    "reintentos en el router."
                ),
                fuentes=["m-02", "m-03"],
                estado="generado",
            ),
            ActivoGenerado(
                id_activo="act-03",
                formato="newsletter",
                copy=(
                    "Resumen semanal: Gran mentoría sobre portafolios de IA "
                    "y resolución de dudas sobre OCI Storage."
                ),
                fuentes=["m-04", "m-05"],
                estado="generado",
            ),
        ],
        alertas_internas=[
            AlertaInterna(
                id_alerta="alt-01",
                nivel="bloqueo",
                mensaje=(
                    "Usuario reportó timeout 504 intermitente al intentar "
                    "acceder al bucket de OCI."
                ),
                fuente="m-06",
            )
        ],
        almacenamiento_oci=AlmacenamientoOCI(
            bucket="communitylab-alwaysfree-bucket",
            ruta=(
                f"demo/{lote.periodo_referencia}/lotes/"
                "proc-mock-2026-001/paquete.json"
            ),
            estado="simulado_pendiente_worker",
        ),
    )


@router.post("/upload", response_model=IngestaResponse)
async def procesar_lote_archivo(
    file: UploadFile = File(...),
    origen_comunidad: str = Form(...),
    periodo_referencia: str = Form(...)
):
    content = await file.read()
    
    # Llamada al módulo de ingestión (Validar, Normalizar, Deduplicar)
    interacciones = procesar_lote(content, file.filename)
    
    # Retornar una respuesta mock basada en el lote procesado
    return IngestaResponse(
        procesamiento_id="proc-mock-2026-002",
        resumen_comunidad=(
            f"Archivo {file.filename} procesado: {len(interacciones)} interacciones "
            f"válidas y únicas para el período {periodo_referencia}."
        ),
        activos_distribucion_generados=[],
        alertas_internas=[],
        almacenamiento_oci=AlmacenamientoOCI(
            bucket="communitylab-alwaysfree-bucket",
            ruta=(
                f"demo/{periodo_referencia}/lotes/"
                f"proc-mock-2026-002/{file.filename}"
            ),
            estado="simulado_pendiente_worker",
        ),
    )
