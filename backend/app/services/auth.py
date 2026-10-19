"""Autenticación de personas: contraseñas bcrypt y sesiones JWT respaldadas por el servidor.

- El navegador recibe el JWT en una cookie HttpOnly (nunca en el cuerpo ni en localStorage).
- Cada JWT identifica una fila de `sesiones` (claim jti): cerrar sesión, deshabilitar al usuario
  o cambiar su rol o contraseña revoca la sesión en el servidor aunque el JWT siga vigente.
- Firma HS256 con JWT_SECRET_KEY (obligatoria, sin valor por defecto). Se exigen exp, iat, sub y jti.
- El rol se lee de la base en cada petición; nunca del token ni de datos enviados por el cliente.
- CSRF: el token es un HMAC de la sesión (no se guarda) y se exige en la cabecera X-CSRF-Token
  en toda petición que modifica estado con cookie de sesión.
No registra contraseñas, tokens ni la clave.
"""
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import text

ALGORITMO = "HS256"
ROLES = ("usuario", "operador", "administrador")
NIVEL = {rol: i for i, rol in enumerate(ROLES)}
COOKIE_SESION = "cl_sesion"
CABECERA_CSRF = "X-CSRF-Token"
MAX_BYTES_CONTRASENA = 72  # límite de bcrypt: más bytes no se verifican
# SHA-256 de claves que estuvieron publicadas en el repositorio como valor por defecto: se rechazan.
CLAVES_PUBLICADAS = {
    "8f09746edf67d5834b39529b6e5ee4ea07ce4c2ef17d6d0352efd655bead0c53",
    "67dcedf9daa040b49754646b64933af856fc33894a1ac22cc3a52de6902aebb3",
}


class AutenticacionNoConfigurada(Exception):
    """Falta JWT_SECRET_KEY o no es aceptable: la autenticación de personas queda cerrada (503)."""


class SesionInvalida(Exception):
    """Token ausente, manipulado, vencido, revocado o de un usuario deshabilitado (401)."""


@dataclass(frozen=True)
class SesionValida:
    id: str
    usuario_id: int
    email: str
    full_name: str | None
    rol: str
    expira: datetime


def _huella(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def clave_jwt() -> str:
    """JWT_SECRET_KEY leída en cada uso (sin valores obsoletos entre pruebas y ejecución)."""
    clave = os.environ.get("JWT_SECRET_KEY", "")
    if len(clave.encode()) < 32 or _huella(clave) in CLAVES_PUBLICADAS:
        raise AutenticacionNoConfigurada()
    return clave


def horas_sesion() -> int:
    try:
        horas = int(os.environ.get("SESION_HORAS", "8"))
    except ValueError:
        horas = 8
    return min(max(horas, 1), 72)


def cookie_segura() -> bool:
    """Secure por defecto; solo un valor explícito «false» lo desactiva (desarrollo local por HTTP)."""
    return os.environ.get("SESION_COOKIE_SEGURA", "true").strip().lower() != "false"


def registro_publico() -> bool:
    return os.environ.get("REGISTRO_PUBLICO", "false").strip().lower() == "true"


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def contrasena_valida(contrasena: str) -> bool:
    return 10 <= len(contrasena) and len(contrasena.encode("utf-8")) <= MAX_BYTES_CONTRASENA


def hash_contrasena(contrasena: str) -> str:
    if not contrasena_valida(contrasena):
        raise ValueError("La contraseña debe tener entre 10 caracteres y 72 bytes.")
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


_HASH_FICTICIO = bcrypt.hashpw(secrets.token_bytes(16).hex().encode(), bcrypt.gensalt()).decode()


def verificar_contrasena(contrasena: str, hash_guardado: str | None) -> bool:
    """Tiempo similar exista o no el usuario (se verifica contra un hash ficticio)."""
    datos = contrasena.encode("utf-8")
    if len(datos) > MAX_BYTES_CONTRASENA:
        bcrypt.checkpw(b"x", _HASH_FICTICIO.encode())
        return False
    try:
        return bcrypt.checkpw(datos, (hash_guardado or _HASH_FICTICIO).encode()) and hash_guardado is not None
    except ValueError:
        return False


def csrf_de(sesion_id: str) -> str:
    return hmac.new(clave_jwt().encode(), f"csrf:{sesion_id}".encode(), hashlib.sha256).hexdigest()


def csrf_valido(sesion_id: str, recibido: str | None) -> bool:
    return bool(recibido) and hmac.compare_digest(csrf_de(sesion_id), recibido)


async def crear_sesion(db, usuario_id: int) -> tuple[str, str, datetime]:
    """Registra la sesión y devuelve (jwt, csrf, expira). Hace commit."""
    clave = clave_jwt()
    ahora = datetime.now(timezone.utc)
    expira = ahora + timedelta(hours=horas_sesion())
    sesion_id = secrets.token_urlsafe(32)
    # Limpieza acotada a la cuenta: sesiones vencidas o revocadas hace más de 7 días.
    await db.execute(text("""DELETE FROM sesiones WHERE usuario_id = :u
        AND (expira < now() - interval '7 days' OR revocada < now() - interval '7 days')"""), {"u": usuario_id})
    await db.execute(text("INSERT INTO sesiones (id, usuario_id, expira) VALUES (:id, :u, :e)"),
                     {"id": sesion_id, "u": usuario_id, "e": expira})
    await db.commit()
    token = jwt.encode({"sub": str(usuario_id), "jti": sesion_id, "iat": int(ahora.timestamp()),
                        "exp": int(expira.timestamp()), "typ": "sesion"}, clave, algorithm=ALGORITMO)
    return token, csrf_de(sesion_id), expira


async def validar_sesion(db, token: str | None) -> SesionValida:
    """Firma, algoritmo, campos y expiración del JWT; luego sesión vigente y usuario habilitado."""
    if not token or len(token) > 2048:
        raise SesionInvalida()
    clave = clave_jwt()
    try:
        datos = jwt.decode(token, clave, algorithms=[ALGORITMO],
                           options={"require_exp": True, "require_iat": True, "require_sub": True,
                                    "require_jti": True, "verify_exp": True, "leeway": 0})
    except JWTError:
        raise SesionInvalida() from None
    if datos.get("typ") != "sesion" or not str(datos.get("sub", "")).isdigit() or not isinstance(datos.get("jti"), str):
        raise SesionInvalida()
    fila = (await db.execute(text("""
        SELECT s.id, s.usuario_id, s.expira, u.email, u.full_name, u.rol, u.is_active
        FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
        WHERE s.id = :id AND s.revocada IS NULL AND s.expira > clock_timestamp()"""),
        {"id": datos["jti"]})).mappings().first()
    if fila is None or str(fila["usuario_id"]) != datos["sub"] or not fila["is_active"] or fila["rol"] not in NIVEL:
        raise SesionInvalida()
    return SesionValida(fila["id"], fila["usuario_id"], fila["email"], fila["full_name"], fila["rol"], fila["expira"])


async def revocar_sesion(db, sesion_id: str) -> None:
    await db.execute(text("UPDATE sesiones SET revocada = clock_timestamp() WHERE id = :id AND revocada IS NULL"),
                     {"id": sesion_id})


async def revocar_sesiones_de(db, usuario_id: int, excepto: str | None = None) -> None:
    await db.execute(text("""UPDATE sesiones SET revocada = clock_timestamp()
        WHERE usuario_id = :u AND revocada IS NULL AND (CAST(:x AS text) IS NULL OR id <> :x)"""),
        {"u": usuario_id, "x": excepto})
