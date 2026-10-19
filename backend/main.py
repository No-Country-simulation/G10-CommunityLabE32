from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="CommunityLab API",
    version="1.0.0",
    description="Motor de Ingesta y Transformación Comunitaria - Mock Inicial"
)

# CORS habilitado para comunicación con Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Esquema de Entrada ---
class Interaccion(BaseModel):
    id: str
    autor: str
    canal: str
    fecha: str
    texto: str

class IngestaRequest(BaseModel):
    origen_comunidad: str = Field(..., example="discord_comunidad_alura")
    periodo_referencia: str = Field(..., example="2026-W38")
    interacciones: List[Interaccion]

# --- Esquema de Salida (Mock) ---
class ActivoGenerado(BaseModel):
    id_activo: str
    formato: str
    copy: str
    fuentes: List[str]
    estado: str

class AlertaInterna(BaseModel):
    id_alerta: str
    nivel: str
    mensaje: str
    fuente: str

class AlmacenamientoOCI(BaseModel):
    bucket: str
    ruta: str
    estado: str

class IngestaResponse(BaseModel):
    procesamiento_id: str
    resumen_comunidad: str
    activos_distribucion_generados: List[ActivoGenerado]
    alertas_internas: List[AlertaInterna]
    almacenamiento_oci: AlmacenamientoOCI

# --- Endpoints ---
@app.get("/health")
def healthcheck():
    return {"status": "healthy", "service": "backend-api"}

@app.post("/api/v1/procesamientos", response_model=IngestaResponse)
async def procesar_lote_comunidad(lote: IngestaRequest):
    return IngestaResponse(
        procesamiento_id="proc-mock-2026-001",
        resumen_comunidad=f"Procesadas {len(lote.interacciones)} interacciones para el período {lote.periodo_referencia}.",
        activos_distribucion_generados=[
            ActivoGenerado(
                id_activo="act-01",
                formato="linkedin",
                copy="¡Orgullo en la comunidad! Uno de nuestros miembros consiguió su primer empleo Dev Jr. tras mostrar su portafolio de IA. #CommunityHighlights",
                fuentes=["m-01"],
                estado="generado"
            ),
            ActivoGenerado(
                id_activo="act-02",
                formato="faq",
                copy="FAQ Técnico: ¿Cómo manejar reintentos en LangGraph? Configura una condición de fallback y limita reintentos en el router.",
                fuentes=["m-02", "m-03"],
                estado="generado"
            ),
            ActivoGenerado(
                id_activo="act-03",
                formato="newsletter",
                copy="Resumen semanal: Gran mentoría sobre portafolios de IA y resolución de dudas sobre OCI Storage.",
                fuentes=["m-04", "m-05"],
                estado="generado"
            )
        ],
        alertas_internas=[
            AlertaInterna(
                id_alerta="alt-01",
                nivel="bloqueo",
                mensaje="Usuario reportó timeout 504 intermitente al intentar acceder al bucket de OCI.",
                fuente="m-06"
            )
        ],
        almacenamiento_oci=AlmacenamientoOCI(
            bucket="communitylab-alwaysfree-bucket",
            ruta=f"demo/{lote.periodo_referencia}/lotes/proc-mock-2026-001/paquete.json",
            estado="simulado_pendiente_worker"
        )
    )