import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Configuración básica (idealmente usar variables de entorno)
OCI_BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "communitylab-activos-marketing")

async def subir_activo_aprobado_oci(id_activo: str, formato: str, copy: str) -> str:
    """
    Guarda el activo en Oracle Cloud Infrastructure (Object Storage) en la ruta aprobados/
    Si no hay credenciales, hace un mock/guardado local por ahora.
    """
    file_name = f"aprobados/{formato}_{id_activo}.md"
    file_content = f"# {formato.upper()}\n\n{copy}\n\n"
    
    logger.info(f"Pendiente de subir a OCI: {file_name}")
    
    # Aquí iría el código real de Boto3 o SDK OCI si tuvieran las credenciales:
    # s3_client = boto3.client('s3', endpoint_url="...", aws_access_key_id="...", aws_secret_access_key="...")
    # s3_client.put_object(Bucket=OCI_BUCKET_NAME, Key=file_name, Body=file_content.encode('utf-8'))

    return "pendiente_oci"
