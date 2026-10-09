"""Inicialización explícita para una instalación local limpia; no carga datos demo."""
import asyncio
import os
from backend.app.core.database import Base, engine
from backend.app.models.activo import Activo
from backend.app.models.mensaje import Mensaje
from worker.store_postgres import ColaPostgres


async def main():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    await engine.dispose()
    await asyncio.to_thread(ColaPostgres(os.environ["DATABASE_URL"]).inicializar)


if __name__ == "__main__":
    asyncio.run(main())
