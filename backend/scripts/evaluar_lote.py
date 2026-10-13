import json
import asyncio
import argparse
from typing import List, Dict

# Suponiendo que hay un servicio de relevancia existente
from backend.app.services.relevancia import evaluar_interaccion
from backend.app.schemas.procesamientos import Interaccion

async def evaluar_lote(ruta_archivo: str):
    """
    Evalúa un lote de mensajes etiquetados manualmente contra el LLM.
    El archivo debe ser un JSON donde cada item tiene:
    - id_mensaje, texto, autor
    - expected_tema, expected_sentimiento, expected_route
    """
    print(f"Cargando dataset desde {ruta_archivo}...")
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        print(f"No se encontró el archivo {ruta_archivo}. Crea uno de prueba para validar.")
        return

    total = len(datos)
    aciertos_tema = 0
    aciertos_sentimiento = 0
    
    print(f"Iniciando evaluación de {total} mensajes...\n")
    
    for i, item in enumerate(datos):
        interaccion = Interaccion(
            id=item["id_mensaje"],
            autor=item["autor"],
            canal="discord",
            fecha="2026-10-01",
            tipo="mensaje_prueba",
            texto=item["texto"]
        )
        
        # Llamada al LLM / Sistema de relevancia
        resultado = evaluar_interaccion(interaccion)
        
        # Las métricas del modelo PuntajeRelevancia usan enteros
        if resultado.relevancia.hito_logrado > 0:
            tema_ia = "logros"
        elif resultado.relevancia.recurrencia >= 5:
            tema_ia = "bloqueos"
        elif resultado.relevancia.recurrencia > 0:
            tema_ia = "dudas"
        elif resultado.relevancia.utilidad > 0:
            tema_ia = "aportes"
        else:
            tema_ia = "otro"

        if resultado.relevancia.emocion > 0:
            sent_ia = "positivo"
        elif resultado.relevancia.emocion < 0:
            sent_ia = "negativo"
        else:
            sent_ia = "neutral"
        
        # Comparación
        match_tema = item["expected_tema"].lower() in tema_ia.lower()
        match_sent = item["expected_sentimiento"].lower() in sent_ia.lower()
        
        if match_tema:
            aciertos_tema += 1
        if match_sent:
            aciertos_sentimiento += 1
            
        print(f"[{i+1}/{total}] Mensaje: {item['texto'][:30]}...")
        if not match_tema:
            print(f"  [ERROR TEMA] Esperado: {item['expected_tema']} | IA dijo: {tema_ia}")
        if not match_sent:
            print(f"  [ERROR SENTIMIENTO] Esperado: {item['expected_sentimiento']} | IA dijo: {sent_ia}")
            
    print("\n=== RESULTADOS FINALES ===")
    print(f"Precisión Tema: {aciertos_tema}/{total} ({(aciertos_tema/total)*100:.1f}%)")
    print(f"Precisión Sentimiento: {aciertos_sentimiento}/{total} ({(aciertos_sentimiento/total)*100:.1f}%)")
    print("==========================")
    
    if (aciertos_tema/total) < 0.8:
        print("💡 SUGERENCIA: La precisión del tema es baja (<80%). Debes ir a backend/app/services/relevancia.py y ajustar los prompts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default="backend/data/lote_etiquetado.json")
    args = parser.parse_args()
    
    asyncio.run(evaluar_lote(args.file))
