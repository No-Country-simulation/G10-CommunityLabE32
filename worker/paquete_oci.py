"""Copia en OCI Object Storage del paquete de distribución de cada procesamiento terminado.

El enunciado pide persistir en el bucket todos los paquetes de activos generados (no solo los
aprobados). Al terminar un trabajo, el worker sube su paquete (resumen, borradores y alertas) a
`activos/<período>/<procesamiento>/paquete-distribucion.json`. Usa la misma identidad de la instancia
que la copia de aprobados (backend/app/services/oci.py). Un fallo de OCI nunca hace fallar el
procesamiento: queda registrado en `resultado.almacenamiento`.
"""
from datetime import datetime, timezone
import json
import logging

from pipelines.communitylab.paquete import paquete_distribucion, ruta_paquete

LOG = logging.getLogger(__name__)
CAPA = "oci_object_storage"


def _oci():
    from backend.app.services import oci   # import tardío: sin OCI configurado no se necesita el SDK
    return oci


def estado_inicial():
    """Valor de `almacenamiento` al guardar el resultado: «pendiente» si se va a subir."""
    return {"capa": CAPA, "estado": "pendiente" if _oci().habilitado() else "desactivado"}


def subir_paquete(procesamiento_id, entrada, resultado):
    """Sube el paquete y devuelve el registro de `almacenamiento` (nunca lanza)."""
    oci = _oci()
    fecha = datetime.now(timezone.utc).isoformat()
    if not oci.habilitado():
        return {"capa": CAPA, "estado": "desactivado", "fecha": fecha}
    ruta = ruta_paquete(resultado.get("periodo_referencia"), procesamiento_id)
    registro = {"capa": CAPA, "estado": "guardado", "bucket": oci.OCI_BUCKET_NAME, "ruta_objeto": ruta,
                "fecha": fecha}
    paquete = paquete_distribucion({**resultado, "almacenamiento": registro}, procesamiento_id=procesamiento_id,
                                   total_interacciones=len(entrada.get("interacciones") or []))
    try:
        oci.subir_objeto(ruta, json.dumps(paquete, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                         "application/json; charset=utf-8")
    except Exception as error:   # el detalle va al log; al resultado solo el tipo de error
        LOG.warning("paquete_oci trabajo=%s error=%s", procesamiento_id, type(error).__name__)
        return {"capa": CAPA, "estado": "error", "fecha": fecha, "error": type(error).__name__}
    return registro
