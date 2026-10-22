# Gemini en el grafo y el worker

El modo productivo del worker es `WORKER_MODE=gemini`. Los cinco componentes del grafo
son reales y usan Gemini: análisis y puntuación (`pipelines/communitylab/analisis_gemini.py`)
y los generadores de Fabián (`pipelines/communitylab/generadores/`). OpenRouter ya no se
utiliza. `WORKER_MODE=simulado` sigue disponible y marca todo como simulado.

## Configuración (solo en `.env` privado)

| Variable | Defecto | Uso |
|---|---|---|
| `GEMINI_API_KEY` | — (obligatoria) | Clave del proyecto. Nunca en Git ni en logs. |
| `GEMINI_MODELOS` | — (obligatoria) | Lista ordenada `rapido,escalado`. Verificar disponibilidad antes de usarla. |
| `GEMINI_TIMEOUT_PETICION` | 30 | Segundos máximos por llamada (además, nunca más que lo que queda del trabajo). |
| `GEMINI_PRESUPUESTO_SEGUNDOS` | 100 | Tiempo total del trabajo; debe ser ≤ `WORKER_TIMEOUT` − 10. |
| `GEMINI_MAX_LLAMADAS` | 16 | Llamadas totales por trabajo, incluidos reintentos y escalamientos. |
| `GEMINI_MAX_TOKENS_SALIDA` | 2048 | `maxOutputTokens` por llamada. |
| `GEMINI_MAX_TOKENS_TRABAJO` | 40000 | Tokens de salida + razonamiento por trabajo. |
| `GEMINI_REINTENTOS` | 1 | Reintentos por llamada ante 429 por ritmo o fallo transitorio (0–3). |
| `GEMINI_ESPERA_MAXIMA` | 10 | Espera máxima aceptada (Retry-After/backoff). |
| `GEMINI_TAMANO_BLOQUE` | 40 | Mensajes por llamada de análisis/puntuación. |
| `GEMINI_NIVEL_RAZONAMIENTO` | (no se envía) | `MINIMAL`/`LOW`/`MEDIUM`/`HIGH` (modelos Gemini 3). |
| `GEMINI_TEMPERATURA` | (no se envía) | 0–2. |

El worker valida la configuración al arrancar y se detiene sin mostrar valores si falta
algo o si el presupuesto no cabe en `WORKER_TIMEOUT`.

**Valores del worker en `docker-compose.yml` y en la VM** (los de la tabla son los del código):
`WORKER_TIMEOUT=300`, `GEMINI_PRESUPUESTO_SEGUNDOS=240`, `GEMINI_MAX_LLAMADAS=24`, `GEMINI_REINTENTOS=2`
y `GEMINI_ESPERA_MAXIMA=60`. Con la cuenta gratuita (unas 15 llamadas por minuto), una semana de la demo
usa 16-19 llamadas en unos 30 s: con los valores del código el 429 por ritmo pedía esperar más de 10 s y el
lote fallaba entero (`ia_cuota`), o se quedaba sin llamadas para los borradores (`ia_presupuesto`). Con estos
valores el lote espera lo que indica Gemini y termina; tarda 1-2 minutos más. La API («Generar post») usa
sus propios valores por defecto (una sola llamada).

## Política

| Situación | Acción | Código del trabajo |
|---|---|---|
| Respuesta válida | Se usa | — |
| JSON inválido, `MAX_TOKENS`, vacía, sin candidato, otra terminación, validador local falla | Escala al siguiente modelo de `GEMINI_MODELOS`; si no quedan, falla | `ia_respuesta_invalida` |
| 400/401/403/404 (clave, permisos, modelo, petición) | Falla sin reintentar ni escalar | `ia_configuracion` |
| 429 con cuota diaria (`quotaId` *PerDay*) o 402 | Falla sin reintentar ni escalar | `ia_cuota` |
| 429 por ritmo | Espera `Retry-After`/`RetryInfo` (o backoff 1, 2… s) si cabe en `GEMINI_ESPERA_MAXIMA` y en el presupuesto; mismo modelo | `ia_cuota` si persiste |
| 408/5xx, timeout, conexión | Reintento acotado en el mismo modelo | `ia_transitorio` |
| `SAFETY`, `promptFeedback.blockReason`, etc. | Falla sin escalar | `ia_bloqueado` |
| Tiempo, llamadas o tokens del trabajo agotados | Corta antes de llamar | `ia_presupuesto` |

### Límite de llamadas en lotes grandes (conocido, sin resolver)

El presupuesto es por trabajo (`GEMINI_MAX_LLAMADAS`: 16 en el código, 24 en la VM). Con la configuración de la VM, los bloques son de
22 (`analizar`) y 40 (`puntuar`). Un lote de N mensajes usa como mínimo `ceil(N/22) + ceil(N/40)` llamadas,
más 1 por cada post de logro, 1 por cada FAQ de duda recurrente y 1 de highlights al cierre (si hay mensajes
relevantes). Los generadores no tienen tope y el cierre vuelve a analizar los mensajes `previo`.

