"""Paquete de distribución con la forma del enunciado de la hackathon (proyecto.pdf, «Funcionalidades
obligatorias (MVP)»): resumen de la comunidad, activos generados y almacenamiento en OCI.

Se arma a partir del resultado del grafo que guarda el worker. Lo usan el endpoint síncrono
`POST /api/v1/procesar` (respuesta) y el worker (objeto JSON que sube a OCI Object Storage).
"""
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import re

ETIQUETAS_SENTIMIENTO = {"positivo": "Positivo", "negativo": "Negativo", "neutral": "Neutral",
                         "indeterminado": "Indeterminado"}
TITULOS = {"post_linkedin_x": "Logro de la comunidad", "community_highlights": "Resumen de la comunidad",
           "faq_tip_tecnico": "Preguntas de la comunidad"}
SEMANA_ISO = re.compile(r"^(\d{4})-W(\d{2})$")


def sentimiento_predominante(sentimientos):
    """«Altamente positivo» si un valor reúne al menos el 70 % de los mensajes analizados; si no,
    el valor más frecuente. Sin mensajes analizados: «Sin datos»."""
    conteo = Counter(v for v in (sentimientos or {}).values() if v in ETIQUETAS_SENTIMIENTO)
    if not conteo:
        return "Sin datos"
    valor, cantidad = max(conteo.items(), key=lambda x: (x[1], x[0] == "positivo"))
    etiqueta = ETIQUETAS_SENTIMIENTO[valor]
    if valor in ("positivo", "negativo") and cantidad / sum(conteo.values()) >= 0.7:
        return "Altamente " + etiqueta.lower()
    return etiqueta


def temas_principales(clasificaciones, limite=5):
    conteo = Counter(c.get("tema") for c in (clasificaciones or {}).values() if isinstance(c, dict) and c.get("tema"))
    return [tema for tema, _ in sorted(conteo.items(), key=lambda x: (-x[1], x[0]))[:limite]]


def _activo(a):
    return {"titulo": TITULOS.get(a.get("formato"), "Contenido de la comunidad"), "copy": a.get("copy"),
            "fuentes": list(a.get("fuentes") or []), "id_activo_curaduria": a.get("id_activo_curaduria"),
            "advertencias_fidelidad": list(a.get("advertencias_fidelidad") or []), "estado": "borrador"}


def paquete_distribucion(resultado, *, procesamiento_id, total_interacciones):
    """Resumen + activos (borradores pendientes de revisión humana) + almacenamiento OCI."""
    activos = resultado.get("activos_distribucion_generados") or []
    por_formato = {f: [_activo(a) for a in activos if a.get("formato") == f] for f in TITULOS}
    sentimientos = resultado.get("sentimientos") or {}
    return {
        "status": "exito",
        "procesamiento_id": procesamiento_id,
        "origen_comunidad": resultado.get("origen_comunidad"),
        "periodo_referencia": resultado.get("periodo_referencia"),
        "resumen_comunidad": {
            "total_interacciones_procesadas": total_interacciones,
            "sentimiento_predominante": sentimiento_predominante(sentimientos),
            "distribucion_sentimiento": dict(Counter(sentimientos.values())),
            "temas_principales": temas_principales(resultado.get("clasificaciones")),
            "alertas_internas": len(resultado.get("alertas_internas") or []),
        },
        "activos_distribucion_generados": {
            "post_linkedin": por_formato["post_linkedin_x"],
            "destaque_newsletter_semanal": por_formato["community_highlights"],
            "sugerencia_contenido_faq": por_formato["faq_tip_tecnico"],
        },
        # Ningún activo se publica solo: quedan como borradores en Curaduría para revisión humana.
        "revision_humana": "pendiente_en_curaduria",
        "almacenamiento_oci": resultado.get("almacenamiento"),
    }


def ruta_paquete(periodo, procesamiento_id):
    """Objeto en el bucket: activos/<período>/<procesamiento>/paquete-distribucion.json."""
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "-", str(periodo or "sin-periodo")).strip("-") or "sin-periodo"
    return f"activos/{limpio}/{procesamiento_id}/paquete-distribucion.json"


def periodo_actual(hoy=None):
    anio, semana, _ = (hoy or datetime.now(timezone.utc).date()).isocalendar()
    return f"{anio}-W{semana:02d}"


def fecha_por_defecto(periodo, hoy=None):
    """Fecha estable para interacciones sin fecha: el lunes 12:00 UTC de la semana ISO del período, o
    hoy 12:00 UTC. Así reenviar el mismo lote produce el mismo contenido y no se duplica."""
    m = SEMANA_ISO.match(str(periodo or ""))
    if m:
        lunes = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    else:
        lunes = hoy or datetime.now(timezone.utc).date()
    return datetime(lunes.year, lunes.month, lunes.day, 12, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def id_por_defecto(origen, periodo, indice, autor, canal, texto):
    """ID estable para interacciones sin ID: el mismo lote reenviado conserva sus IDs."""
    base = "\x1f".join(str(x) for x in (origen, periodo, indice, autor, canal, texto))
    return "api-" + sha256(base.encode("utf-8")).hexdigest()[:20]


__all__ = ["paquete_distribucion", "ruta_paquete", "periodo_actual", "fecha_por_defecto", "id_por_defecto",
           "sentimiento_predominante", "temas_principales"]
