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

    # 2. Emoción (positiva o negativa)
    keywords_emocion_positiva = [r"feliz", r"orgullos", r"emocionad", r"gracias", r"increíble", r"excelente", r"me encanta", r"❤️", r"🥳", r"🚀"]
    keywords_emocion_negativa = [r"frustrado", r"harto", r"molesto", r"enojado", r"\bmal\b", r"decepcionado", r"triste", r"rendirme"]
    
    emocion_pos = sum(2 for kw in keywords_emocion_positiva if re.search(kw, texto_lower))
    emocion_neg = sum(2 for kw in keywords_emocion_negativa if re.search(kw, texto_lower))
    
    if "!" in texto and emocion_pos > 0:
        emocion_pos += 2
        
    # Usaremos emoción_pos como la emoción general (o si es mayor a la negativa)
    # y si la negativa es mayor, la ponemos como número negativo.
    if emocion_neg > emocion_pos:
        emocion_score = -min(emocion_neg, 10)
    else:
        emocion_score = min(emocion_pos, 10)

    # 3. Utilidad
    keywords_utilidad = [r"tutorial", r"guía", r"solución", r"paso a paso", r"resolví", r"cómo hacer", r"consejo", r"tip", r"repo", r"github.com"]
    utilidad_score = sum(3 for kw in keywords_utilidad if re.search(kw, texto_lower))
    utilidad_score = min(utilidad_score, 10)

    # 4. Recurrencia (Dudas comunes o preguntas frecuentes)
    keywords_recurrencia = [r"cómo", r"duda", r"pregunta", r"error", r"falla", r"ayuda", r"alguien sabe", r"no me funciona", r"issue"]
    recurrencia_score = sum(2 for kw in keywords_recurrencia if re.search(kw, texto_lower))
    
    # Agregar penalización/bloqueo a recurrencia si es muy grave
    keywords_bloqueo = [r"días intentando", r"no es clara", r"estancado", r"bloqueado", r"imposible", r"no puedo avanzar"]
    bloqueo_score = sum(5 for kw in keywords_bloqueo if re.search(kw, texto_lower))
    
    if "?" in texto or "¿" in texto:
        recurrencia_score += 3
        
    # Si hay un bloqueo, sumamos mucho a la recurrencia para que lo alerte
    recurrencia_score += bloqueo_score
    recurrencia_score = min(recurrencia_score, 10)

    # Total (usamos valor absoluto de emoción para el puntaje)
    total = hito_score + abs(emocion_score) + utilidad_score + recurrencia_score

    # Umbral para destacar
    es_destacado = total >= 8

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
