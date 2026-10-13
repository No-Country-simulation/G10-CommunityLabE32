import asyncio
import json

# Placeholder: Asegúrate de importar tu servicio/grafo real de LangGraph o LLM
from backend.app.schemas.procesamientos import Interaccion
from pipelines.communitylab.grafo import ejecutar_lote
from pipelines.communitylab.simulados import crear_componentes

async def generar_demo():
    print("Iniciando validación de 3 transformaciones para DEMO...")

    # Mensajes de ejemplo (Logro, Duda y Período)
    mensajes_demo = [
        Interaccion(
            id="m-demo-1",
            autor="Maria",
            canal="general",
            fecha="2026-10-06",
            tipo="mensaje",
            texto="¡Chicos! Quería contarles que por fin conseguí mi primer trabajo como Dev Jr gracias a que armé mi portafolio de IA como sugirieron acá."
        ),
        Interaccion(
            id="m-demo-2",
            autor="Carlos",
            canal="ayuda",
            fecha="2026-10-06",
            tipo="duda",
            texto="Tengo un error de timeout 504 al conectar OCI con LangGraph. ¿Alguien sabe cómo hacer un retry o fallback?"
        ),
        Interaccion(
            id="m-demo-3",
            autor="Admin",
            canal="anuncios",
            fecha="2026-10-07",
            tipo="anuncio",
            texto="Esta semana se unieron 50 personas nuevas, tuvimos 2 eventos de live coding y ayudamos a 5 miembros a desplegar en OCI."
        )
    ]

    print("\n--- Simulando inyección en el Pipeline ---")
    
    # 1. Definir cómo la IA (simulada aquí) va a puntuar estos mensajes
    # Esto le dice al router a qué destino (linkedin, faq, newsletter) debe ir cada uno
    señales = {
        "m-demo-1": {"es_logro": True, "es_duda": False, "es_bloqueo": False, "tema": "logros", "relevancia": 0.9},
        "m-demo-2": {"es_logro": False, "es_duda": True, "es_bloqueo": False, "tema": "dudas", "relevancia": 0.8},
        "m-demo-3": {"es_logro": False, "es_duda": False, "es_bloqueo": False, "tema": "resumen", "relevancia": 0.95}
    }
    
    componentes = crear_componentes(señales)
    
    # Adaptar la entrada al contrato que espera ejecutar_lote
    entrada = {
        "origen_comunidad": "discord_demo",
        "periodo_referencia": "2026-10-01",
        "cierre_periodo": True,
        "interacciones": [
            {"id": m.id, "autor": m.autor, "canal": m.canal, "fecha": m.fecha, "texto": m.texto} 
            for m in mensajes_demo
        ]
    }
    
    # Ejecutamos el pipeline (grafo)
    resultado = ejecutar_lote(entrada, componentes)
    
    print("\nResultado Generado por el Grafo:")
    for activo in resultado.get("activos_distribucion_generados", []):
        print(f"\n✅ FORMATO: {activo['formato']}")
        print(f"   COPY: {activo['copy']}")
    
    print("\n[!] NOTA: El script está llamando a `simulados.py` el cual YA inyecta la cita correctamente ([Fuente: Autor - ID]) para cumplir con la demo.")

if __name__ == "__main__":
    asyncio.run(generar_demo())
