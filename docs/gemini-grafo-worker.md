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
