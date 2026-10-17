# Métricas del panel

`GET /api/dashboard/kpis` (`backend/app/routers/dashboard.py`). Parámetros opcionales `origen` y
`periodo` (valores de `origen_comunidad` y `periodo_referencia` de los lotes); sin ellos, el ámbito
es toda la base, incluidos históricos y pruebas. `GET /api/dashboard/ambitos` lista los pares
origen/período con lotes registrados, para el selector del panel.

| Campo | Significado | No significa |
|---|---|---|
| `total_mensajes` | Mensajes guardados del ámbito (deduplicados por `id_mensaje`). | Mensajes procesados con éxito: se guardan al encolar, aunque el trabajo falle después. |
| `mensajes_por_tipo` | Conteo por `tipo` (`sin_clasificar` si el lote no lo trajo). | Clasificación de la IA: el análisis del grafo no se escribe en `mensajes`. |
| `distribucion_sentimiento` | Solo mensajes con `sentimiento_ref` explícito. | Que el resto sea neutral. |
| `sentimiento.estado` | `sin_datos` (ninguno clasificado), `parcial` o `completo`. | — |
| `activos_generados` | Total de contenidos en curaduría (todos los estados). | — |
| `activos_por_estado` | Conteo por estado de curaduría. | — |
| `borradores_pendientes` | Estados `generado` + `revisado` (pendientes de decisión humana). | — |
| `activos_aprobados` | Estado `aprobado`. | Publicados. |
| `publicados` / `publicacion_externa` | `null` / `no_implementada`: no hay publicación externa. | — |
| `alertas_internas` | Mensajes distintos con alerta interna en resultados de trabajos terminados. | Coincidencias de palabras como "error" o "bloqueo" en el texto. |
| `alertas_registradas` | Alertas en resultados; un mismo mensaje cuenta una vez por lote distinto que lo incluyó. | — |
| `trabajos_por_estado` | Trabajos del ámbito por estado. | — |

## Ámbito y doble conteo

`mensajes` y `activos` no guardan su origen. El ámbito se reconstruye desde `trabajos_worker`
(`backend/app/services/ambito.py`): mensajes = IDs de las interacciones de los lotes del ámbito;
activos = IDs que el worker asigna (`act-` + sha256(id_trabajo + id_activo)[:40]); alertas = las de
los resultados de lotes terminados. Un reenvío idéntico reutiliza el trabajo y no duplica nada; el
mismo contenido con otro período es otro lote y genera contenidos propios (por diseño).

El cálculo lee todos los trabajos (adecuado para cientos de lotes). Con más volumen convendría
guardar el origen en las tablas. No se borran datos para "limpiar" métricas: se filtra por ámbito.
