from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from typing import Annotated, List, Literal, Optional
from datetime import datetime, timezone
from enum import Enum

def _utc(valor: datetime) -> datetime:
    # Las columnas de activos se guardan en UTC sin zona (datetime.utcnow): se declaran como UTC para que el
    # navegador no las tome como hora local (salían 6 h corridas frente al historial, que sí lleva zona).
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor


FechaUTC = Annotated[datetime, AfterValidator(_utc)]


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

class PostsRedes(BaseModel):
    # Mismos límites que los generadores: X hasta 280 caracteres.
    linkedin: str = Field(min_length=5, max_length=6000)
    x: str = Field(default="", max_length=280)

class EventoHistorial(BaseModel):
    evento: str            # generado | edicion | estado | posts_generados
    estado: str
    version: int
    fecha: FechaUTC
    actor: Optional[str] = None
    comentario: Optional[str] = None

class SolicitudPosts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    redes: List[Literal["linkedin", "x"]] = Field(default_factory=lambda: ["linkedin", "x"], min_length=1)

class ActivoResponse(BaseModel):
    id_activo: str
    formato: str
    titulo: str
    copy: str
    estado: str
    fuentes: List[str] = []
    version: int
    comentario_curador: Optional[str] = None
    # Controles automáticos de fidelidad; None en activos anteriores al control.
    advertencias_fidelidad: Optional[List[dict]] = None
    posts_redes: Optional[PostsRedes] = None
    fecha_creacion: FechaUTC
    fecha_actualizacion: FechaUTC

    model_config = ConfigDict(from_attributes=True)

class ActivoDetalleResponse(ActivoResponse):
    fuentes_detalle: List[FuenteMensajeDetalle] = []
    # Eventos registrados desde que existe la auditoría (sin reconstruir el pasado).
    historial: List[EventoHistorial] = []
    generaciones_restantes: Optional[int] = None

class ActivoUpdateDTO(BaseModel):
    copy: Optional[str] = Field(None, min_length=5, description="Nuevo texto editado")
    estado: Optional[EstadoActivoEnum] = None
    comentario_curador: Optional[str] = Field(None, max_length=500)
    # Versiones LinkedIn y X; si llega, `copy` pasa a ser la de LinkedIn.
    posts_redes: Optional[PostsRedes] = None

class PaginatedActivosResponse(BaseModel):
    items: List[ActivoResponse]
    total: int
    page: int
    limit: int
    total_pages: int