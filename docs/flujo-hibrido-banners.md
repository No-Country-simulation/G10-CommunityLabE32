# Flujo híbrido, banners y análisis de sentimiento

## Flujo

1. Discord recibe mensajes. El lector los guarda en la bandeja y el bot sigue respondiendo dudas y
   enviando alertas internas de inmediato (sin cambios).
2. **Procesar pendientes** (Ingesta) crea una solicitud. El puente la toma en su ciclo normal, cada
   `PUENTE_INTERVALO` segundos, sin un programador adicional. Por cada período abierto envía un lote
   con `cierre_periodo=false`.
3. El worker genera borradores con fuentes y advertencias de fidelidad, que pasan a curaduría.
4. Una persona aprueba el texto (requiere token de operador).
5. Otra acción, **Generar banner**, crea la tarjeta de la versión aprobada.
6. El banner se revisa (aprobado o rechazado). Aprobar el banner **no publica**: la publicación
   sigue siendo una acción externa y manual.

## Lotes parciales (puente)

- **Qué mensajes entran.** Solo los nuevos del período, es decir, los que no se enviaron en un
  parcial anterior. El conjunto queda fijado al tomar la solicitud: lo que llega después espera a la
  siguiente.
- **Contexto.** El lote suma hasta `PUENTE_MAX_PREVIOS` mensajes (100 por defecto) ya procesados en
  parciales terminados, marcados con `previo=true`. Cuentan para la recurrencia de dudas (dos o más
  autores), pero no repiten alertas ni posts. Una FAQ solo se genera si el grupo incluye al menos
  una duda nueva.
- **Sin pendientes.** No se envía ningún trabajo y la solicitud termina como `sin_pendientes`, sin
  ninguna llamada a Gemini.
- **Idempotencia.** La planificación se guarda en SQLite antes del POST:
  - Las tablas `entregas_solicitud` y `solicitudes_parciales` relacionan solicitud → entrega →
    trabajo.
  - La clave es `discord-parcial-v1-sha256(ámbito parcial + solicitud + payload)`.
  - Tras un reinicio se reenvía la misma clave, que devuelve el mismo trabajo.
- **Fallos.** Un trabajo con `error` o un rechazo 4xx libera los mensajes, que vuelven a pendientes
  para la próxima solicitud. No hay reintento automático: evita consumir cuota en bucle.
- **Cierre semanal.**
  - Sigue siendo único por período.
  - Se aplaza mientras haya parciales del período en curso.
  - Marca `previo=true` lo ya procesado en parciales terminados: los highlights lo incluyen, pero
    no se duplican posts ni alertas.
- **Doble clic y concurrencia.**
  - La API: un índice único admite una sola solicitud abierta por origen, y crear otra devuelve la
    existente.
  - La interfaz: un `ref` evita el doble envío.
  - El puente: atiende una sola solicitud a la vez.
- **Recuperación.** Si el puente cae después de tomar una solicitud, la reserva vence a los 10
  minutos y la API vuelve a ofrecer el mismo id. Ese id se planifica una sola vez.
- **Trazabilidad.** El recorrido es mensaje → entrega (SQLite) → trabajo (`trabajos_worker`) →
  activo (`act-…` derivado del trabajo). La solicitud guarda los lotes con su trabajo.

## Sentimiento

**Causa del «N/A» anterior.** Ningún componente escribía `mensajes.sentimiento_ref`:

- el análisis de Gemini no pedía sentimiento;
- el worker insertaba los mensajes sin ese campo;
- la tabla mostraba `N/A` para `NULL`.

**Contrato.**

- Valores: `positivo`, `negativo`, `neutral` o `indeterminado` (tono no determinable con el texto).
- `NULL` significa **sin analizar**: nunca se convierte en neutral.
- El sentimiento es independiente de la intención: una duda o un bloqueo no son negativos por sí
  mismos.

**Obtención.**

- Viaja en la **misma** llamada `analizar` del grafo: un campo más en el esquema JSON.
- No añade llamadas. Sí añade unos pocos tokens de salida por mensaje y un renglón del prompt.
- Un valor ausente o fuera del contrato deja ese mensaje sin analizar y no hace fallar el lote.

**Persistencia.** El worker la escribe en la misma transacción que los activos:

