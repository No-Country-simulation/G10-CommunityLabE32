"""Cuentas y sesiones. El JWT viaja solo en una cookie HttpOnly; ver services/auth.py y docs/politica-acceso.md.

Anónimo: POST /login, POST /register (solo con REGISTRO_PUBLICO=true; crea rol «usuario»).
Sesión:  GET /sesion (recupera csrf_token tras recargar), POST /logout, GET y PATCH /me.
Administrador: GET/POST /usuarios, PATCH /usuarios/{id} (rol y habilitación; revoca sus sesiones).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.acceso import Administrador, Usuario as UsuarioActual, sesion_de
from backend.app.core.database import get_db
from backend.app.models.usuario import Usuario
from backend.app.schemas.usuario import (SesionResponse, UsuarioAdminUpdate, UsuarioCreadoPorAdmin, UsuarioCreate,
                                         UsuarioResponse, UsuarioUpdate)
from backend.app.services import auth
from backend.app.services.limite_login import LIMITE, ip_cliente

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])
CREDENCIALES_INVALIDAS = {"codigo": "credenciales_invalidas", "mensaje": "Correo o contraseña incorrectos."}


def _error(http, codigo, mensaje):
    return HTTPException(http, {"codigo": codigo, "mensaje": mensaje})


def _sin_configurar():
    return _error(503, "autenticacion_no_configurada", "La autenticación de usuarios no está configurada en el servidor.")


async def _por_email(db, email):
    return (await db.execute(select(Usuario).where(Usuario.email == auth.normalizar_email(email)))).scalar_one_or_none()


async def _crear(db, datos: UsuarioCreate, rol: str) -> Usuario:
    usuario = Usuario(email=auth.normalizar_email(datos.email), full_name=(datos.full_name or "").strip() or None,
                      hashed_password=auth.hash_contrasena(datos.password), rol=rol, is_active=True)
    db.add(usuario)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _error(409, "email_en_uso", "Ese correo electrónico ya está registrado.") from None
    await db.refresh(usuario)
    return usuario


def _poner_cookie(response: Response, token, expira):
    response.set_cookie(auth.COOKIE_SESION, token, httponly=True, secure=auth.cookie_segura(), samesite="strict",
                        path="/api", expires=expira)


def _quitar_cookie(response: Response):
    response.delete_cookie(auth.COOKIE_SESION, path="/api", httponly=True, secure=auth.cookie_segura(),
                           samesite="strict")


@router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def register(usuario_in: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    if not auth.registro_publico():
        raise _error(403, "registro_deshabilitado", "El registro público está deshabilitado. Solicite una cuenta.")
    try:
        auth.clave_jwt()
    except auth.AutenticacionNoConfigurada:
        raise _sin_configurar() from None
    if not auth.contrasena_valida(usuario_in.password):
        raise _error(422, "contrasena_invalida", "La contraseña debe tener entre 10 caracteres y 72 bytes.")
    return await _crear(db, usuario_in, "usuario")


@router.post("/login", response_model=SesionResponse)
async def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_db)):
    try:
        auth.clave_jwt()
    except auth.AutenticacionNoConfigurada:
        raise _sin_configurar() from None
    email, ip = auth.normalizar_email(form_data.username)[:255], ip_cliente(request)
    if LIMITE.bloqueado(ip, email):
        raise HTTPException(429, {"codigo": "demasiados_intentos",
                                  "mensaje": "Demasiados intentos. Espere unos minutos e intente de nuevo."})
    usuario = await _por_email(db, email)
    valida = auth.verificar_contrasena(form_data.password, usuario.hashed_password if usuario else None)
    if not valida or not usuario.is_active or usuario.rol not in auth.NIVEL:
        LIMITE.fallo(ip, email)
        # Mismo mensaje y código exista o no la cuenta, o esté deshabilitada.
        raise HTTPException(401, CREDENCIALES_INVALIDAS)
    LIMITE.exito(ip, email)
    token, csrf, expira = await auth.crear_sesion(db, usuario.id)
    _poner_cookie(response, token, expira)
    response.headers["Cache-Control"] = "no-store"
    return {"usuario": usuario, "csrf_token": csrf, "expira": expira}


@router.get("/sesion", response_model=SesionResponse)
async def sesion_actual(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    sesion = await sesion_de(request)
    usuario = await db.get(Usuario, sesion.usuario_id)
    response.headers["Cache-Control"] = "no-store"
    return {"usuario": usuario, "csrf_token": auth.csrf_de(sesion.id), "expira": sesion.expira}


@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Revoca la sesión en el servidor (exige CSRF) y borra la cookie."""
    sesion = await sesion_de(request)
    await auth.revocar_sesion(db, sesion.id)
    await db.commit()
    salida = Response(status_code=204)
    _quitar_cookie(salida)
    return salida


