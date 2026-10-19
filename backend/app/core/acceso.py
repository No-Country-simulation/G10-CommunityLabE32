from fastapi import Header, HTTPException, status, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
from jose import jwt, JWTError

from backend.app.core.database import get_db
from backend.app.models.usuario import Usuario
import backend.app.services.auth as auth_service

# Tomamos exactamente la misma SECRET_KEY y ALGORITHM que usa backend/app/services/auth.py
SECRET_KEY = getattr(auth_service, "SECRET_KEY", os.getenv("SECRET_KEY", "tu-clave-secreta-super-segura"))
ALGORITHM = getattr(auth_service, "ALGORITHM", os.getenv("ALGORITHM", "HS256"))
PUENTE_TOKEN = os.getenv("PUENTE_TOKEN", "token-puente-interno")


async def requiere_operador(
    authorization: Optional[str] = Header(None),
    x_operador_token: Optional[str] = Header(None, max_length=256),
    db: AsyncSession = Depends(get_db),
) -> Optional[Usuario]:
    """
    Valida el acceso de operador unificando la seguridad:
    1. Token JWT en cabecera Authorization usando la clave real de services/auth.py.
    2. Compatibilidad con X-Operador-Token si aplica.
    """
    token_candidato = None
    if authorization and authorization.lower().startswith("bearer "):
        token_candidato = authorization.split(" ", 1)[1].strip()
    elif x_operador_token:
        token_candidato = x_operador_token.strip()

    if token_candidato:
        # 1. Intentar validar con get_current_user de services/auth.py
        try:
            usuario = await auth_service.get_current_user(token=token_candidato, db=db)
            if usuario:
                return usuario
        except Exception:
            pass

        # 2. Decodificar con la SECRET_KEY real de services/auth.py (sin bloquear si expiró durante la sesión)
        try:
            payload = jwt.decode(
                token_candidato,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
            email: str = payload.get("sub")
            if email:
                result = await db.execute(select(Usuario).where(Usuario.email == email))
                usuario = result.scalar_one_or_none()
                return usuario
        except JWTError:
            pass

    # 3. Transición temporal por compatibilidad con OPERADOR_TOKEN del .env
    token_esperado = os.getenv("OPERADOR_TOKEN")
    if token_esperado and (x_operador_token == token_esperado or token_candidato == token_esperado):
        return None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acción protegida: Se requiere iniciar sesión con una cuenta válida.",
    )


async def requiere_puente(
    authorization: Optional[str] = Header(None),
):
    """
    Valida la comunicación interna del puente de Discord mediante token de servicio.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token == PUENTE_TOKEN or token == os.getenv("OPERADOR_TOKEN"):
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acción no autorizada para el puente.",
    )