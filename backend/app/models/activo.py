from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, JSON
from datetime import datetime
from typing import Optional, List
from backend.app.core.database import Base

class Activo(Base):
    __tablename__ = "activos"

    # Identificador alfanumérico (ej: "act-01", "act-02") alineado con la propuesta
    id_activo: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    formato: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # linkedin, faq, newsletter
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    copy: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default="generado", index=True)  # generado, revisado, aprobado, rechazado
    
    # Lista de IDs de los mensajes fuente (ej: ["m-01", "m-02"])
    fuentes: Mapped[List[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)
    comentario_curador: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)