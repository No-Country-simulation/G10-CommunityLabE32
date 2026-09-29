import json
import csv
from io import StringIO
from typing import List, Dict, Any
from datetime import datetime

from backend.app.schemas.procesamientos import Interaccion


def parse_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parsea el contenido del archivo dependiendo de su extensión."""
    if filename.endswith('.json'):
        return json.loads(content.decode('utf-8'))
    elif filename.endswith('.csv'):
        text = content.decode('utf-8')
        reader = csv.DictReader(StringIO(text))
        return list(reader)
    else:
        raise ValueError("Formato de archivo no soportado. Debe ser JSON o CSV.")


def normalize_date(date_str: str) -> str:
    """Normaliza y formatea la fecha."""
    if not date_str:
        return ""
    # En un escenario real aquí se manejarían diferentes formatos (ej. con dateutil)
    return date_str.strip()


def normalize_interaccion(raw: Dict[str, Any]) -> Interaccion:
    """Normaliza un diccionario a un objeto Interaccion."""
    # Los datos reales traen 'id_mensaje' en lugar de 'id'
    id_val = str(raw.get('id', raw.get('id_mensaje', ''))).strip()
    autor = str(raw.get('autor', '')).strip()
    canal = str(raw.get('canal', '')).strip()
    fecha = normalize_date(str(raw.get('fecha', '')))
    texto = str(raw.get('texto', '')).strip()

    # Validar campos obligatorios
    if not id_val or not autor or not texto:
        raise ValueError(f"Faltan campos obligatorios en el registro: {raw}")

    return Interaccion(
        id=id_val,
        autor=autor,
        canal=canal,
        fecha=fecha,
        texto=texto
    )


def deduplicate(interacciones: List[Interaccion]) -> List[Interaccion]:
    """Deduplica interacciones basándose en el ID."""
    vistos = set()
    unicas = []
    for interaccion in interacciones:
        if interaccion.id not in vistos:
            vistos.add(interaccion.id)
            unicas.append(interaccion)
    return unicas


def procesar_lote(content: bytes, filename: str) -> List[Interaccion]:
    """
    Flujo principal del módulo de ingestión: 
    Validar (formato, campos), Normalizar (tipos, espacios) y Deduplicar.
    """
    # 1. Parsear archivo
    raw_data = parse_file(content, filename)
    
    # 2. Normalizar y Validar
    interacciones = []
    for raw in raw_data:
        try:
            interacciones.append(normalize_interaccion(raw))
        except ValueError:
            # En un entorno productivo, esto se loguearía para auditoría
            continue
            
    # 3. Deduplicar
    return deduplicate(interacciones)
