from fastapi import FastAPI
from backend.app.api.routes.procesamientos import router as procesamientos_router

app = FastAPI(
    title="G10 CommunityLab API",
    version="1.0.0",
    description="API del proyecto G10 CommunityLab E32",
)

@app.get("/health")
def health_check():
    return {
        "estado": "ok",
        "servicio": "communitylab-api"
    }

app.include_router(procesamientos_router)