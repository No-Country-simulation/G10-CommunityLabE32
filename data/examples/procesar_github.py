import csv
import json
import re
from pathlib import Path

INPUT_FILE = Path(r"C:\PROYECTOS\Hackathon\Data_hf\top_github_repos_2026.csv")
OUTPUT_FILE = Path(r"C:\PROYECTOS\Hackathon\proyectos_github_estructurados.json")

# Palabras clave orientadas a repositorios (inglés/español)
POS_KEYWORDS = ["awesome", "free", "best", "great", "useful", "easy", "powerful", "fast", "excelente", "gratis"]
NEG_KEYWORDS = ["deprecated", "unmaintained", "obsolete", "vulnerability", "bug", "error", "fail", "obsoleto"]

def analizar_sentimiento(texto: str) -> str:
    """Clasifica el sentimiento basado en keywords comunes en descripciones de repositorios."""
    texto_lower = str(texto).lower()
    score = 0
    
    for kw in POS_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', texto_lower):
            score += 1
            
    for kw in NEG_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', texto_lower):
            score -= 1
            
    if score > 0: return "positivo"
    elif score < 0: return "negativo"
    else: return "neutro"

def procesar_github():
    resultados = []
    total_lineas = 0
    
    if not INPUT_FILE.exists():
        print(f"Error: El archivo no existe en la ruta:\n{INPUT_FILE}")
        return

    print("Procesando dataset de GitHub Repositories...")

    # Abrir el CSV
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_lineas += 1
            
            # 1. Extraer autor y nombre del repo de la columna 'name' (ej: 'microsoft/vscode')
            full_name = row.get("name", "")
            if "/" in full_name:
                autor, repo_name = full_name.split("/", 1)
            else:
                autor, repo_name = "Comunidad", full_name
            
           # 1. Extraer autor y nombre del repo
            full_name = row.get("name", "")
            if "/" in full_name:
                autor, repo_name = full_name.split("/", 1)
            else:
                autor, repo_name = "Comunidad", full_name
            
            # 2. Construir el texto enriquecido (CORRECCIÓN AQUÍ)
            descripcion = row.get("description", "").strip()
            
            # Si no hay descripción o dice "nan" (común al exportar de pandas)
            if not descripcion or descripcion.lower() == 'nan':
                descripcion = "Repositorio sin descripción detallada."

            lenguaje = row.get("language", "").strip()
            topics = row.get("topics", "").replace("|", ", ")
            
            # Siempre incluimos el nombre del proyecto para dar contexto a la IA
            texto_compuesto = f"Proyecto: {full_name}\n{descripcion}"
            
            if lenguaje and lenguaje.lower() != 'nan':
                texto_compuesto += f"\nLenguaje principal: {lenguaje}."
            if topics and topics.lower() != 'nan':
                texto_compuesto += f"\nEtiquetas: {topics}."
                
            # Ya no descartamos por longitud porque aseguramos un texto mínimo válido
                
            # 3. Asignar Fechas y Clasificaciones
            fecha_raw = row.get("created_at", "2026-01-01")
            fecha_iso = f"{fecha_raw}T12:00:00Z" # Formateado para ISO8601
            
            sentimiento = analizar_sentimiento(texto_compuesto)
            tema = lenguaje if lenguaje and lenguaje.lower() != 'nan' else "Herramientas Generales"
            
            # 4. Mapeo a la estructura unificada
            item_normalizado = {
                "id_mensaje": f"github-{full_name.replace('/', '-')}",
                "autor": autor,
                "fecha": fecha_iso,
                "canal": "#recursos-y-repositorios",
                "tipo": "recomendacion_repositorio",
                "texto": texto_compuesto,
                "sentimiento_ref": sentimiento,
                "tema_ref": tema
            }
            
            resultados.append(item_normalizado)

    # Exportar el JSON estructurado
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print("\n--- ¡Procesamiento completado! ---")
    print(f"Repositorios totales revisados: {total_lineas}")
    print(f"Items normalizados generados: {len(resultados)}")
    print(f"Archivo generado en: {OUTPUT_FILE}")

if __name__ == "__main__":
    procesar_github()