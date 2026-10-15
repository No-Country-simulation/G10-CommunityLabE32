"""Generadores editoriales con Gemini (aporte de Fabián) integrados al grafo.

Cada generador recibe la petición que arma el grafo y un ClienteGemini, y devuelve
{'copy', 'fuentes'} con exactamente las fuentes recibidas. Los activos quedan en
borrador para curaduría: este paquete no publica nada.
"""
from .faq_generador import generar_faq
from .highlights_generador import generar_highlights
from .post_generador import generar_post

__all__ = ["generar_post", "generar_faq", "generar_highlights"]
