from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import mensajes

# Inicialización profesional de la App
app = FastAPI(
    title="CommunityLab API Enterprise",
    description="API robusta para el procesamiento de interacciones y recursos híbridos",
    version="1.0.0"
)

# Configuración estricta de CORS para seguridad
# Esto permite que Next.js consuma tu API sin ser bloqueado por el navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, esto se cambia a ["https://tudominio.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Ensamblaje de Routers modulares
app.include_router(mensajes.router)

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "mensaje": "El motor Backend de CommunityLab está operativo y seguro. 🚀"
    }