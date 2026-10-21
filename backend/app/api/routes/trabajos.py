"""Contrato asíncrono local de referencia para revisar con Fredy."""
import asyncio
import csv
import io
import json
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Header

from backend.app.core.acceso import Principal, requiere_puente_u_operador
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from worker.store_postgres import ColaPostgres, ConflictoIdempotencia, ConflictoMensaje
from pipelines.communitylab.diagnostico import normalizar_diagnostico
from pipelines.communitylab.fechas import fecha_utc

# Entrega y consulta de lotes: el puente (Bearer PUENTE_TOKEN) o una persona operadora.
router = APIRouter(prefix="/api/v1/trabajos", tags=["Trabajos asíncronos"],
                   dependencies=[Depends(requiere_puente_u_operador)])


class InteraccionTrabajo(BaseModel):
    # Mismos máximos que el contrato de lectura (autor 150, canal 50, tipo 50).
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    autor: str = Field(min_length=1, max_length=150)
    canal: str = Field(min_length=1, max_length=50)
    fecha: str = Field(min_length=1)
    texto: str = Field(min_length=1)
    tipo: str | None = Field(default=None, min_length=1, max_length=50)
    # Nombre visible (p. ej. de Discord); el `autor` sigue siendo la identidad del mensaje.
    autor_nombre: str | None = Field(default=None, min_length=1, max_length=150)
    # Contexto ya procesado en un lote parcial del mismo período (no genera alertas ni posts).
    previo: bool | None = None

    @field_validator("fecha")
    @classmethod
    def validar_fecha(cls, valor):
        fecha_utc(valor)
        return valor


class LoteTrabajo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen_comunidad: str = Field(min_length=1, max_length=200)
    periodo_referencia: str = Field(min_length=1, max_length=100)
    cierre_periodo: bool = False
    interacciones: list[InteraccionTrabajo] = Field(min_length=1, max_length=500)


MAX_BYTES_ARCHIVO = 5 * 1024 * 1024
MAX_REGISTROS = 500
MAX_ERRORES_INFORMADOS = 10
AYUDA_FORMATO = ("Use JSON (lista o {\"interacciones\": [...]}), JSONL o CSV, máximo 5 MiB y "
                 "500 registros. Campos por registro: id (o id_mensaje), autor, canal, "
                 "fecha ISO 8601 con zona (p. ej. 2026-10-19T14:10:00Z) y texto; tipo es opcional.")
METADATOS = ("origen_comunidad", "periodo_referencia", "cierre_periodo")


def error_api(estado, codigo, mensaje, errores=None):
    """Error seguro para la interfaz: código estable, mensaje y ubicación; nunca valores del archivo."""
    detalle = {"codigo": codigo, "mensaje": mensaje, "ayuda": AYUDA_FORMATO}
    if errores:
        detalle["errores"] = errores[:MAX_ERRORES_INFORMADOS]
        detalle["errores_totales"] = len(errores)
    return HTTPException(estado, detalle)


def _motivo(error):
    tipo, ctx = error.get("type", ""), error.get("ctx") or {}
    # Un campo ausente en el archivo llega como None: se informa como obligatorio, no como tipo.
    if tipo == "missing" or (tipo == "string_type" and error.get("input") is None):
        return "campo obligatorio ausente"
    if tipo == "string_too_short":
        return "no puede estar vacío"
    if tipo == "string_too_long":
        return f"supera {ctx.get('max_length')} caracteres"
    if tipo == "string_type":
        return "debe ser texto"
    if tipo == "value_error":
        return "fecha inválida: use ISO 8601 con hora y zona (p. ej. 2026-10-19T14:10:00Z)"
    if tipo == "extra_forbidden":
        return "campo no permitido"
    return "valor inválido"


def cola():
    return ColaPostgres(os.environ["DATABASE_URL"])


@router.post("", status_code=202)
async def crear_trabajo(lote: LoteTrabajo, principal: Principal = Depends(requiere_puente_u_operador),
                        idempotency_key: str | None = Header(default=None, max_length=128)):
    # El puente de Discord entrega con su Bearer; una persona operadora carga a mano.
    return await encolar_lote(lote, idempotency_key, "discord" if principal.tipo == "puente" else "manual")


async def encolar_lote(lote: LoteTrabajo, idempotency_key: str | None, fuente: str):
    try:
        almacen = cola()
        identificador, nuevo = await asyncio.to_thread(
            almacen.encolar_detalle, lote.model_dump(exclude_none=True), idempotency_key, fuente)
        trabajo = await asyncio.to_thread(almacen.obtener, identificador)
    except ConflictoIdempotencia:
        raise error_api(409, "conflicto_idempotencia",
                        "La clave de idempotencia ya identifica otro lote con contenido distinto.") from None
    except ConflictoMensaje as exc:
        raise error_api(409, "conflicto_mensaje",
                        "Un ID de mensaje ya existe con otro contenido (autor, fecha, canal, tipo o texto). "
                        "Use un ID nuevo o el mismo contenido.",
                        [{"id": exc.id_mensaje, "motivo": "contenido distinto al ya guardado"}]) from None
    except ValueError as exc:
        # Mensajes controlados de la cola y del grafo (sin contenido del lote).
        raise error_api(422, "lote_invalido", str(exc)) from None
    except Exception:
        raise HTTPException(503, {"codigo": "servicio_no_disponible",
                                  "mensaje": "No se pudo registrar el trabajo; intente nuevamente."}) from None
    return {"procesamiento_id": identificador, "estado": trabajo["estado"], "reutilizado": not nuevo,
            "consulta": f"/api/v1/trabajos/{identificador}"}


