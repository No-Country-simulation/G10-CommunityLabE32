"""Importación histórica de mensajes de Discord por canal y rango de fechas.

Separada del lector en vivo: no usa su bandeja, no activa el bot ni alertas, no cierra períodos,
no publica y no llama a Gemini. Fases:
  1. verificar y previsualizar (servicio.py),
  2. importar el historial en un trabajo persistente (importador.py + runner.py),
  3. procesamiento con IA: acción posterior y explícita, no implementada aquí (ver la documentación).
"""
