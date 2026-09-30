import sys
import os
import json
import asyncio
import logging
from pathlib import Path

# Inyección del path raíz para que Python encuentre el módulo 'app' sin errores
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.core.database import AsyncSessionLocal, engine, Base

# Importamos los modelos para que SQLAlchemy registre TODAS las tablas 
from app.models.mensaje import Mensaje 
from app.models.activo import Activo  # 

# Configuración de Logging Empresarial
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Resolución dinámica de rutas de los archivos JSON de Tian
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILES_TO_LOAD = [
    DATA_DIR / "interacciones_simuladas_es.json",
    DATA_DIR / "proyectos_github_estructurados.json"
]

def chunked_iterable(iterable, size):
    """Generador para procesar grandes volúmenes de datos por bloques (Chunking) y salvar memoria."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

async def init_db():
    """Genera la estructura de la tabla dinámicamente si no existe."""
    logger.info("Inicializando esquemas de la base de datos...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tablas creadas/verificadas correctamente.")

async def upsert_mensajes(session, mensajes_data: list[dict]):
    """Operación Idempotente (Upsert): Inserta nuevos o actualiza existentes."""
    if not mensajes_data:
        return

    stmt = sqlite_insert(Mensaje).values(mensajes_data)
    
    # Lógica de Upsert en SQLite
    update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}
    stmt = stmt.on_conflict_do_update(
        index_elements=['id_mensaje'],
        set_=update_dict
    )
    
    await session.execute(stmt)

async def seed_database():
    """Orquestador del Data Pipeline."""
    await init_db()

    for file_path in FILES_TO_LOAD:
        if not file_path.exists():
            logger.error(f"Archivo crítico no encontrado: {file_path}")
            continue

        logger.info(f"Leyendo dataset: {file_path.name}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Fallo al decodificar {file_path.name}: {str(e)}")
            continue
        
        BATCH_SIZE = 500
        total_records = len(data)
        inserted_count = 0

        logger.info(f"Iniciando ingesta de {total_records} registros en lotes de {BATCH_SIZE}...")

        async with AsyncSessionLocal() as session:
            async with session.begin():
                for chunk in chunked_iterable(data, BATCH_SIZE):
                    await upsert_mensajes(session, chunk)
                    inserted_count += len(chunk)
                    logger.info(f"Progreso: {inserted_count}/{total_records} registros procesados.")
            
        logger.info(f"✅ Finalizado con éxito: {file_path.name}\n")

if __name__ == "__main__":
    logger.info("🚀 Iniciando el Data Ingestion Pipeline...")
    try:
        asyncio.run(seed_database())
        logger.info("🎉 Proceso de ingesta completado al 100%.")
    except Exception as e:
        logger.critical(f"❌ Error crítico en el pipeline: {str(e)}")