@router.get("/{identificador}")
async def consultar_trabajo(identificador: str):
    try:
        trabajo = await asyncio.to_thread(cola().obtener, identificador)
    except Exception:
        raise HTTPException(503, "Consulta temporalmente no disponible.") from None
    if trabajo is None:
        raise HTTPException(404, "Trabajo no encontrado")
    resultado = trabajo.get("resultado")
    if isinstance(resultado, dict) and "diagnostico" in resultado:
        # Defensa en la salida: aunque una fila tenga otro contenido, solo se exponen valores de catálogo.
        trabajo = {**trabajo, "resultado": {**resultado,
                                            "diagnostico": normalizar_diagnostico(resultado["diagnostico"])}}
    return trabajo


def _leer_registros(contenido, nombre):
    texto = contenido.decode("utf-8-sig")
    if nombre.endswith(".json"):
        datos = json.loads(texto)
    elif nombre.endswith(".jsonl"):
        datos = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
    elif nombre.endswith(".csv"):
        datos = list(csv.DictReader(io.StringIO(texto)))
    else:
        raise error_api(400, "formato_no_soportado", "Formato no soportado: use JSON, JSONL o CSV.")
    metadatos = {}
    if isinstance(datos, dict):
        metadatos = {k: datos[k] for k in METADATOS if k in datos}
        datos = datos.get("interacciones")
    if not isinstance(datos, list) or not datos:
        raise error_api(422, "sin_interacciones", "El archivo no contiene una lista de interacciones.")
    return datos, metadatos


async def encolar_archivo(file: UploadFile, origen: str, periodo: str, cierre: bool):
    contenido = await file.read(MAX_BYTES_ARCHIVO + 1)
    if len(contenido) > MAX_BYTES_ARCHIVO:
        raise error_api(413, "archivo_demasiado_grande", "El archivo supera el máximo de 5 MiB.")
    try:
        datos, metadatos = _leer_registros(contenido, (file.filename or "").lower())
    except UnicodeError:
        raise error_api(422, "codificacion_invalida", "El archivo debe estar codificado en UTF-8.") from None
    except (json.JSONDecodeError, csv.Error):
        raise error_api(422, "archivo_malformado", "El archivo no es JSON, JSONL o CSV válido.") from None

    errores, normalizados, huellas, por_id, duplicados = [], [], set(), {}, 0
    for posicion, m in enumerate(datos, start=1):
        if not isinstance(m, dict):
            errores.append({"registro": posicion, "motivo": "el registro debe ser un objeto"})
            continue
        registro = {k: m.get(k) for k in ("autor", "canal", "fecha", "texto")}
        identificador = m.get("id", m.get("id_mensaje"))
        registro["id"] = str(identificador) if isinstance(identificador, int) else identificador
        if m.get("tipo") not in (None, ""):
            registro["tipo"] = m["tipo"]
        huella = json.dumps(registro, sort_keys=True, ensure_ascii=False)
        if huella in huellas:
            duplicados += 1  # Registro idéntico repetido en el archivo: se conserva una vez.
            continue
        if isinstance(registro["id"], str) and registro["id"] in por_id:
            errores.append({"registro": posicion, "id": registro["id"], "campo": "id",
                            "motivo": f"ID repetido con contenido distinto (registro {por_id[registro['id']]})"})
            continue
        huellas.add(huella)
        if isinstance(registro["id"], str):
            por_id[registro["id"]] = posicion
        normalizados.append((posicion, registro))

    if len(normalizados) > MAX_REGISTROS:
        raise error_api(422, "demasiados_registros",
                        f"El archivo tiene {len(normalizados)} registros distintos; el máximo es {MAX_REGISTROS}. "
                        "Divídalo en varios lotes.")
    try:
        lote = LoteTrabajo(origen_comunidad=origen, periodo_referencia=periodo,
                           cierre_periodo=cierre, interacciones=[r for _, r in normalizados])
    except ValidationError as exc:
        for e in exc.errors():
            loc = e.get("loc", ())
            if len(loc) >= 2 and loc[0] == "interacciones" and isinstance(loc[1], int):
                posicion, registro = normalizados[loc[1]]
                identificador = registro.get("id") if isinstance(registro.get("id"), str) else None
                errores.append({"registro": posicion, "id": identificador,
                                "campo": loc[2] if len(loc) > 2 else None, "motivo": _motivo(e)})
            else:
                errores.append({"campo": str(loc[0]) if loc else None, "motivo": _motivo(e)})
    if errores:
        errores.sort(key=lambda e: e.get("registro") or 0)
        raise error_api(422, "archivo_invalido",
                        f"{len(errores)} problema(s) en el archivo; no se encoló ningún registro.", errores)

    respuesta = await encolar_lote(lote, None, "manual")
    # Precedencia documentada: los campos del formulario prevalecen sobre metadatos del archivo.
    formulario = {"origen_comunidad": origen, "periodo_referencia": periodo, "cierre_periodo": cierre}
    ignorados = [k for k, v in metadatos.items() if v != formulario[k]]
    return {**respuesta, "interacciones": len(normalizados), "registros_duplicados_omitidos": duplicados,
            "metadatos_archivo_ignorados": ignorados}
