"""Estado de «escucha» por canal para el interruptor de «Conectar a Discord».

Escucha = el canal tiene una importación histórica en curso (pendiente o ejecutando). No toca el bot ni
el lector en vivo: el importador solo lee mientras trae el rango pedido y se detiene solo al terminar,
aunque se cierre el navegador. Apagar = cancelar la importación activa de ese canal.

  GET   /api/v1/discord/canales/{canal_id}/escucha   {canal_id, conectado, escuchando, deteniendo, importacion}
  PATCH /api/v1/discord/canales/{canal_id}/escucha   {"escuchando": false} cancela; true solo confirma una activa

`conectado` = el canal está en la lista autorizada del servidor (no consulta Discord). Visibilidad igual
que en el histórico: un operador ve y cancela solo sus importaciones; un administrador, todas.
"""
import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from backend.app.core.acceso import Operador
from backend.app.discord_historico.configuracion import Configuracion, ConfiguracionInvalida
from backend.app.discord_historico.fechas import es_snowflake
from backend.app.discord_historico.store import Store

router = APIRouter(prefix="/api/v1/discord/canales", tags=["Discord: escucha por canal"])


class CambioEscucha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    escuchando: bool


def _error(http, codigo, mensaje):
    return HTTPException(http, {"codigo": codigo, "mensaje": mensaje})


def _store():
    return Store(os.environ["DATABASE_URL"])


def _conectado(canal_id):
    try:
        config = Configuracion.desde_entorno()
    except ConfiguracionInvalida:
        return False
    return config.configurada and config.servidor_de(canal_id) is not None


def _estado(canal_id, principal):
    if not es_snowflake(canal_id):
        raise _error(422, "canal_invalido", "El ID del canal debe ser un número de Discord (snowflake).")
    activa = _store().activa_de_canal(canal_id)
    visible = activa is not None and (principal.es_administrador or activa.get("solicitante") == principal.solicitante)
    return activa, {
        "canal_id": canal_id,
        "conectado": _conectado(canal_id),
        # Una cancelación pedida durante la ejecución se completa entre páginas: ya no cuenta como escucha.
        "escuchando": activa is not None and not activa.get("cancelacion_solicitada"),
        "deteniendo": bool(activa and activa.get("cancelacion_solicitada")),
        "importacion": ({"id": activa["id"], "estado": activa["estado"]} if visible else None),
    }


@router.get("/{canal_id}/escucha")
async def consultar_escucha(canal_id: str, principal: Operador):
    _, estado = await asyncio.to_thread(_estado, canal_id, principal)
    return estado


@router.patch("/{canal_id}/escucha")
async def cambiar_escucha(canal_id: str, cambio: CambioEscucha, principal: Operador):
    activa, estado = await asyncio.to_thread(_estado, canal_id, principal)
    if cambio.escuchando:
        if not estado["escuchando"]:
            raise _error(409, "sin_importacion",
                         "Para escuchar un canal, completa el ID, las fechas y la zona horaria: la importación se inicia sola.")
        return estado
    if activa is None or activa.get("cancelacion_solicitada"):
        return estado                                   # ya apagado (o deteniéndose): idempotente
    if estado["importacion"] is None:
        raise _error(403, "importacion_ajena", "La importación activa de este canal pertenece a otra cuenta.")
    await asyncio.to_thread(_store().solicitar_cancelacion, activa["id"])
    _, estado = await asyncio.to_thread(_estado, canal_id, principal)
    return estado
