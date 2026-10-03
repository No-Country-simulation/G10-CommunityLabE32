from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import AsyncSessionLocal
import logging

logger = logging.getLogger(__name__)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Inyección de Dependencia para manejar el ciclo de vida de la sesión BD.
    Garantiza el cierre (teardown) aislando las transacciones por petición.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Error crítico en transacción de base de datos: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()