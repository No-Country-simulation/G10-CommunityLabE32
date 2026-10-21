from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime
from backend.app.core.database import Base

class Mensaje(Base):
    __tablename__ = "mensajes"

    # Tipiado estricto e indexación para rendimiento (Performance)
    id_mensaje: Mapped[str] = mapped_column(primary_key=True, index=True)
    autor: Mapped[str] = mapped_column(nullable=False, index=True)
    fecha: Mapped[str] = mapped_column(nullable=False)
    canal: Mapped[str] = mapped_column(nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(nullable=False, index=True)
    texto: Mapped[str] = mapped_column(nullable=False)
    # Estos campos pueden ser nulos si el compa tian no los envía
    # NULL = sin analizar. positivo | negativo | neutral | indeterminado (ver docs/flujo-hibrido-banners.md).
    sentimiento_ref: Mapped[Optional[str]] = mapped_column(nullable=True)
    sentimiento_origen: Mapped[Optional[str]] = mapped_column(nullable=True)
    sentimiento_version: Mapped[Optional[str]] = mapped_column(nullable=True)
    sentimiento_trabajo: Mapped[Optional[str]] = mapped_column(nullable=True)
    sentimiento_fecha: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tema_ref: Mapped[Optional[str]] = mapped_column(nullable=True)
    # Nombre visible (p. ej. de Discord). `autor` sigue siendo la identidad (en Discord, el ID).
    autor_nombre: Mapped[Optional[str]] = mapped_column(nullable=True)