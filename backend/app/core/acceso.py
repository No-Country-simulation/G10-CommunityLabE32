"""Control de acceso mínimo para acciones operativas, sin cuentas de usuario.

- Acciones de operador (procesar pendientes, aprobar textos, generar y revisar banners,
  reprocesar sentimiento): cabecera X-Operador-Token igual a OPERADOR_TOKEN.
- Puente Discord -> API (tomar solicitudes, informar avance): Authorization: Bearer PUENTE_TOKEN.

Si la variable no está configurada, la acción se rechaza (503): nunca queda abierta por omisión.
Los tokens no se registran ni se devuelven en respuestas.
"""
import hmac
import os

from fastapi import Header, HTTPException


def _comparar(variable: str, recibido: str | None, nombre: str) -> None:
    esperado = os.environ.get(variable) or ""
    if not esperado:
        raise HTTPException(503, {"codigo": "acceso_no_configurado",
                                  "mensaje": f"La acción requiere {variable} configurado en el servidor."})
    if not recibido or not hmac.compare_digest(recibido.encode(), esperado.encode()):
        raise HTTPException(401, {"codigo": "token_invalido", "mensaje": f"{nombre} ausente o inválido."})


def requiere_operador(x_operador_token: str | None = Header(default=None, max_length=256)) -> None:
    _comparar("OPERADOR_TOKEN", x_operador_token, "Token de operador")


def requiere_puente(authorization: str | None = Header(default=None, max_length=300)) -> None:
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    _comparar("PUENTE_TOKEN", token, "Token del puente")


def solicitante_operador(x_operador_token: str | None = Header(default=None, max_length=256)) -> str:
    """Igual que requiere_operador, pero devuelve quién solicita, para registrarlo.

    Hoy el token es compartido y no identifica a la persona: se registra «operador:token-compartido».
    Cuando exista el sistema de usuarios, esta función devolverá el usuario autenticado y los
    endpoints que la usan no tendrán que cambiar.
    """
    requiere_operador(x_operador_token)
    return "operador:token-compartido"
