"""Procesamiento con el contrato del enunciado (proyecto.pdf, «Funcionalidades obligatorias (MVP)»).

`POST /api/v1/procesar` recibe el JSON del enunciado tal cual: `id`, `fecha` y `cierre_periodo` son
opcionales (en `/api/v1/trabajos` son obligatorios). Completa lo que falte, encola el lote en la misma
cola que el resto de la app, espera el resultado y responde con la forma del enunciado: resumen de la
comunidad, activos generados y almacenamiento en OCI.

El proxy corta a los 60 s, así que la espera es de 50 s como máximo: si el análisis tarda más se
responde 202 con `status: en_proceso` y la consulta `GET /api/v1/procesar/{procesamiento_id}`.
"""
import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.core.acceso import requiere_puente_u_operador
from backend.app.api.routes.trabajos import LoteTrabajo, cola, encolar_lote, error_api, _motivo
from pipelines.communitylab.diagnostico import normalizar_diagnostico
from pipelines.communitylab.paquete import fecha_por_defecto, id_por_defecto, paquete_distribucion, periodo_actual

router = APIRouter(prefix="/api/v1/procesar", tags=["Procesamiento (contrato del enunciado)"],
                   dependencies=[Depends(requiere_puente_u_operador)])
ESPERA_MAXIMA = 50          # segundos; por debajo del proxy_read_timeout de 60 s
ESPERA_OCI = 10             # segundos extra para que el worker confirme la copia en OCI
INTERVALO = 1.0


class InteraccionEnunciado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    autor: str = Field(min_length=1, max_length=150)
    canal: str = Field(min_length=1, max_length=50)
    texto: str = Field(min_length=1)
    tipo: str | None = Field(default=None, min_length=1, max_length=50)
    id: str | None = Field(default=None, min_length=1)
    fecha: str | None = Field(default=None, min_length=1)
    autor_nombre: str | None = Field(default=None, min_length=1, max_length=150)


class LoteEnunciado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen_comunidad: str = Field(default="api", min_length=1, max_length=200)
    periodo_referencia: str | None = Field(default=None, min_length=1, max_length=100)
    # Por defecto se cierra el período: así el lote también genera el resumen semanal (newsletter).
    cierre_periodo: bool = True
    interacciones: list[InteraccionEnunciado] = Field(min_length=1, max_length=500)


def completar(lote: LoteEnunciado) -> LoteTrabajo:
    """Lote del enunciado → lote de la cola, con ID y fecha estables donde falten."""
    periodo = lote.periodo_referencia or periodo_actual()
    fecha = fecha_por_defecto(periodo)
    interacciones = []
    for i, m in enumerate(lote.interacciones):
        datos = m.model_dump(exclude_none=True)
        datos.setdefault("id", id_por_defecto(lote.origen_comunidad, periodo, i, m.autor, m.canal, m.texto))
        datos.setdefault("fecha", fecha)
        interacciones.append(datos)
    try:
        return LoteTrabajo(origen_comunidad=lote.origen_comunidad, periodo_referencia=periodo,
                           cierre_periodo=lote.cierre_periodo, interacciones=interacciones)
    except ValidationError as exc:
        errores = [{"registro": e["loc"][1] + 1 if len(e["loc"]) > 1 and isinstance(e["loc"][1], int) else None,
                    "campo": str(e["loc"][-1]), "motivo": _motivo(e)} for e in exc.errors()]
        raise error_api(422, "lote_invalido", "Hay interacciones con datos inválidos.", errores) from None


def _total(identificador):
    with cola().conectar() as c:
        fila = c.execute("SELECT jsonb_array_length(entrada->'interacciones') AS n FROM trabajos_worker WHERE id=%s",
                         (identificador,)).fetchone()
    return fila["n"] if fila else None


def respuesta(trabajo, total):
    identificador = trabajo["id"]
    if trabajo["estado"] == "terminado":
        return JSONResponse(paquete_distribucion(trabajo["resultado"] or {}, procesamiento_id=identificador,
                                                 total_interacciones=total))
    if trabajo["estado"] == "error":
        resultado = trabajo.get("resultado") or {}
        return JSONResponse({"status": "error", "procesamiento_id": identificador,
                             "error_codigo": trabajo.get("error_codigo"),
                             "diagnostico": normalizar_diagnostico(resultado.get("diagnostico"))
                             if isinstance(resultado, dict) and resultado.get("diagnostico") else None},
                            status_code=502)
    return JSONResponse({"status": "en_proceso", "procesamiento_id": identificador,
                         "consulta": f"/api/v1/procesar/{identificador}"}, status_code=202)


async def esperar(identificador, segundos):
    """Espera a que el trabajo termine (y, si corresponde, a que se confirme la copia en OCI)."""
    almacen = cola()
    limite = asyncio.get_running_loop().time() + segundos
    extra_oci = None
    while True:
        trabajo = await asyncio.to_thread(almacen.obtener, identificador)
        if trabajo is None:
            raise HTTPException(503, "El trabajo encolado no se encontró; intente consultar más tarde.")
        estado = trabajo["estado"]
        if estado == "error":
            return trabajo
        if estado == "terminado":
            pendiente = ((trabajo.get("resultado") or {}).get("almacenamiento") or {}).get("estado") == "pendiente"
            if not pendiente:
                return trabajo
            extra_oci = extra_oci or asyncio.get_running_loop().time() + ESPERA_OCI
            if asyncio.get_running_loop().time() >= min(extra_oci, limite + ESPERA_OCI):
                return trabajo   # la copia sigue en curso: el paquete lo indica como «pendiente»
        elif asyncio.get_running_loop().time() >= limite:
            return trabajo
        await asyncio.sleep(INTERVALO)


@router.post("")
async def procesar(lote: LoteEnunciado, espera: int = Query(ESPERA_MAXIMA, ge=0, le=ESPERA_MAXIMA),
                   idempotency_key: str | None = Header(default=None, max_length=128)):
    encolado = await encolar_lote(completar(lote), idempotency_key, "manual")
    trabajo = await esperar(encolado["procesamiento_id"], espera)
    return respuesta(trabajo, len(lote.interacciones))


@router.get("/{identificador}")
async def consultar(identificador: str):
    try:
        trabajo = await asyncio.to_thread(cola().obtener, identificador)
        total = await asyncio.to_thread(_total, identificador) if trabajo else None
    except Exception:
        raise HTTPException(503, "Consulta temporalmente no disponible.") from None
    if trabajo is None:
        raise HTTPException(404, "Procesamiento no encontrado")
    return respuesta(trabajo, total)
