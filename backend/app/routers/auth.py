from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.usuario import Usuario
from backend.app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioResponse, Token
from backend.app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

@router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def register(usuario_in: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.email == usuario_in.email))
    db_user = result.scalar_one_or_none()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado."
        )
    
    hashed_pass = get_password_hash(usuario_in.password)
    nuevo_usuario = Usuario(
        email=usuario_in.email,
        hashed_password=hashed_pass,
        full_name=usuario_in.full_name
    )
    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)
    return nuevo_usuario

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.email == form_data.username))
    usuario = result.scalar_one_or_none()
    if not usuario or not verify_password(form_data.password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas (correo o contraseña inválidos).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": usuario.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UsuarioResponse)
async def obtener_perfil_actual(current_user: Usuario = Depends(get_current_user)):
    """Devuelve los datos del usuario autenticado mediante el token JWT."""
    return current_user

@router.patch("/me", response_model=UsuarioResponse)
async def actualizar_perfil_actual(
    datos: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permite al usuario autenticado actualizar su nombre, correo o contraseña."""
    if datos.email and datos.email != current_user.email:
        existe = await db.execute(select(Usuario).where(Usuario.email == datos.email))
        if existe.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ese correo electrónico ya está en uso por otra cuenta."
            )
        current_user.email = datos.email

    if datos.full_name is not None:
        current_user.full_name = datos.full_name.strip()

    if datos.new_password:
        if not datos.current_password or not verify_password(datos.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual ingresada no es correcta."
            )
        current_user.hashed_password = get_password_hash(datos.new_password)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user