from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers del Frontend (Ian)
from backend.app.routers import mensajes, curaduria, dashboard
# Router de Procesamientos (Tareck)
from backend.app.api.routes.procesamientos import router as procesamientos_router

app = FastAPI(
    title="CommunityLab API",
    version="1.0.0",
    description="Motor backend para procesamiento, curaduría y distribución comunitaria."
)

# Configuración CORS para conectar con Next.js (puerto 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar todos los routers (Unión de Ian y Tareck)
app.include_router(mensajes.router)
app.include_router(curaduria.router)
app.include_router(dashboard.router)
app.include_router(procesamientos_router)

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