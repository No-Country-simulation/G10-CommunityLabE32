"""Crea una cuenta (por ejemplo, el primer administrador) sin credenciales predeterminadas.

La contraseña se pide por teclado sin eco (dos veces) o se lee de la entrada estándar con
--contrasena-stdin. Nunca se acepta como argumento, no se imprime y no se registra.

Uso dentro del contenedor de la API (lee DATABASE_URL del entorno):
    docker compose exec api python -m backend.scripts.crear_usuario --email ana@ejemplo.org --rol administrador
Con la contraseña desde un gestor de contraseñas o un archivo temporal protegido:
    docker compose exec -T api python -m backend.scripts.crear_usuario --email ... --rol operador --contrasena-stdin < archivo
Requiere el esquema aplicado (db-init). No modifica cuentas existentes.
"""
import argparse
import getpass
import os
import sys

import psycopg

from backend.app.services.auth import ROLES, contrasena_valida, hash_contrasena, normalizar_email


def leer_contrasena(desde_stdin, entrada=None):
    if desde_stdin:
        return (entrada or sys.stdin).readline().rstrip("\r\n")
    primera = getpass.getpass("Contraseña (no se muestra): ")
    if getpass.getpass("Repetir contraseña: ") != primera:
        raise SystemExit("Las contraseñas no coinciden; no se creó la cuenta.")
    return primera


def crear(url, email, rol, contrasena, nombre=None):
    if rol not in ROLES:
        raise SystemExit(f"Rol inválido: use {', '.join(ROLES)}.")
    if not contrasena_valida(contrasena):
        raise SystemExit("La contraseña debe tener entre 10 caracteres y 72 bytes; no se creó la cuenta.")
    email = normalizar_email(email)
    with psycopg.connect(url.replace("postgresql+asyncpg://", "postgresql://", 1)) as c:
        fila = c.execute("""INSERT INTO usuarios (email, hashed_password, full_name, rol, is_active, created_at)
            VALUES (%s, %s, %s, %s, true, now()) ON CONFLICT (email) DO NOTHING RETURNING id""",
                         (email, hash_contrasena(contrasena), nombre, rol)).fetchone()
    if fila is None:
        raise SystemExit("Ya existe una cuenta con ese correo; no se modificó.")
    return fila[0]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--rol", choices=ROLES, required=True)
    p.add_argument("--nombre")
    p.add_argument("--contrasena-stdin", action="store_true", help="leer la contraseña de la entrada estándar")
    args = p.parse_args(argv)
    identificador = crear(os.environ["DATABASE_URL"], args.email, args.rol,
                          leer_contrasena(args.contrasena_stdin), args.nombre)
    print(f"Cuenta creada: id={identificador} rol={args.rol}")


if __name__ == "__main__":
    main()
