"""Control de acceso centralizado. Política por endpoint: docs/politica-acceso.md.

Credenciales y dónde valen (no son intercambiables):
- Sesión de persona (cookie HttpOnly `cl_sesion`, ver services/auth.py): rol usuario, operador o
  administrador, leído de la base en cada petición. Las peticiones que modifican estado exigen
  además la cabecera X-CSRF-Token.
- X-Operador-Token = OPERADOR_TOKEN: compatibilidad explícita y limitada para scripts y operación
  por terminal (no para el navegador). Equivale al rol operador; nunca a administrador ni al puente.
  Solo se evalúa si la cabecera está presente: sin OPERADOR_TOKEN configurado -> 503; distinto -> 401.
- Authorization: Bearer PUENTE_TOKEN: solo el servicio puente (rutas /api/v1/puente/* y la
  entrega y consulta de lotes en /api/v1/trabajos). Sin PUENTE_TOKEN configurado -> 503.
La configuración se lee en cada petición. Los tokens no se registran ni se devuelven.
"""
import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from backend.app.core.database import AsyncSessionLocal
from backend.app.services import auth

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    tipo: str                       # "sesion" | "operador_token" | "puente"
    rol: str | None = None          # rol efectivo para personas y token de operador
    sesion: auth.SesionValida | None = None

    @property
    def solicitante(self) -> str:
        """Identificador para auditoría: sin email ni secretos."""
        if self.sesion is not None:
            return f"usuario:{self.sesion.usuario_id}"
        return "operador:token-compartido" if self.tipo == "operador_token" else "puente"

    @property
    def es_administrador(self) -> bool:
        return self.rol == "administrador"


def _error(http, codigo, mensaje):
    return HTTPException(http, {"codigo": codigo, "mensaje": mensaje})


def _comparar(variable: str, recibido: str | None, nombre: str) -> None:
    esperado = os.environ.get(variable) or ""
    if not esperado:
        raise _error(503, "acceso_no_configurado", f"La acción requiere {variable} configurado en el servidor.")
    if not recibido or not hmac.compare_digest(recibido.encode(), esperado.encode()):
        raise _error(401, "token_invalido", f"{nombre} ausente o inválido.")


async def sesion_de(request: Request) -> auth.SesionValida:
    """Sesión vigente de la cookie, con CSRF en métodos que modifican estado. 401/403/503 si no."""
    token = request.cookies.get(auth.COOKIE_SESION)
    if not token:
        raise _error(401, "sesion_requerida", "Inicie sesión para continuar.")
    try:
        async with AsyncSessionLocal() as db:
            sesion = await auth.validar_sesion(db, token)
        if request.method not in METODOS_SEGUROS and not auth.csrf_valido(
                sesion.id, request.headers.get(auth.CABECERA_CSRF)):
            raise _error(403, "csrf_invalido", "Falta o no coincide la cabecera X-CSRF-Token.")
    except auth.AutenticacionNoConfigurada:
        raise _error(503, "autenticacion_no_configurada",
                     "La autenticación de usuarios no está configurada en el servidor.") from None
    except auth.SesionInvalida:
        raise _error(401, "sesion_invalida", "La sesión no es válida o expiró. Inicie sesión de nuevo.") from None
    return sesion


def requiere_rol(minimo: str, *, admite_token_operador: bool = True):
    async def dependencia(request: Request,
                          x_operador_token: str | None = Header(default=None, max_length=256)) -> Principal:
        if x_operador_token is not None and admite_token_operador and auth.NIVEL[minimo] <= auth.NIVEL["operador"]:
            _comparar("OPERADOR_TOKEN", x_operador_token, "Token de operador")
            return Principal("operador_token", "operador")
        sesion = await sesion_de(request)
        if auth.NIVEL[sesion.rol] < auth.NIVEL[minimo]:
            raise _error(403, "permiso_insuficiente", "Su cuenta no tiene permiso para esta acción.")
        return Principal("sesion", sesion.rol, sesion)
    return dependencia


requiere_usuario = requiere_rol("usuario")
requiere_operador = requiere_rol("operador")
requiere_administrador = requiere_rol("administrador", admite_token_operador=False)
Usuario = Annotated[Principal, Depends(requiere_usuario)]
Operador = Annotated[Principal, Depends(requiere_operador)]
Administrador = Annotated[Principal, Depends(requiere_administrador)]


async def solicitante_operador(principal: Operador) -> str:
    """Quién solicita una acción de operador, para registrarlo (Discord histórico)."""
    return principal.solicitante


def requiere_puente(authorization: str | None = Header(default=None, max_length=300)) -> Principal:
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    _comparar("PUENTE_TOKEN", token, "Token del puente")
    return Principal("puente")


async def requiere_puente_u_operador(request: Request,
                                     authorization: str | None = Header(default=None, max_length=300),
                                     x_operador_token: str | None = Header(default=None, max_length=256)) -> Principal:
    """Entrega y consulta de lotes: el puente con su Bearer, o una persona operadora."""
    if authorization is not None:
        return requiere_puente(authorization)
    return await requiere_operador(request, x_operador_token)
