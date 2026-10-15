from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from typing import List
class MensajeBase(BaseModel):
    """Esquema base con validaciones estrictas de longitud y tipo de dato."""
    autor: str = Field(..., min_length=1, max_length=150, description="Autor del mensaje")
    fecha: str = Field(..., description="Fecha en formato ISO 8601")
    canal: str = Field(..., min_length=1, max_length=50)
    tipo: str = Field(..., min_length=1, max_length=50)
    texto: str = Field(..., min_length=1, description="Contenido textual del mensaje")
    sentimiento_ref: Optional[str] = Field(default=None, max_length=20)
    tema_ref: Optional[str] = Field(default=None, max_length=100)

class MensajeResponse(MensajeBase):
    """
    DTO (Data Transfer Object) de salida. 
    Solo esto es lo que el Frontend tiene permitido ver.
    """
    id_mensaje: str

    # Configuración de Pydantic V2 para leer objetos de SQLAlchemy
    model_config = ConfigDict(from_attributes=True)
    
   

class PaginatedMensajesResponse(BaseModel):
    items: List[MensajeResponse]
    total: int