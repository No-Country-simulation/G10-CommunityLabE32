from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class EstadoActivoEnum(str, Enum):
    GENERADO = "generado"
    REVISADO = "revisado"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"

class FormatoActivoEnum(str, Enum):
    LINKEDIN = "linkedin"
    FAQ = "faq"
    NEWSLETTER = "newsletter"

class FuenteMensajeDetalle(BaseModel):
    id_mensaje: str
    autor: str
    canal: str
    fecha: str
    texto: str

    model_config = ConfigDict(from_attributes=True)

class ActivoResponse(BaseModel):
    id_activo: str
    formato: str
    titulo: str
    copy: str
    estado: str
    fuentes: List[str] = []
    version: int
    comentario_curador: Optional[str] = None
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)

class ActivoDetalleResponse(ActivoResponse):
    fuentes_detalle: List[FuenteMensajeDetalle] = []

class ActivoUpdateDTO(BaseModel):
    copy: Optional[str] = Field(None, min_length=5, description="Nuevo texto editado")
    estado: Optional[EstadoActivoEnum] = None
    comentario_curador: Optional[str] = Field(None, max_length=500)

class PaginatedActivosResponse(BaseModel):
    items: List[ActivoResponse]
    total: int
    page: int
    limit: int
    total_pages: int