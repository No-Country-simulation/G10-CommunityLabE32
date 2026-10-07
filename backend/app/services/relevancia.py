import re
from backend.app.schemas.procesamientos import PuntajeRelevancia, Interaccion, InteraccionEvaluada

def evaluar_texto(texto: str) -> PuntajeRelevancia:
    """
    Evalúa la relevancia de un texto basándose en heurísticas (palabras clave) para 4 criterios:
    - hito logrado
    - emoción
    - utilidad
    - recurrencia
    """
    texto_lower = texto.lower()

    # 1. Hito logrado
    keywords_hito = [r"conseguí", r"logré", r"primer empleo", r"aprobé", r"certificación", r"terminé", r"portafolio", r"contratado", r"oferta"]
    hito_score = sum(3 for kw in keywords_hito if re.search(kw, texto_lower))
    hito_score = min(hito_score, 10)

    # 2. Emoción
    keywords_emocion = [r"feliz", r"orgullos", r"emocionad", r"gracias", r"increíble", r"excelente", r"me encanta", r"❤️", r"🥳", r"🚀"]
    emocion_score = sum(2 for kw in keywords_emocion if re.search(kw, texto_lower))
    # Bonus por exclamaciones
    if "!" in texto:
        emocion_score += 2
    emocion_score = min(emocion_score, 10)

    # 3. Utilidad
    keywords_utilidad = [r"tutorial", r"guía", r"solución", r"paso a paso", r"resolví", r"cómo hacer", r"consejo", r"tip", r"repo", r"github.com"]
    utilidad_score = sum(3 for kw in keywords_utilidad if re.search(kw, texto_lower))
    utilidad_score = min(utilidad_score, 10)

    # 4. Recurrencia (Dudas comunes o preguntas frecuentes)
    keywords_recurrencia = [r"cómo", r"duda", r"pregunta", r"error", r"falla", r"ayuda", r"alguien sabe", r"no me funciona", r"issue"]
    recurrencia_score = sum(2 for kw in keywords_recurrencia if re.search(kw, texto_lower))
    if "?" in texto or "¿" in texto:
        recurrencia_score += 3
    recurrencia_score = min(recurrencia_score, 10)

    # Total
    total = hito_score + emocion_score + utilidad_score + recurrencia_score

    # Umbral para destacar
    es_destacado = total >= 12

    return PuntajeRelevancia(
        hito_logrado=hito_score,
        emocion=emocion_score,
        utilidad=utilidad_score,
        recurrencia=recurrencia_score,
        total=total,
        es_destacado=es_destacado
    )

def evaluar_interaccion(interaccion: Interaccion) -> InteraccionEvaluada:
    relevancia = evaluar_texto(interaccion.texto)
    return InteraccionEvaluada(
        interaccion=interaccion,
        relevancia=relevancia
    )
