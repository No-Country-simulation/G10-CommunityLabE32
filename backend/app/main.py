from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Importar los routers de la carpeta app/routers
from app.routers import mensajes, curaduria, dashboard

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

# 2. Registrar los routers
app.include_router(mensajes.router)
app.include_router(curaduria.router)
app.include_router(dashboard.router)

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "mensaje": "El motor Backend de CommunityLab está operativo y seguro. 🚀"
    }