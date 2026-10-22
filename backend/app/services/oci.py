"""Copia de los activos aprobados en OCI Object Storage.

Acceso por identidad de la instancia (instance principal): la VM pertenece al grupo dinámico
`communitylab-vm-dg` y la política `communitylab-vm-bucket-policy` le permite leer el bucket y
crear o sobrescribir objetos (no borrarlos). No hay llaves en el `.env` ni en el repositorio.

Variables:
- OCI_ALMACENAMIENTO: `instance_principal` para subir; cualquier otro valor (por defecto
  `desactivado`) no llama a OCI y registra el activo como no subido.
- OCI_BUCKET_NAME (por defecto `communitylab-activos-marketing`) y OCI_NAMESPACE (opcional: si
  falta, se consulta una vez).

Objetos por aprobación: `aprobados/<id_activo>/v<versión>/activo.json` y, si el activo tiene un
banner generado para esa versión, `.../banner.svg`. Un fallo de OCI nunca impide aprobar: queda
registrado en `activos.almacenamiento_oci` y se puede reintentar con
`python -m backend.scripts.oci_almacenamiento --subir-aprobados --aplicar`.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OCI_BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "communitylab-activos-marketing")
PREFIJO = "aprobados"
_cliente = None
_namespace = None


def modo():
    return os.getenv("OCI_ALMACENAMIENTO", "desactivado").strip().lower()


def habilitado():
    return modo() == "instance_principal"


def _cliente_oci():
    """Cliente de Object Storage firmado con la identidad de la instancia (se crea una vez)."""
    global _cliente, _namespace
    if _cliente is None:
        import oci
        firmante = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        _cliente = oci.object_storage.ObjectStorageClient(config={"region": firmante.region}, signer=firmante)
    if _namespace is None:
        _namespace = os.getenv("OCI_NAMESPACE") or _cliente.get_namespace().data
    return _cliente, _namespace


def subir_objeto(nombre: str, contenido: bytes, tipo: str) -> None:
    cliente, namespace = _cliente_oci()
    cliente.put_object(namespace, OCI_BUCKET_NAME, nombre, contenido, content_type=tipo)


def leer_objeto(nombre: str) -> bytes:
    cliente, namespace = _cliente_oci()
    return cliente.get_object(namespace, OCI_BUCKET_NAME, nombre).data.content


def datos_para_oci(activo) -> dict:
    """Contenido publicable de un activo aprobado (sin datos de las cuentas que lo revisaron)."""
    return {"id_activo": activo.id_activo, "version": activo.version, "formato": activo.formato,
            "titulo": activo.titulo, "copy": activo.copy, "posts_redes": activo.posts_redes,
            "fuentes": list(activo.fuentes or []), "advertencias_fidelidad": activo.advertencias_fidelidad,
            "aprobado": datetime.now(timezone.utc).isoformat()}


def objetos_de(activo_dict: dict, banner_svg: str | None) -> list[tuple[str, bytes, str]]:
    """Objetos a subir para una versión aprobada (nombre, contenido, tipo)."""
    base = f"{PREFIJO}/{activo_dict['id_activo']}/v{activo_dict['version']}"
    objetos = [(f"{base}/activo.json",
                json.dumps(activo_dict, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                "application/json; charset=utf-8")]
    if banner_svg:
        objetos.append((f"{base}/banner.svg", banner_svg.encode("utf-8"), "image/svg+xml"))
    return objetos


def _subir(objetos):
    for nombre, contenido, tipo in objetos:
        subir_objeto(nombre, contenido, tipo)


async def subir_activo_aprobado_oci(activo_dict: dict, banner_svg: str | None = None) -> dict:
    """Sube la versión aprobada y devuelve el registro para `activos.almacenamiento_oci` (nunca lanza)."""
    fecha = datetime.now(timezone.utc).isoformat()
    if not habilitado():
        return {"estado": "desactivado", "fecha": fecha}
    objetos = objetos_de(activo_dict, banner_svg)
    try:
        await asyncio.to_thread(_subir, objetos)
    except Exception as error:  # el detalle va al log; al activo solo el tipo de error
        logger.warning("No se pudo subir %s a OCI: %s", activo_dict["id_activo"], type(error).__name__)
        return {"estado": "error", "fecha": fecha, "error": type(error).__name__}
    return {"estado": "guardado", "fecha": fecha, "bucket": OCI_BUCKET_NAME, "objetos": [o[0] for o in objetos]}
