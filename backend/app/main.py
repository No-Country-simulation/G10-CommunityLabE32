import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers del Frontend (Ian) y Autenticación de Seguridad
from backend.app.routers import mensajes, curaduria, dashboard, auth
# Router de Procesamientos (Tareck)
from backend.app.api.routes.procesamientos import router as procesamientos_router

app = FastAPI(
    title="CommunityLab API",
    version="1.0.0",
    description="Motor backend para procesamiento, curaduría, distribución comunitaria y autenticación segura."
)

# La interfaz llega por el mismo origen (rewrites de Next.js en local, nginx en la VM), así que
# no hace falta CORS. CORS_ORIGENES (lista separada por comas) solo para un origen distinto explícito.
_origenes = [o.strip() for o in os.environ.get("CORS_ORIGENES", "").split(",") if o.strip()]
if _origenes:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origenes,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
    )

# Registrar todos los routers
app.include_router(mensajes.router)
app.include_router(curaduria.router)
app.include_router(dashboard.router)
app.include_router(procesamientos_router)
from backend.app.api.routes.trabajos import router as trabajos_router
app.include_router(trabajos_router)
from backend.app.api.routes.solicitudes import router as solicitudes_router
from backend.app.api.routes.banners import router as banners_router
app.include_router(solicitudes_router)
app.include_router(banners_router)
from backend.app.api.routes.discord_historico import router as discord_historico_router
app.include_router(discord_historico_router)

# Registrar el router de autenticación y seguridad JWT
app.include_router(auth.router)

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "mensaje": "El motor Backend de CommunityLab está operativo y seguro. 🚀"
    }

@app.get("/health", tags=["Health Check"])
def health_check():
    return {
        "estado": "ok",
        "servicio": "communitylab-api"
    }