@router.get("/me", response_model=UsuarioResponse)
async def obtener_perfil_actual(principal: UsuarioActual, db: AsyncSession = Depends(get_db)):
    """Datos de la persona con sesión. El token de operador no representa a ninguna cuenta."""
    if principal.sesion is None:
        raise _error(401, "sesion_requerida", "Inicie sesión para continuar.")
    return await db.get(Usuario, principal.sesion.usuario_id)


@router.patch("/me", response_model=UsuarioResponse)
async def actualizar_perfil_actual(datos: UsuarioUpdate, principal: UsuarioActual,
                                   db: AsyncSession = Depends(get_db)):
    """Nombre libre; correo y contraseña exigen la contraseña actual. Cambiar la contraseña
    revoca las demás sesiones de la cuenta."""
    if principal.sesion is None:
        raise _error(401, "sesion_requerida", "Inicie sesión para continuar.")
    usuario = await db.get(Usuario, principal.sesion.usuario_id)
    nuevo_email = auth.normalizar_email(datos.email) if datos.email else None
    cambia_email = nuevo_email is not None and nuevo_email != usuario.email
    if (cambia_email or datos.new_password) and not (
            datos.current_password and auth.verificar_contrasena(datos.current_password, usuario.hashed_password)):
        raise _error(400, "contrasena_actual_incorrecta", "La contraseña actual ingresada no es correcta.")
    if cambia_email:
        usuario.email = nuevo_email
    if datos.full_name is not None:
        usuario.full_name = datos.full_name.strip() or None
    if datos.new_password:
        usuario.hashed_password = auth.hash_contrasena(datos.new_password)
        await auth.revocar_sesiones_de(db, usuario.id, excepto=principal.sesion.id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _error(400, "email_en_uso", "Ese correo electrónico ya está en uso por otra cuenta.") from None
    await db.refresh(usuario)
    return usuario


@router.get("/usuarios", response_model=list[UsuarioResponse])
async def listar_usuarios(_: Administrador, db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Usuario).order_by(Usuario.id))).scalars().all()


@router.post("/usuarios", response_model=UsuarioResponse, status_code=201)
async def crear_usuario(datos: UsuarioCreadoPorAdmin, _: Administrador, db: AsyncSession = Depends(get_db)):
    if not auth.contrasena_valida(datos.password):
        raise _error(422, "contrasena_invalida", "La contraseña debe tener entre 10 caracteres y 72 bytes.")
    return await _crear(db, datos, datos.rol)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioResponse)
async def actualizar_usuario(usuario_id: int, datos: UsuarioAdminUpdate, principal: Administrador,
                             db: AsyncSession = Depends(get_db)):
    """Cambiar el rol o deshabilitar revoca todas las sesiones de esa cuenta."""
    if usuario_id == principal.sesion.usuario_id:
        raise _error(409, "no_modificable", "No puede cambiar su propio rol ni deshabilitar su propia cuenta.")
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise _error(404, "usuario_no_encontrado", "Usuario no encontrado.")
    if datos.rol is not None:
        usuario.rol = datos.rol
    if datos.is_active is not None:
        usuario.is_active = datos.is_active
    await auth.revocar_sesiones_de(db, usuario.id)
    await db.commit()
    await db.refresh(usuario)
    return usuario
