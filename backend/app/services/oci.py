import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Configuración básica (idealmente usar variables de entorno)
OCI_BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "communitylab-alwaysfree-bucket")

async def subir_activo_aprobado_oci(id_activo: str, formato: str, copy: str) -> str:
    """
    Guarda el activo en Oracle Cloud Infrastructure (Object Storage) en la ruta aprobados/
    Si no hay credenciales, hace un mock/guardado local por ahora.
    """
    file_name = f"aprobados/{formato}_{id_activo}.md"
    file_content = f"# {formato.upper()}\n\n{copy}\n\n"
    
    # Simulación de subida (Fallback para desarrollo local)
    os.makedirs("aprobados_local_mock", exist_ok=True)
    local_path = os.path.join("aprobados_local_mock", f"{formato}_{id_activo}.md")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(file_content)
    
    logger.info(f"Subido a OCI (Simulado): {file_name}")
    
    # Aquí iría el código real de Boto3 o SDK OCI si tuvieran las credenciales:
    # s3_client = boto3.client('s3', endpoint_url="...", aws_access_key_id="...", aws_secret_access_key="...")
    # s3_client.put_object(Bucket=OCI_BUCKET_NAME, Key=file_name, Body=file_content.encode('utf-8'))

    return f"oci://{OCI_BUCKET_NAME}/{file_name}"
