"""Comprueba el acceso a OCI Object Storage y sube los activos aprobados que aún no tienen copia.

Uso (contenedor de la API, con OCI_ALMACENAMIENTO=instance_principal):
    python -m backend.scripts.oci_almacenamiento --verificar
        Escribe y vuelve a leer demo/verificacion-vm.txt (el mismo objeto siempre: la política no
        permite borrar, así que se sobrescribe en lugar de acumular pruebas).
    python -m backend.scripts.oci_almacenamiento --subir-aprobados [--aplicar]
        Sin --aplicar solo cuenta los aprobados sin copia (o con error); con --aplicar los sube y
        guarda el resultado en activos.almacenamiento_oci.
Imprime conteos y nombres de objetos, nunca textos ni credenciales.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import psycopg
from psycopg.rows import dict_row

from backend.app.services import oci

VERIFICACION = "demo/verificacion-vm.txt"
PENDIENTES = """SELECT id_activo, version, formato, titulo, copy, posts_redes, fuentes, advertencias_fidelidad
    FROM activos WHERE estado = 'aprobado'
    AND (almacenamiento_oci IS NULL OR almacenamiento_oci->>'estado' IS DISTINCT FROM 'guardado')
    ORDER BY id_activo"""
BANNER = """SELECT svg FROM banners WHERE id_activo = %s AND version_texto = %s
    AND estado = 'generado' AND svg IS NOT NULL"""


def verificar():
    marca = f"CommunityLab: verificación de acceso {datetime.now(timezone.utc).isoformat()}".encode()
    oci.subir_objeto(VERIFICACION, marca, "text/plain; charset=utf-8")
    leido = oci.leer_objeto(VERIFICACION)
    print(f"bucket={oci.OCI_BUCKET_NAME} objeto={VERIFICACION} escritura=ok lectura={'ok' if leido == marca else 'distinta'}")
    return leido == marca


def subir_aprobados(aplicar):
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    subidos = errores = 0
    with psycopg.connect(url, row_factory=dict_row) as c:
        pendientes = c.execute(PENDIENTES).fetchall()
        print(f"aprobados_sin_copia={len(pendientes)} aplicado={aplicar}")
        if not aplicar:
            return
        for fila in pendientes:
            banner = c.execute(BANNER, (fila["id_activo"], fila["version"])).fetchone()
            datos = oci.datos_para_oci(SimpleNamespace(**fila))
            registro = {"fecha": datetime.now(timezone.utc).isoformat()}
            try:
                objetos = oci.objetos_de(datos, banner["svg"] if banner else None)
                for nombre, contenido, tipo in objetos:
                    oci.subir_objeto(nombre, contenido, tipo)
                registro.update(estado="guardado", bucket=oci.OCI_BUCKET_NAME, objetos=[o[0] for o in objetos])
                subidos += 1
            except Exception as error:
                registro.update(estado="error", error=type(error).__name__)
                errores += 1
            c.execute("UPDATE activos SET almacenamiento_oci = %s WHERE id_activo = %s",
                      (json.dumps(registro), fila["id_activo"]))
    print(f"subidos={subidos} errores={errores}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--verificar", action="store_true", help="escribir y leer un objeto de prueba")
    g.add_argument("--subir-aprobados", action="store_true", help="subir los aprobados sin copia")
    p.add_argument("--aplicar", action="store_true", help="con --subir-aprobados: subir y guardar")
    args = p.parse_args()
    if not oci.habilitado():
        raise SystemExit(f"OCI_ALMACENAMIENTO={oci.modo()}: defínelo como instance_principal para usar OCI.")
    if args.verificar:
        sys.exit(0 if verificar() else 1)
    subir_aprobados(args.aplicar)


if __name__ == "__main__":
    main()
