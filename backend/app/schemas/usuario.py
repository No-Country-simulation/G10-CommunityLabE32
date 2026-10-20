from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Rol = Literal["usuario", "operador", "administrador"]


class UsuarioBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=255)


class UsuarioCreate(UsuarioBase):
    """Registro público (deshabilitado por defecto). El rol NUNCA viene del cliente: extra=forbid."""
    model_config = ConfigDict(extra="forbid")
    # 10 caracteres como mínimo; bcrypt solo verifica 72 bytes (también se valida en bytes en el servicio).
    password: str = Field(min_length=10, max_length=72)


class UsuarioCreadoPorAdmin(UsuarioCreate):
    rol: Rol = "usuario"


class UsuarioAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rol: Optional[Rol] = None
    is_active: Optional[bool] = None
    # Contraseña temporal fijada por un administrador; la persona la cambia luego en Configuración.
    new_password: Optional[str] = Field(default=None, min_length=10, max_length=72)


class UsuarioUpdate(BaseModel):
    """Cambiar correo o contraseña exige la contraseña actual. El rol no se puede cambiar aquí."""
    model_config = ConfigDict(extra="forbid")
    full_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = None
    current_password: Optional[str] = Field(default=None, max_length=72)
    new_password: Optional[str] = Field(default=None, min_length=10, max_length=72)


class UsuarioResponse(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rol: Rol
    is_active: bool
    created_at: datetime


class SesionResponse(BaseModel):
    """El JWT viaja solo en la cookie HttpOnly. csrf_token se guarda en memoria del navegador."""
    usuario: UsuarioResponse
    csrf_token: str
    expira: datetime
