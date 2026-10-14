# Clasificador local de Fabián

Aporte original del PR25: sanitización, TF-IDF/embeddings, sentimiento, umbrales,
contexto por servidor/canal/autor y herramientas de calibración. La integración
corregida con el transporte se documenta en ../../../processor/README.md.

## Cambios de contrato de esta entrega

- Logros y mensajes sin señal no producen respuesta; tema general no vacío.
- Dudas/bloqueos requieren un generador en la API síncrona. Sin él se lanza un
  error explícito. Los fallos externos propagan un código genérico, sin secretos.
- No se publican excepciones como alertas operativas de un usuario.
- Revisión pendiente se señala con ReviewRequired, persistida como needs_review
  por el transporte. No se inventa una decisión válida con respuesta vacía.
- Se valida la salida con el mismo validate_decision del bot. Se rechaza texto
  excesivo en unidades UTF-16; no se trunca silenciosamente una respuesta o código.
- Los logs de decisión no incluyen texto original ni excepciones del proveedor.

## Entrada recomendada para Discord

`community_processor.integrated:procesar` es async, recibe discord-source-v1
estricto y devuelve discord-decision-v1 validado. Usa el análisis local sin memoria
conversacional como hipótesis; Gemini confirma/corrige la clasificación y redacta
el texto. Conserva señales combinadas y la prioridad de bloqueo. Ver README del
procesador para configuración y pruebas.

La API de clasificación/calibración local permanece disponible. Para usar
clasificar/clasificar_payload como productor de decisiones, aportar GeneradorIA
para dudas/bloqueos y manejar ReviewRequired. Para obtener solamente diagnósticos,
usar preparar_lote y decidir; no llamar a generación. Sus esquemas internos
aceptan más entradas que la frontera estricta del adaptador de Discord.

## Verificación

La suite test_contrato_io se ejecuta ahora desde el validador integrado, junto
con pruebas de integración reales del contrato de transporte. Usa forzar_fallback
sin red y generador ficticio. Las métricas de reporte_calibracion.json son evidencia
histórica del autor sobre otro modo de ejecución: no acreditan el comportamiento
de Gemini ni deben interpretarse como precisión de esta integración.
