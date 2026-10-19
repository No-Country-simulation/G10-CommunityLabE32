from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # usuario | operador | administrador (restricción en worker/schema.sql). Nunca lo elige el cliente.
    rol: Mapped[str] = mapped_column(String(20), default="usuario", server_default=text("'usuario'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
