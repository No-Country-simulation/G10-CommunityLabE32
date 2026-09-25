from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/procesamientos",
    tags=["Procesamientos"],
)


@router.post("")
def crear_procesamiento():
    return {
        "procesamiento_id": "mock-001",
        "estado": "recibido",
        "mensaje": "Procesamiento recibido correctamente"
    }