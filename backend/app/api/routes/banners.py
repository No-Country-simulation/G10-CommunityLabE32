"""Banners de activos aprobados: generar (acción separada), ver y revisar. Nunca publica.

- Solo se genera desde un activo en estado «aprobado», para su versión de texto vigente.
- Uno por (activo, versión): repetir la acción devuelve el mismo banner; uno en error o
  abandonado en «generando» (reinicio a mitad) se puede volver a intentar.
- Si el texto cambia, el activo vuelve a «revisado» (ver curaduria.py) y el banner queda
  desactualizado: no se puede aprobar y la interfaz lo marca.
- Aprobar el banner solo registra la revisión; no hay publicación automática.
"""
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.acceso import requiere_operador
from backend.app.core.dependencias import get_db
from backend.app.models.activo import Activo
from backend.app.services import banners as plantilla

router = APIRouter(tags=["Banners"])
ABANDONO_SEGUNDOS = 120
CABECERAS_SVG = {
    # El SVG se sirve como imagen aislada: sin scripts, sin recursos externos, sin sniffing.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, max-age=60",
}


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["aprobado", "rechazado"]
    comentario: str | None = Field(default=None, max_length=500)


def id_banner(id_activo, version):
    return "ban-" + sha256(f"{id_activo}:{version}".encode()).hexdigest()[:32]


async def _activo(db, id_activo):
    activo = (await db.execute(select(Activo).where(Activo.id_activo == id_activo))).scalar_one_or_none()
    if activo is None:
        raise HTTPException(404, "Activo no encontrado.")
    return activo


def _vista(fila, activo):
    # Un banner de otra plantilla (diseño anterior) queda desactualizado: «Generar» lo vuelve a renderizar.
    vigente = (activo is not None and activo.estado == "aprobado" and activo.version == fila["version_texto"]
               and plantilla.huella_texto(activo.copy) == fila["huella_texto"]
               and fila["plantilla"] == plantilla.PLANTILLA)
    return {"id": fila["id"], "id_activo": fila["id_activo"], "version_texto": fila["version_texto"],
            "estado": fila["estado"], "revision": fila["revision"], "desactualizado": not vigente,
            "proveedor": fila["proveedor"], "plantilla": fila["plantilla"],
            "error_codigo": fila["error_codigo"], "intentos": fila["intentos"], "comentario": fila["comentario"],
            "creado": fila["creado"], "actualizado": fila["actualizado"],
            "url": f"/api/banners/{fila['id']}.svg" if fila["estado"] == "generado" else None}


COLUMNAS = ("id, id_activo, version_texto, huella_texto, estado, revision, proveedor, plantilla, "
            "error_codigo, intentos, comentario, creado, actualizado")


@router.get("/api/curaduria/activos/{id_activo}/banners", dependencies=[Depends(requiere_operador)])
async def listar_banners(id_activo: str, db: AsyncSession = Depends(get_db)):
    activo = await _activo(db, id_activo)
    filas = (await db.execute(text(f"SELECT {COLUMNAS} FROM banners WHERE id_activo=:a "
                                   "ORDER BY version_texto DESC"), {"a": id_activo})).mappings().all()
    banners = [_vista(f, activo) for f in filas]
    return {"id_activo": id_activo, "estado_activo": activo.estado, "version_texto": activo.version,
            "puede_generar": activo.estado == "aprobado",
            "proveedor": plantilla.PROVEEDOR, "generacion_ia": False,
            "banners": banners,
            "vigente": next((b for b in banners if not b["desactualizado"]), None)}


@router.post("/api/curaduria/activos/{id_activo}/banners", status_code=201,
             dependencies=[Depends(requiere_operador)])
