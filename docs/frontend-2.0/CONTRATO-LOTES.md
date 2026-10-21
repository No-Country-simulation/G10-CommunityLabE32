# Origen de los lotes en el Resumen

El selector muestra Todos los lotes y agrupa los registros por fuente_ingesta.

GET /api/dashboard/ambitos debe incluir fuente_ingesta en cada elemento: discord o manual. Si no está disponible, se muestra Origen sin identificar. origen sigue representando la comunidad y periodo sigue representando el período del lote.

Para separar dos vías de carga de una misma comunidad y período, el backend debe devolver un elemento por combinación de origen, periodo y fuente_ingesta, y aceptar fuente_ingesta como filtro en /api/dashboard/kpis y /api/mensajes (y el endpoint de resumen de sentimiento). El frontend envía este filtro únicamente cuando el lote lo incluye.

La vista de referencia local no incluye lotes individuales. No se inventaron registros de Discord o de carga manual.
