from typing import List

from pydantic import BaseModel, Field


class Interaccion(BaseModel):
    id: str
    autor: str
    canal: str
    fecha: str
    texto: str
    tipo: str = "mensaje"


class PuntajeRelevancia(BaseModel):
    hito_logrado: int = Field(default=0, ge=0, le=10, description="Puntuación por hitos o logros mencionados")
    emocion: int = Field(default=0, ge=0, le=10, description="Puntuación por la carga emocional del mensaje")
    utilidad: int = Field(default=0, ge=0, le=10, description="Puntuación por qué tan útil es para otros")
    recurrencia: int = Field(default=0, ge=0, le=10, description="Puntuación si aborda temas o dudas frecuentes")
    total: int = Field(default=0, description="Suma de las puntuaciones anteriores")
    es_destacado: bool = Field(default=False, description="True si supera el umbral para publicación")


class InteraccionEvaluada(BaseModel):
    interaccion: Interaccion
    relevancia: PuntajeRelevancia

class IngestaRequest(BaseModel):
    origen_comunidad: str = Field(
        ...,
        example="discord_comunidad_alura",
    )
    periodo_referencia: str = Field(
        ...,
        example="2026-W38",
    )
    interacciones: List[Interaccion]


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