async def generar_banner(id_activo: str, response: Response, db: AsyncSession = Depends(get_db)):
    activo = await _activo(db, id_activo)
    if activo.estado != "aprobado":
        raise HTTPException(409, {"codigo": "texto_no_aprobado",
                                  "mensaje": "Solo se genera el banner de un texto aprobado."})
    version, copy, formato = activo.version, activo.copy, activo.formato
    identificador = id_banner(id_activo, version)
    await db.execute(text("""INSERT INTO banners (id, id_activo, version_texto, huella_texto, proveedor, plantilla)
        VALUES (:id, :a, :v, :h, :p, :t) ON CONFLICT (id_activo, version_texto) DO NOTHING"""),
        {"id": identificador, "a": id_activo, "v": version, "h": plantilla.huella_texto(copy),
         "p": plantilla.PROVEEDOR, "t": plantilla.PLANTILLA})
    fila = (await db.execute(text(f"""SELECT {COLUMNAS},
        actualizado < clock_timestamp() - make_interval(secs => :s) AS abandonado
        FROM banners WHERE id_activo=:a AND version_texto=:v FOR UPDATE"""),
        {"a": id_activo, "v": version, "s": ABANDONO_SEGUNDOS})).mappings().first()
    if fila["estado"] == "generado" and fila["plantilla"] == plantilla.PLANTILLA:
        await db.commit()
        response.status_code = 200
        return {**_vista(fila, activo), "reutilizado": True}
    if fila["estado"] == "generando" and not fila["abandonado"]:
        await db.commit()
        raise HTTPException(409, {"codigo": "generacion_en_curso", "mensaje": "El banner ya se está generando."})
    await db.execute(text("""UPDATE banners SET estado='generando', intentos=intentos+1, error_codigo=NULL,
        proveedor=:p, plantilla=:t, actualizado=clock_timestamp() WHERE id=:id"""),
        {"id": fila["id"], "p": plantilla.PROVEEDOR, "t": plantilla.PLANTILLA})
    await db.commit()  # Estado visible antes de renderizar: un reinicio deja rastro recuperable.
    try:
        svg, estado, error = plantilla.renderizar(formato, copy), "generado", None
    except plantilla.BannerNoGenerable:
        svg, estado, error = None, "error", "texto_insuficiente"
    except Exception:
        svg, estado, error = None, "error", "fallo_render"
    await db.execute(text("""UPDATE banners SET estado=:e, svg=:svg, error_codigo=:err, revision='pendiente',
        actualizado=clock_timestamp() WHERE id=:id"""), {"e": estado, "svg": svg, "err": error, "id": fila["id"]})
    await db.commit()
    fila = (await db.execute(text(f"SELECT {COLUMNAS} FROM banners WHERE id=:id"),
                             {"id": fila["id"]})).mappings().first()
    return {**_vista(fila, activo), "reutilizado": False}


# Borradores sin publicar: solo operadores (la cookie de sesión viaja con <img> del mismo sitio).
@router.get("/api/banners/{identificador}.svg", dependencies=[Depends(requiere_operador)])
async def ver_banner(identificador: str, db: AsyncSession = Depends(get_db)):
    svg = (await db.execute(text("SELECT svg FROM banners WHERE id=:id AND estado='generado'"),
                            {"id": identificador})).scalar()
    if svg is None:
        raise HTTPException(404, "Banner no disponible")
    return Response(svg, media_type="image/svg+xml", headers=CABECERAS_SVG)


@router.post("/api/banners/{identificador}/revision", dependencies=[Depends(requiere_operador)])
async def revisar_banner(identificador: str, revision: Revision, db: AsyncSession = Depends(get_db)):
    fila = (await db.execute(text(f"SELECT {COLUMNAS} FROM banners WHERE id=:id FOR UPDATE"),
                             {"id": identificador})).mappings().first()
    if fila is None:
        raise HTTPException(404, "Banner no encontrado")
    activo = await _activo(db, fila["id_activo"])
    vista = _vista(fila, activo)
    if fila["estado"] != "generado":
        raise HTTPException(409, {"codigo": "banner_no_generado", "mensaje": "El banner aún no está generado."})
    if revision.decision == "aprobado" and vista["desactualizado"]:
        raise HTTPException(409, {"codigo": "banner_desactualizado",
                                  "mensaje": "El texto cambió o ya no está aprobado; genere un banner nuevo."})
    await db.execute(text("""UPDATE banners SET revision=:r, comentario=:c, actualizado=clock_timestamp()
        WHERE id=:id"""), {"r": revision.decision, "c": revision.comentario, "id": identificador})
    await db.commit()
    fila = (await db.execute(text(f"SELECT {COLUMNAS} FROM banners WHERE id=:id"),
                             {"id": identificador})).mappings().first()
    # Aprobado no es publicado: la publicación sigue siendo una acción externa y manual.
    return {**_vista(fila, activo), "publicado": False}