- Solo sobre filas con `sentimiento_ref IS NULL`, de modo que nunca pisa un valor válido.
- Solo para IDs que pertenecen al lote.
- Registra `sentimiento_origen`, `sentimiento_version` (`gemini-analizar-v1`),
  `sentimiento_trabajo` y `sentimiento_fecha`.
- El modo simulado no escribe sentimiento.

**API.**

- `GET /api/mensajes?sentimiento=positivo|negativo|neutral|indeterminado|sin_analizar` filtra en el
  servidor.
- `GET /api/mensajes/sentimiento/resumen` devuelve los conteos del filtro completo, con porcentajes
  sobre analizados.

**Históricos.** `python -m backend.scripts.reprocesar_sentimiento previsualizar | ejecutar`:

- `ejecutar` exige `--limite`, `--max-llamadas` y `--confirmo-consumo`.
- Es reanudable e idempotente.
- La ejecución real requiere autorización aparte.

**Evaluación etiquetada.** `pipelines/communitylab/ejemplos/evaluacion_sentimiento.json` contiene
20 mensajes ficticios y se evalúa con `tools/evaluar_sentimiento.py`.

## Banners

- **Render.** `backend/app/services/banners.py` porta la plantilla de Fabián (Tarea 1, 15-10-26) a
  un SVG determinista de 1200×630:
  - Usa solo texto del copy aprobado.
  - Proveedor: `plantilla-svg-v1`.
  - **No es IA.**
- **Tabla `banners`.**
  - Hay uno por (activo, versión del texto), con estados `pendiente`, `generando`, `generado` y
    `error`, más la revisión `pendiente`, `aprobado` o `rechazado`.
  - Repetir la generación devuelve el mismo banner.
  - Uno en `error`, o abandonado en `generando` más de 120 s, se puede reintentar.
- **Invalidación.**
  - Editar el texto de un activo aprobado lo devuelve a `revisado` y sube su versión.
  - El banner anterior queda `desactualizado` y no se puede aprobar.
- **Entrega.** `GET /api/banners/{id}.svg` responde con `Content-Security-Policy: default-src
  'none'; sandbox` y `X-Content-Type-Options: nosniff`, y escapa todo el texto.
- **Pendiente.** Elegir un proveedor de imágenes con IA (costo, términos y revisión de hechos). No
  se simula una «generación con IA».

## Acceso

| Acción | Requisito |
|---|---|
| Procesar pendientes, aprobar textos, generar y revisar banners | Cabecera `X-Operador-Token` = `OPERADOR_TOKEN` |
| Tomar solicitudes e informar avance (puente) | `Authorization: Bearer` = `PUENTE_TOKEN` |
| Reprocesar sentimiento | CLI con acceso a la base, más `--confirmo-consumo` |

- Si la variable está vacía, la acción responde 503: nunca queda abierta por omisión.
- La interfaz guarda el token solo en el `sessionStorage` de la pestaña.

## Migraciones (aditivas) y reversión

`worker/schema.sql`, aplicado por el servicio `db-init` en cada despliegue, hace lo siguiente:

- Añade a `mensajes` las columnas `sentimiento_origen`, `sentimiento_version`,
  `sentimiento_trabajo` y `sentimiento_fecha`. Todas son nullables; `NULL` significa sin analizar.
- Crea las tablas `solicitudes_procesamiento` (con un índice único parcial por origen abierto),
  `estado_puente` y `banners`.

No modifica ni borra datos existentes. Los activos y mensajes anteriores siguen válidos.

**Reversión** (después de un respaldo comprobado; solo si se vuelve a la imagen anterior):

```sql
DROP TABLE IF EXISTS banners, solicitudes_procesamiento, estado_puente;
ALTER TABLE mensajes DROP COLUMN IF EXISTS sentimiento_origen, DROP COLUMN IF EXISTS sentimiento_version,
  DROP COLUMN IF EXISTS sentimiento_trabajo, DROP COLUMN IF EXISTS sentimiento_fecha;
-- Opcional, para revertir también los valores escritos por el worker:
-- UPDATE mensajes SET sentimiento_ref = NULL WHERE sentimiento_origen IN ('gemini','gemini-reproceso');
```

La imagen anterior ignora estas columnas y tablas, así que se puede revertir solo la imagen sin
tocar la base. En el puente, las tablas SQLite nuevas (`solicitudes_parciales`,
`entregas_solicitud`) son aditivas, y el código anterior las ignora.
