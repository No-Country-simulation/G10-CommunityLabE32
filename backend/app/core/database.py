import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Carga las variables del archivo .env a la memoria
load_dotenv()

# Lee la variable de forma segura (sin contraseñas quemadas en el código)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("⚠️ ERROR CRÍTICO: Falta la variable de entorno DATABASE_URL en el archivo .env")

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