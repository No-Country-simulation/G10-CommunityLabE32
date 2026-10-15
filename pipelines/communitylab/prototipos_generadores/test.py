"""
Script de validación y pruebas de contrato para los agentes generadores MVP.
Carga los casos de prueba desde 'test_lotes.json', los procesa mediante
'dispatch_generator' y ejecuta aserciones estrictas de integridad contractual.

Ejecutar: python test.py
"""

import json
import os
import sys
import time
from typing import Dict, Any, List

from generadores.router_generador import dispatch_generator
from generadores.post_generador import generar_post
from generadores.faq_generador import generar_faq
from generadores.highlights_generador import generar_highlights

# Registro oficial de funciones generadoras habilitadas
GENERADORES_REGISTRADOS = {
    "post_linkedin_x": generar_post,
    "faq_tip_tecnico": generar_faq,
    "community_highlights": generar_highlights,
}

def validar_resultado_contrato(contrato_entrada: Dict[str, Any], respuesta: Dict[str, Any]) -> None:
    """
    Ejecuta el conjunto estricto de aserciones contractuales exigidas
    por el grafo orquestador sobre la respuesta del agente.
    """
    # 1. Validación de estructura y claves exactas
    assert isinstance(respuesta, dict), (
        f"Fallo de contrato: La respuesta debe ser un dict, recibido {type(respuesta).__name__}."
    )
    assert set(respuesta.keys()) == {"copy", "fuentes"}, (
        f"Fallo de contrato: Claves inválidas en la respuesta: {set(respuesta.keys())}. "
        "Se exige estrictamente {'copy', 'fuentes'}."
    )

    # 2. Validación del campo 'copy'
    copy = respuesta["copy"]
    assert isinstance(copy, str), (
        f"Fallo de contrato: El campo 'copy' debe ser un string, recibido {type(copy).__name__}."
    )
    assert len(copy.strip()) > 0, "Fallo de contrato: El campo 'copy' está vacío o solo contiene espacios."

    # 3. Validación del campo 'fuentes'
    fuentes_out = respuesta["fuentes"]
    fuentes_in = contrato_entrada["fuentes"]

    assert isinstance(fuentes_out, list), (
        f"Fallo de contrato: 'fuentes' debe ser una lista, recibido {type(fuentes_out).__name__}."
    )
    assert all(isinstance(f, str) and f.strip() for f in fuentes_out), (
        "Fallo de contrato: Cada elemento en 'fuentes' debe ser un string no vacío."
    )
    assert len(fuentes_out) == len(set(fuentes_out)), (
        f"Fallo de contrato: La lista de fuentes contiene identificadores duplicados: {fuentes_out}"
    )
    assert set(fuentes_out) == set(fuentes_in), (
        f"Fallo de contrato: Las fuentes retornadas no coinciden exactamente con las de entrada.\n"
        f"Esperadas: {sorted(fuentes_in)}\nRecibidas: {sorted(fuentes_out)}"
    )

def cargar_lote_pruebas(ruta_archivo: str = "test_lotes.json") -> List[Dict[str, Any]]:
    """
    Carga y valida sintácticamente el archivo de contratos de prueba.
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(
            f"No se encontró el archivo de casos de prueba '{ruta_archivo}'."
        )

    with open(ruta_archivo, "r", encoding="utf-8") as archivo:
        lote = json.load(archivo)

    if not isinstance(lote, list) or len(lote) == 0:
        raise ValueError(f"El archivo '{ruta_archivo}' debe contener una lista no vacía de contratos.")

    return lote

def ejecutar_suite_pruebas() -> bool:
    """
    Itera sobre todos los contratos del lote, invoca los generadores vía router
    y reporta el estado de cumplimiento contractual de cada uno.
    """
    print("=" * 80)
    print("EJECUTOR DE PRUEBAS DE CONTRATO - AGENTES GENERADORES (MVP)")
    print("=" * 80)

    try:
        lote = cargar_lote_pruebas()
    except Exception as error_carga:
        print(f"[ERROR CRÍTICO] No fue posible cargar el dataset de pruebas: {error_carga}")
        return False

    total_casos = len(lote)
    casos_exitosos = 0
    tiempo_inicio = time.time()

    print(f"Total de casos cargados para evaluación: {total_casos}\n")

    for indice, caso in enumerate(lote, start=1):
        formato = caso.get("formato", "desconocido")
        fuentes = caso.get("fuentes", [])
        periodo = caso.get("periodo_referencia", "N/A")
        
        print(f"[{indice}/{total_casos}] Evaluando formato: '{formato}' | Fuentes: {fuentes} | Periodo: {periodo}")

        try:
            inicio_caso = time.time()
            respuesta = dispatch_generator(caso, GENERADORES_REGISTRADOS)
            duracion = time.time() - inicio_caso

            # Validación de contrato
            validar_resultado_contrato(caso, respuesta)

            # Guardar la respuesta en un archivo de salida para inspección manual
            with open(f"salida_{indice}.json", "w", encoding="utf-8") as f:
                json.dump(respuesta, f, ensure_ascii=False, indent=2)   

            # Muestra del copy generado (primeras líneas)
            """primeras_lineas = respuesta["copy"].strip().split("\n")
            preview = primeras_lineas[0] if primeras_lineas else ""
            if len(preview) > 90:
                preview = preview[:87] + "..."""
            
        
            print(f"      Estado: [OK]")
            print(f"      Latencia: {duracion:.2f}s")
            #print(f"      Vista previa copy: \"{preview}\"")
            print("      COPY COMPLETO:")
            print(respuesta["copy"])
            print(f"      Fuentes verificadas: {respuesta['fuentes']}")
            print("-" * 80)
            casos_exitosos += 1

        except AssertionError as error_asercion:
            print(f"      Estado: [FALLO DE CONTRATO]")
            print(f"      Detalle: {error_asercion}")
            print("-" * 80)
        except Exception as error_inesperado:
            print(f"      Estado: [EXCEPCIÓN]")
            print(f"      Detalle: {error_inesperado}")
            print("-" * 80)

    tiempo_total = time.time() - tiempo_inicio
    print("\n" + "=" * 80)
    print("RESUMEN DE EJECUCIÓN")
    print(f"Casos evaluados: {total_casos}")
    print(f"Casos exitosos:  {casos_exitosos}")
    print(f"Casos fallidos:  {total_casos - casos_exitosos}")
    print(f"Tiempo total:    {tiempo_total:.2f}s")
    print("=" * 80)

    return casos_exitosos == total_casos

if __name__ == "__main__":
    exito = ejecutar_suite_pruebas()
    sys.exit(0 if exito else 1)