Ejemplos de cierre (calculados y cubiertos por `test_fidelidad_y_diagnostico.PruebasPresupuestoCierre`):
- 150 mensajes con 4 logros usan exactamente 16 llamadas;
- con 5 logros, el trabajo termina en `ia_presupuesto`;
- 220 mensajes sin nada relevante caben, pero 221 ya no.

Si no cabe, el trabajo falla **entero** (sin borradores parciales ni descartes silenciosos). Resolverlo cambia
el comportamiento del producto (reutilizar análisis previos, limitar generaciones o escalar el presupuesto) y
queda como propuesta separada.

- Un solo nivel de reintentos: no se usa el SDK `google-genai` porque reintenta por su cuenta.
  El worker tampoco reintenta un trabajo fallido (queda en `error` para revisión).
- Salida estructurada: `responseMimeType: application/json` + `responseJsonSchema`, y
  validación local estricta (la respuesta HTTP 200 no se considera válida por sí sola).
- Terminación: solo `finishReason=STOP` es válida; se ignoran partes `thought`.
- Fuentes: los generadores devuelven exactamente las fuentes que eligió el router; el
  modelo nunca las decide. Un fallo en cualquier nodo deja el lote sin activos ni alertas.
- Activos en borrador (`generado` en la base) para curaduría humana.
- Métricas en el log `communitylab.gemini`: tarea, modelo, intento, resultado, código HTTP,
  latencia, tokens y llamadas. Sin claves, textos ni mensajes del proveedor.

## Diagnóstico de rechazos (HTTP 4xx)

Un 400/401/403/404 no se escala ni se reintenta (no se oculta un error de contrato).
`pipelines/communitylab/diagnostico.py` arma el diagnóstico **sin copiar texto del proveedor**:
`error.message` y cualquier texto libre se descartan, porque el proveedor puede reflejar datos
de la petición con o sin comillas. Solo se conservan:

| Campo | Origen |
|---|---|
| `http` | Estado HTTP (entero). |
| `categoria` | Interna, derivada del HTTP: `peticion_rechazada`, `credencial`, `permiso`, `modelo_o_ruta` u `otro`. |
| `estado_proveedor` | `error.status` solo si está en el catálogo (`INVALID_ARGUMENT`, `FAILED_PRECONDITION`…); si no, `OTRO`. |
| `razon` | `ErrorInfo.reason` solo si está en el catálogo (`API_KEY_INVALID`, `SERVICE_DISABLED`…); si no, `otra`. |
| `campos` | Rutas de `fieldViolations` normalizadas contra el vocabulario de la petición generateContent; los segmentos desconocidos pasan a `*` (p. ej. `contents[].parts[].*`). |
| `peticion` | Métricas numéricas: `bytes_peticion`, `bytes_esquema`, `valores_enum`, `items_esperados`. |
| `detalle` | Texto generado internamente desde categoría y estado (nunca del proveedor). |

El diagnóstico se registra en el log `gemini diagnostico` y se propaga al resultado del grafo, a
`resultado.diagnostico` del trabajo con error y a `GET /api/v1/trabajos/{id}`. Cada capa
(grafo, worker, persistencia y API) vuelve a aplicar `normalizar_diagnostico`, así que solo
viajan valores del catálogo aunque un componente o una fila antigua traigan otra cosa. Si hiciera
falta el mensaje original del proveedor para investigar, debe obtenerse por un canal restringido
aparte, nunca por la API ni los logs generales.

El HTTP 400 observado el 17/10 con un lote histórico de 423 interacciones ocurrió en la primera
llamada de análisis (bloque de 40, esquema con enum de 40 IDs y `minItems`/`maxItems` 40). Su causa
**no está confirmada**: el diagnóstico estructurado permite contrastar las hipótesis (complejidad
del esquema, contenido del bloque) en el próximo intento.

## Pruebas

- Sin red ni claves (CI): `pipelines/communitylab/tests/test_gemini.py`,
  `test_generadores.py`, `test_componentes_gemini.py` y `worker/tests/test_ia_contract.py`
  (incluye PostgreSQL real desechable en el job `postgres`). El doble de transporte está en
  `pipelines/communitylab/gemini_falso.py`.
- Real y opcional (consume cuota): `COMMUNITYLAB_GEMINI_REAL=1 python tools/probar_gemini_real.py`.
  Verifica primero que los modelos de `GEMINI_MODELOS` existan en el proyecto.

## Pendiente fuera de este cambio

- Servicios permanentes de Discord, operación de la VM y redespliegue (paso 2).
- El módulo legacy `community_processor:procesar` del bot conserva su proveedor OpenRouter;
  el bot productivo usa `community_processor.integrated:procesar` (Gemini).
