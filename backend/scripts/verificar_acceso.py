"""Comprueba que una cuenta puede iniciar sesión, sin mostrar la contraseña ni el token.

Hace el recorrido real del navegador contra la API local del contenedor: login (cookie de sesión),
GET /api/auth/sesion y una lectura del rol pedido. Imprime solo códigos y el rol. Sale con 0 si todo
es correcto. Úsese tras crear o restablecer el administrador, ANTES de dar el despliegue por terminado:
    docker compose exec -T api python -m backend.scripts.verificar_acceso --email <correo> < archivo-protegido
(o sin redirección: pide la contraseña sin eco). Cuenta como un intento de login más (límite de intentos).
"""
import argparse
import getpass
import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

LECTURA_POR_ROL = {"usuario": "/api/dashboard/kpis", "operador": "/api/mensajes?limit=1",
                   "administrador": "/api/auth/usuarios"}


def verificar(base, email, contrasena, salida=print):
    tarro = http.cookiejar.CookieJar()
    abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(tarro)).open

    def pedir(ruta, datos=None):
        try:
            with abrir(urllib.request.Request(base + ruta, data=datos), timeout=10) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, None

    codigo, cuerpo = pedir("/api/auth/login", urllib.parse.urlencode(
        {"username": email, "password": contrasena}).encode())
    salida(f"login={codigo}")
    if codigo != 200:
        return 1
    rol = cuerpo["usuario"]["rol"]
    codigo, _ = pedir("/api/auth/sesion")
    lectura, _ = pedir(LECTURA_POR_ROL[rol])
    salida(f"sesion={codigo} rol={rol} lectura_{rol}={lectura}")
    return 0 if codigo == 200 and lectura == 200 else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    args = p.parse_args(argv)
    contrasena = sys.stdin.readline().rstrip("\r\n") if not sys.stdin.isatty() else getpass.getpass("Contraseña: ")
    return verificar(args.base, args.email, contrasena)


if __name__ == "__main__":
    sys.exit(main())
