from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
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
    sentimiento_ref: Mapped[Optional[str]] = mapped_column(nullable=True)
    tema_ref: Mapped[Optional[str]] = mapped_column(nullable=True)