import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Patrón Empresarial: Usar SQLite asíncrono para desarrollo local sin fricción.
# En producción se inyecta la URL de PostgreSQL por variables de entorno.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./communitylab.db")

# Creación del motor asíncrono
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()