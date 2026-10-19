"""API de importación histórica de Discord. TODOS los endpoints exigen operador.

Prefijo: /api/v1/discord/historico
  POST /verificar                       comprueba acceso al canal (sin leer mensajes)
  POST /previsualizar                   rango normalizado, permisos, límites y conteo (1 página)
  POST /importaciones                   crea la importación (202); el runner la ejecuta aparte
  GET  /importaciones                   lista las últimas
  GET  /importaciones/{id}              estado y progreso
  POST /importaciones/{id}/cancelar     cancela (pendiente: al instante; ejecutando: entre páginas)
  POST /importaciones/{id}/reanudar     solo errores reanudables (límite de Discord o red)
  GET  /importaciones/{id}/mensajes     mensajes importados (paginado; protegido)
Importar no llama a la IA, no publica, no responde en Discord ni cierra períodos.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.acceso import solicitante_operador
from backend.app.discord_historico.cliente import ClienteDiscord, CredencialInvalida, ErrorDiscord
from backend.app.discord_historico.configuracion import Configuracion, ConfiguracionInvalida
from backend.app.discord_historico.fechas import RangoInvalido, normalizar_rango
from backend.app.discord_historico.servicio import AccesoDenegado, previsualizar, requiere_confirmacion, verificar_acceso
from backend.app.discord_historico.store import Conflicto, Store, huella_solicitud

router = APIRouter(prefix="/api/v1/discord/historico", tags=["Discord: importación histórica"])
Operador = Annotated[str, Depends(solicitante_operador)]


class Canal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canal_id: str = Field(min_length=1, max_length=25)


class Solicitud(Canal):
    desde: str = Field(min_length=10, max_length=40, description="AAAA-MM-DD o ISO 8601 con hora")
    hasta: str = Field(min_length=10, max_length=40, description="AAAA-MM-DD (día completo) o ISO 8601")
    zona: str = Field(min_length=1, max_length=64, description="Zona IANA, p. ej. America/Guatemala")
    max_mensajes: int | None = Field(default=None, ge=1)


class Previsualizacion(Solicitud):
    incluir_muestra: bool = False


class Importacion(Solicitud):
    confirmar_alcance: bool = False


def _error(http, codigo, mensaje):
    return HTTPException(http, {"codigo": codigo, "mensaje": mensaje})


def _config():
    try:
        config = Configuracion.desde_entorno()
    except ConfiguracionInvalida as e:
        raise _error(503, "configuracion_invalida", str(e)) from None
    if not config.configurada:
        raise _error(503, "discord_no_configurado", "El backend no tiene DISCORD_HISTORICO_TOKEN configurado.")
    return config


def _store():
    return Store(os.environ["DATABASE_URL"])


def _cliente(config):
    return ClienteDiscord(config.token, config.api_base)


def _traducir(exc):
    if isinstance(exc, RangoInvalido):
        return _error(422, exc.codigo, exc.mensaje)
    if isinstance(exc, AccesoDenegado):
        return _error(exc.http, exc.codigo, exc.mensaje)
    if isinstance(exc, CredencialInvalida):
        return _error(503, exc.codigo, "La credencial del bot no es válida.")
    if isinstance(exc, ErrorDiscord):
        return _error(502, exc.codigo, "Discord no respondió como se esperaba; reintente más tarde.")
    return None


async def _con_cliente(funcion, config):
    def ejecutar():
        cliente = _cliente(config)
        try:
            return funcion(cliente)
        finally:
            cliente.cerrar()
    try:
        return await asyncio.to_thread(ejecutar)
    except (RangoInvalido, AccesoDenegado, ErrorDiscord) as e:
        raise _traducir(e) from None


@router.post("/verificar")
async def verificar(datos: Canal, _: Operador):
    config = _config()
    return await _con_cliente(lambda c: verificar_acceso(c, config, datos.canal_id), config)


@router.post("/previsualizar")
async def previsualizar_rango(datos: Previsualizacion, _: Operador):
    config = _config()
    ahora = datetime.now(timezone.utc)
    return await _con_cliente(lambda c: previsualizar(c, config, datos.canal_id, datos.desde, datos.hasta,
                                                      datos.zona, ahora, datos.max_mensajes, datos.incluir_muestra),
                              config)


def _conflicto(e):
    mensajes = {"importacion_activa_en_el_canal": "Ya hay una importación activa para este canal.",
                "clave_idempotencia_reutilizada": "La clave de idempotencia ya identifica otra solicitud."}
    return HTTPException(409, {"codigo": e.codigo, "mensaje": mensajes.get(e.codigo, e.codigo),
                               "importacion": jsonable_encoder(e.existente)})


@router.post("/importaciones", status_code=202)
async def crear_importacion(datos: Importacion, solicitante: Operador,
                            idempotency_key: str | None = Header(default=None, max_length=128)):
    """Crea la importación. Con Idempotency-Key, repetir la MISMA solicitud devuelve la original.

    La comparación usa la huella de los parámetros solicitados, no el rango efectivo: si «hasta»
    incluye hoy, el corte se congeló en la primera solicitud y no se recalcula al reintentar.
    """
    config = _config()
    solicitud, huella = huella_solicitud(datos.canal_id, datos.desde, datos.hasta, datos.zona, datos.max_mensajes)
    if idempotency_key:
        try:
            previa = await asyncio.to_thread(_store().por_clave, idempotency_key, huella)
        except Conflicto as e:
            raise _conflicto(e) from None
        if previa is not None:
            # Recuperar no salta la autorización: operador (dependencia) + canal aún en la lista autorizada.
            if config.servidor_de(previa["canal_id"]) is None:
                raise _error(403, "canal_no_autorizado", "Este canal ya no está autorizado para importación histórica.")
            return {"importacion": previa, "reutilizada": True, "advertencias": []}
    ahora = datetime.now(timezone.utc)
    max_mensajes = datos.max_mensajes or config.max_mensajes
    if max_mensajes > config.max_mensajes:
        raise _error(422, "limite_invalido", f"max_mensajes no puede superar {config.max_mensajes}.")
    try:
        rango = normalizar_rango(datos.desde, datos.hasta, datos.zona, ahora, config.max_dias)
    except RangoInvalido as e:
        raise _traducir(e) from None
    if requiere_confirmacion(config, rango, max_mensajes) and not datos.confirmar_alcance:
        raise _error(409, "confirmacion_requerida",
                     f"El alcance ({rango.dias:.1f} días, hasta {max_mensajes} mensajes) requiere confirmar_alcance=true.")
    acceso = await _con_cliente(lambda c: verificar_acceso(c, config, datos.canal_id), config)
    try:
        importacion, nueva = await asyncio.to_thread(
            _store().crear, guild_id=acceso["servidor"]["id"], canal_id=datos.canal_id,
            canal_nombre=acceso["canal"]["nombre"], canal_tipo=acceso["canal"]["tipo"], rango=rango,
            max_mensajes=max_mensajes, solicitante=solicitante, clave_idempotencia=idempotency_key,
            solicitud=solicitud, huella=huella)
    except Conflicto as e:
        raise _conflicto(e) from None
    return {"importacion": importacion, "reutilizada": not nueva,
            "advertencias": list(rango.advertencias) if nueva else []}


def _obtener(identificador):
    fila = _store().obtener(identificador)
    if fila is None:
        raise _error(404, "importacion_no_encontrada", "Importación no encontrada.")
    return fila


@router.get("/importaciones")
async def listar(_: Operador, limite: int = Query(20, ge=1, le=100)):
    return {"items": await asyncio.to_thread(_store().listar, limite)}


@router.get("/importaciones/{identificador}")
async def consultar(identificador: str, _: Operador):
    return await asyncio.to_thread(_obtener, identificador)


@router.post("/importaciones/{identificador}/cancelar")
async def cancelar(identificador: str, _: Operador):
    await asyncio.to_thread(_obtener, identificador)
    return await asyncio.to_thread(_store().solicitar_cancelacion, identificador)


@router.post("/importaciones/{identificador}/reanudar")
async def reanudar(identificador: str, _: Operador):
    await asyncio.to_thread(_obtener, identificador)
    try:
        return await asyncio.to_thread(_store().reanudar, identificador)
    except Conflicto as e:
        if e.codigo == "no_reanudable":
            raise HTTPException(409, {"codigo": e.codigo, "mensaje": "La importación no se puede reanudar en su estado actual.",
                                      "importacion": jsonable_encoder(e.existente)}) from None
        raise _conflicto(e) from None


@router.get("/importaciones/{identificador}/mensajes")
async def mensajes(identificador: str, _: Operador, limite: int = Query(50, ge=1, le=200),
                   desplazamiento: int = Query(0, ge=0)):
    await asyncio.to_thread(_obtener, identificador)
    filas, total = await asyncio.to_thread(_store().mensajes, identificador, limite, desplazamiento)
    return {"total": total, "items": filas}
