from typing import List

from pydantic import BaseModel, Field


class Interaccion(BaseModel):
    id: str
    autor: str
    canal: str
    fecha: str
    texto: str


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