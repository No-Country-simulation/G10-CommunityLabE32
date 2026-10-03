import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.activo import Activo
from backend.app.models.mensaje import Mensaje

async def inyectar_activos():
    async with AsyncSessionLocal() as session:
        # Primero, buscamos 3 mensajes reales en tu base de datos para usarlos como fuente
        resultado = await session.execute(select(Mensaje.id_mensaje).limit(3))
        ids_reales = resultado.scalars().all()
        
        if not ids_reales or len(ids_reales) < 3:
            print("Error: Necesitas correr primero seed_db.py para tener mensajes reales en la tabla.")
            return

        # Limpiamos los activos viejos para no tener duplicados
        await session.execute(Activo.__table__.delete())

        activos_demo = [
            Activo(
                id_activo="act-01",
                formato="linkedin",
                titulo="Post LinkedIn: Primer empleo Dev Jr.",
                copy="¡Del proyecto al primer empleo! 🚀\n\nUn miembro de nuestra comunidad nos cuenta cómo su portfolio de IA le abrió las puertas para su primera oportunidad como Dev Jr. ¡El esfuerzo rinde frutos!",
                estado="generado",
                fuentes=[ids_reales[0]], # <--- Vinculamos al primer mensaje real
                comentario_curador=""
            ),
            Activo(
                id_activo="act-02",
                formato="faq",
                titulo="Tip Técnico: Reintentos en LangGraph",
                copy="💡 ¿Cómo encaminar un reintento en LangGraph?\n\nDefine una condición de error clara, limita los intentos máximos y dirige el flujo a un nodo de recuperación.",
                estado="generado",
                fuentes=[ids_reales[1], ids_reales[2]], # <--- Vinculamos a otros mensajes reales
                comentario_curador=""
            ),
            Activo(
                id_activo="act-03",
                formato="newsletter",
                titulo="Highlights Semanales de la Comunidad",
                copy="Esta semana, la comunidad estuvo increíble. Compartieron una nueva app construida con Next.js y se realizó una mentoría sobre portfolios.",
                estado="revisado",
                fuentes=[ids_reales[0]],
                comentario_curador="Revisado el tono para que suene más a boletín informativo."
            )
        ]
        
        session.add_all(activos_demo)
        await session.commit()
        print("✅ ¡Activos inyectados y vinculados a mensajes REALES de tu base de datos!")

if __name__ == "__main__":
    asyncio.run(inyectar_activos())