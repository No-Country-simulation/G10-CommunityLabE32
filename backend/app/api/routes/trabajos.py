"""Contrato asíncrono local de referencia para revisar con Fredy."""
import asyncio
import csv
import io
import json
import os
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from worker.store_postgres import ColaPostgres

router = APIRouter(prefix="/api/v1/trabajos", tags=["Trabajos asíncronos"])


class InteraccionTrabajo(BaseModel):
    # Mismos máximos que el contrato de lectura (autor 150, canal 50, tipo 50).
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    autor: str = Field(min_length=1, max_length=150)
    canal: str = Field(min_length=1, max_length=50)
    fecha: str = Field(min_length=1)
    texto: str = Field(min_length=1)
    tipo: str | None = Field(default=None, min_length=1, max_length=50)


class LoteTrabajo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen_comunidad: str = Field(min_length=1, max_length=200)
    periodo_referencia: str = Field(min_length=1, max_length=100)
    cierre_periodo: bool = False
    interacciones: list[InteraccionTrabajo] = Field(min_length=1, max_length=500)


def cola():
    return ColaPostgres(os.environ["DATABASE_URL"])


@router.post("", status_code=202)
async def crear_trabajo(lote: LoteTrabajo):
    try:
        identificador = await asyncio.to_thread(cola().encolar, lote.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(503, "No se pudo registrar el trabajo; intente nuevamente.") from None
    return {"procesamiento_id": identificador, "estado": "recibido",
            "consulta": f"/api/v1/trabajos/{identificador}"}


@router.get("/{identificador}")
async def consultar_trabajo(identificador: str):
    try:
        trabajo = await asyncio.to_thread(cola().obtener, identificador)
    except Exception:
        raise HTTPException(503, "Consulta temporalmente no disponible.") from None
    if trabajo is None:
        raise HTTPException(404, "Trabajo no encontrado")
    return trabajo


async def encolar_archivo(file: UploadFile, origen: str, periodo: str, cierre: bool):
    contenido = await file.read(5 * 1024 * 1024 + 1)
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(413, "Máximo 5 MiB por archivo")
    try:
        texto = contenido.decode("utf-8-sig")
        nombre = (file.filename or "").lower()
        if nombre.endswith(".json"):
            datos = json.loads(texto)
        elif nombre.endswith(".jsonl"):
            datos = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
        elif nombre.endswith(".csv"):
            datos = list(csv.DictReader(io.StringIO(texto)))
        else:
            raise HTTPException(400, "Use JSON, JSONL o CSV")
        if isinstance(datos, dict):
            datos = datos.get("interacciones")
        if not isinstance(datos, list) or not all(isinstance(m, dict) for m in datos):
            raise ValueError()
        normalizados, vistos = [], set()
        for m in datos:
            registro = {k: m.get(k) for k in ("autor", "canal", "fecha", "texto")}
            registro["id"] = m.get("id", m.get("id_mensaje"))
            if "tipo" in m:
                registro["tipo"] = m["tipo"]
            huella = json.dumps(registro, sort_keys=True, ensure_ascii=False)
            if huella not in vistos:
                normalizados.append(registro)
                vistos.add(huella)
        lote = LoteTrabajo(origen_comunidad=origen, periodo_referencia=periodo,
                          cierre_periodo=cierre, interacciones=normalizados)
    except (ValueError, UnicodeError, TypeError, csv.Error):
        raise HTTPException(422, "Archivo inválido: campos completos y máximo 500 registros.") from None
    return await crear_trabajo(lote)
