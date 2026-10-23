# Importación histórica de Discord (backend)

Permite que un operador traiga a CommunityLab los mensajes **ya existentes** de un canal autorizado dentro de
un rango de fechas. Es independiente del lector en vivo, del bot y de la bandeja: no escucha de forma
permanente, no responde en Discord, no envía alertas y no publica. Importar **no llama a Gemini**: el análisis
es un paso aparte que la persona confirma (fase 3).

## Fases

| Fase | Qué hace | Dónde |
|---|---|---|
| 1. Verificar y previsualizar | Comprueba lista autorizada, canal, servidor, membresía del bot, permisos y tipo; normaliza el rango; lee **una** página para estimar. No guarda nada. | API (`POST /verificar`, `POST /previsualizar`) |
| 2. Importar | Crea un trabajo persistente (202). Un runner aparte lo ejecuta página a página y guarda en tablas protegidas. | API (`POST /importaciones`) + servicio `discord-historico` de `compose.discord.yml` (`python -m backend.app.discord_historico.runner`) |
| 3. Enviar al análisis | Encola en el worker los mensajes importados que aún no se analizaron, con confirmación explícita del uso de Gemini. Repetirlo no duplica. | API (`GET`/`POST /importaciones/{id}/analisis`) + botón «Enviar al análisis» en Ingesta |

Módulos (`backend/app/discord_historico/`): `fechas` (rango e instantes), `permisos` (algoritmo oficial de
permisos efectivos), `configuracion` (entorno), `cliente` (HTTP solo GET, 429/reintentos), `servicio`
(verificación y previsualización), `store` (PostgreSQL), `importador` (paginación), `runner` (proceso).
Rutas: `backend/app/api/routes/discord_historico.py`. Esquema: final de `worker/schema.sql`.

## Configuración (solo backend)

| Variable | Uso | Por defecto |
|---|---|---|
| `DISCORD_HISTORICO_TOKEN` | Token del bot, solo lectura. Nunca se devuelve ni se registra. Sin él, 503 `discord_no_configurado`. | — |
| `DISCORD_HISTORICO_AUTORIZADOS` | JSON `{"<guild_id>": ["<canal_id>", ...]}`. Lista **propia**, distinta de la del lector en vivo. | vacía |
| `DISCORD_HISTORICO_MAX_MENSAJES` | Tope por importación (1–50000). | 5000 |
| `DISCORD_HISTORICO_MAX_DIAS` | Rango máximo (1–4000). | 400 |
| `DISCORD_HISTORICO_CONFIRMAR_DIAS` / `_CONFIRMAR_MENSAJES` | Por encima, `confirmar_alcance=true` es obligatorio. | 31 / 1000 |
| `DISCORD_HISTORICO_INTERVALO` | Espera del runner sin trabajo (s). | 5 |
| `DISCORD_HISTORICO_LATIDO` | Archivo de latido del runner para `… runner salud` (Compose: `/tmp/historico-latido.json`). | — |

El runner es opcional: sin `DISCORD_HISTORICO_TOKEN` (o con configuración inválida) queda **en espera y sano**,
sin reservar nada; nadie depende de él para arrancar. Una sola instancia (sin réplicas). En local, con Discord
simulado: `docker compose -f docker-compose.yml -f compose.local.yml up --build`.
| `DISCORD_API_BASE` | Solo pruebas: exige `DISCORD_HISTORICO_BASE_PRUEBA=1` y host `127.0.0.1`, `localhost` o `discord-falso`. | `https://discord.com/api/v10` |

Los IDs se validan como snowflakes (17–20 dígitos) y solo se insertan en rutas fijas; nunca se construyen
URLs arbitrarias. La lista autorizada se consulta **antes** de cualquier llamada a Discord.

## Contrato de fechas

- Entrada: `desde`, `hasta` (ISO 8601) y `zona` (IANA, p. ej. `America/Guatemala`). Se guarda en UTC.
- Intervalo semiabierto **[inicio, fin)**.
- `AAAA-MM-DD` en `desde` = **primer instante** de ese día local; en `hasta` = **todo** ese día (fin = primer
  instante del día siguiente local). Con cambio de horario un día puede durar 23 o 25 h (se calcula con la
  zona, no +24 h).
- **Medianoche inexistente** (el reloj salta a las 00:00, p. ej. `America/Sao_Paulo` el 2018-11-04): el día
  empieza en el primer instante cuya fecha local es la pedida (`2018-11-04T01:00:00-02:00`), nunca en una hora
  del día anterior. Vale igual para el fin exclusivo. Advertencia `<campo>_inicio_del_dia_ajustado_por_cambio_de_horario`.
  Se calcula con una búsqueda del primer instante con esa fecha local, sin depender de `fold`, así que también
  funciona si el salto empieza antes de medianoche.
- **Fecha local completa inexistente** (p. ej. `2011-12-30` en `Pacific/Apia`, que saltó ese día): 422
  `fecha_local_inexistente`, tanto en `desde` como en `hasta`.
- Fecha-hora sin desplazamiento = hora local de `zona`. Con desplazamiento (`Z`, `-06:00`) = instante exacto.
- Hora inexistente (salto de primavera) → 422 `hora_inexistente`; hora ambigua (otoño) → primera ocurrencia
  (`fold=0`) con advertencia `<campo>_ambigua_se_uso_la_primera_ocurrencia`. Una medianoche repetida usa también
  la primera.
- Errores 422: `fecha_invalida`, `zona_invalida`, `hora_inexistente`, `fecha_local_inexistente`,
  `rango_invertido`, `fecha_futura`, `rango_excesivo`, `rango_anterior_a_discord` (el rango termina antes de 2015).
- Si `fin` supera el momento de la solicitud se recorta a ese momento (advertencia
  `hasta_recortado_al_momento_de_la_solicitud`): el rango queda congelado.

### Previsualización ↔ creación

Cada operación calcula «ahora» por separado. Si el rango termina hoy, el corte de la creación es posterior al de
la previsualización y puede incluir mensajes nuevos. Para crear **exactamente** lo previsualizado, la
previsualización devuelve `alcance_congelado = {desde, hasta, zona}`: son instantes UTC con `Z`. Al enviarlos a
`POST /importaciones` no se recortan de nuevo. Para rangos que terminan en el pasado ambos cortes coinciden.

Representaciones recomendadas (zona `America/Guatemala`):

| Alcance | `desde` | `hasta` |
|---|---|---|
| Un día | `2026-09-14` | `2026-09-14` |
| Semana ISO W38 | `2026-09-14` | `2026-09-20` |
| Mes | `2026-09-01` | `2026-09-30` |
| Año | `2025-01-01` | `2025-12-31` (requiere confirmación) |

## Llamadas a Discord (API v10, solo GET)

| Paso | Llamadas |
|---|---|
| Verificar | `GET /channels/{id}`, `GET /users/@me`, `GET /guilds/{g}/members/{bot}`, `GET /guilds/{g}`, `GET /guilds/{g}/roles` (5) |
| Previsualizar | las 5 anteriores + 1 × `GET /channels/{id}/messages?before=<snowflake(fin)>&limit=100` |
| Importar | las 5 de verificación al iniciar cada ejecución + 1 por cada página de hasta 100 mensajes |

Permisos efectivos según el algoritmo oficial (dueño → todos; `@everyone` + roles; `ADMINISTRATOR`;
sobrescrituras `@everyone` → roles → miembro). Se exigen `VIEW_CHANNEL` y `READ_MESSAGE_HISTORY`.

## Paginación, límites y recuperación

- Hacia atrás con `before`: el primer cursor es el snowflake de `fin`, de modo que nada posterior entra,
  ni siquiera mensajes enviados durante la importación. Se avanza con el ID más antiguo de la página y se
  detiene al cruzar `inicio`, con una página incompleta o vacía.
- Si el cursor no retrocede → `error` `cursor_sin_avance` (no hay bucles).
- 429: espera `retry_after` (cuerpo) o `Retry-After`; si supera 60 s o se repite → `error` reanudable
  `limite_discord`. Si `X-RateLimit-Remaining` llega a 0 espera el `reset-after`. 5xx/timeout: reintento
  con espera creciente (máx. 3) → `error_transitorio_discord` reanudable.
- 401 → `credencial_discord_invalida`; 403/404 en mitad → error **no** reanudable
  (`permiso_revocado_o_canal_eliminado`).
- Cada página y su cursor se guardan en una sola transacción. Reserva con token y vencimiento (60 s):
  si el runner muere, al vencer otro runner retoma desde el cursor; repetir una página no duplica.
  Tras 5 intentos → `error` `reintentos_agotados`.
- Tope `max_mensajes`: termina `completada_con_limite` (resultado parcial, `limite_alcanzado=true`,
  `motivos_parcial` incluye `max_mensajes`).

Estados: `pendiente → ejecutando → completada | completada_con_limite | cancelada | error`.
`cancelar`: pendiente → cancelada al instante; ejecutando → se detiene antes de la siguiente página.
`reanudar`: solo `error` con `reanudable=true`; vuelve a `pendiente` y continúa desde el cursor.
Una sola importación activa por canal (índice único parcial).

### Idempotencia

- Se guardan por separado los **parámetros solicitados** (`solicitud`) y el **rango efectivo** congelado
  (`desde_utc`, `hasta_utc`).
- `huella_solicitud` = `v1-` + SHA-256 del JSON canónico de `[canal_id, desde, hasta, zona, max_mensajes]`:
  - las cadenas van tal como se enviaron, sin espacios exteriores;
  - `max_mensajes` va como se envió, `null` si se omitió;
  - no entran `confirmar_alcance` (es consentimiento, no alcance) ni la hora de la solicitud.
- Con `Idempotency-Key`, la clave se busca **antes** de recalcular el rango:
  - **misma huella:** devuelve la importación original (`reutilizada: true`) con su corte, aunque haya pasado
    tiempo o ya esté terminada;
  - **huella distinta:** 409 `clave_idempotencia_reutilizada`.
- Recuperar una clave **no salta la autorización**: exige el token de operador y que el canal siga en la lista
  autorizada (403 `canal_no_autorizado`). No consulta Discord; el runner vuelve a verificar al ejecutar.
- **Concurrencia con la misma clave:** convergen en una sola importación. Una violación de unicidad, o ver a la
  gemela como «activa», se resuelve releyendo por clave. Solo una clave distinta recibe
  `importacion_activa_en_el_canal`.
- **Filas sin huella**, creadas antes de esta versión: su clave se trata como de otra solicitud (409).

## Almacenamiento y deduplicación

Tablas protegidas (no se exponen por `/api/mensajes` ni alimentan el panel público):

- `discord_importaciones`: parámetros, estado, contadores, cursor, error estructurado sin secretos, fechas.
- `discord_mensajes_historicos`: un registro por mensaje con id canónico `discord-<message_id>` (el mismo
  que usa el lector en vivo). Guarda autor (ID), fecha (del snowflake), texto, `contenido_disponible`,
  tipo, metadatos de adjuntos **sin URL ni descarga**, referencia, fecha de captura y la instantánea de ingesta/IA
  (`en_ingesta_vivo`, `estado_ia_captura`, `estado_ia_trabajo`, `procesado_ia`).
- `discord_importacion_mensajes`: relación importación ↔ mensaje con `resultado`
  (`insertado`, `existente`, `existente_en_vivo`, `editado`).

Políticas:
- **Superposición**: un mensaje ya importado no se duplica; la nueva importación lo enlaza como `existente`.
- **Llegado en vivo:** si `discord-<id>` ya está en `mensajes`, el resultado es `existente_en_vivo` y
  `en_ingesta_vivo=true`. Eso solo prueba que se **guardó**: la ingesta inserta en `mensajes` al encolar,
  antes de procesar. Nunca se modifica la tabla `mensajes`.
- **Estado de IA:**
  - Se obtiene solo de evidencia vinculada al mensaje: filas de `trabajos_worker` cuyo
    `entrada.interacciones[].id` es el `id_mensaje`. Es la misma relación que usa `services/ambito.py`.
  - Valores: `procesado` (algún trabajo `terminado`), `pendiente` (`recibido`/`procesando`), `fallido` (solo
    `error`) y `sin_evidencia` (ningún trabajo).
  - `procesado_ia` es `true` únicamente si el estado es `procesado`. No se infiere de `sentimiento` ni de otros
    campos sueltos.
  - `terminado` acredita que el lote que contenía el mensaje se procesó con éxito, no que generara un activo.
- **Sin obsolescencia:**
  - `estado_ia_captura` y `estado_ia_trabajo` son lo observado al importar.
  - `GET …/mensajes` devuelve además `estado_ia`, `estado_ia_trabajo` y `procesado_ia` **calculados en ese
    momento**. Así, un mensaje importado primero y procesado después por otra vía no queda con un estado viejo.
  - Las filas creadas antes de esta corrección (solo en bases locales) pueden tener un `procesado_ia=true` sin
    respaldo. La API no lo usa.
- **Ediciones**: `texto` conserva la **primera captura**; si Discord trae otra versión se guarda en
  `texto_ultima_version` con `edicion_detectada_en`. Nunca se alteran fuentes de activos aprobados.
- **Borrados**: un mensaje borrado en Discord **antes** de importar no se puede recuperar (la API no lo devuelve).
  Uno borrado después de importarse permanece aquí; la importación no lo detecta.
- **Consistencia**: la importación observa el canal mientras pagina; ediciones o borrados concurrentes pueden
  hacer que el historial guardado no sea una instantánea exacta de un solo momento.
- **Contenido**: `texto=""` con `contenido_disponible=false` puede indicar que el bot no tiene el intent
  `MESSAGE_CONTENT` (la previsualización lo advierte). Vacío con adjuntos/embeds es `contenido_disponible=true`.
- Se excluyen bots, webhooks y mensajes de sistema (tipos distintos de 0 y 19); quedan en `descartados`.
- **Adjuntos**: solo `id`, `filename`, `content_type` y `size`. No se guardan URLs porque los enlaces de
  Discord caducan; no se descargan adjuntos ni se visitan URLs de los mensajes.
- Importar **no** significa procesado por IA ni consentimiento para publicar.

## Alcance v1

Canales de texto (0) y anuncios (5). Hilos (10–12), foros (15), medios (16), voz y escenario → 422
`tipo_no_soportado`. Los mensajes que inician hilos se cuentan en `hilos_detectados`, pero los mensajes
dentro de los hilos **no** se importan (`alcance = canal_sin_hilos`). Si se detectó algún hilo, la importación
**no** se declara completa: termina `completada_con_limite` con `motivos_parcial = ["hilos_excluidos"]`.

## Fase 3: enviar al análisis

`GET /api/v1/discord/historico/importaciones/{id}/analisis` resume cuántos mensajes de la importación ya están en
el análisis y cuántos faltan; `POST` (202) encola los que faltan (`backend/app/discord_historico/analisis.py`).

1. **Mismo mensaje que en vivo:** cada mensaje se convierte igual que en el lector en vivo (`discord-<message_id>`,
   `discord_<canal_id>`, fecha UTC), así un mensaje que también llegó en vivo es el mismo registro.
2. **Lotes por semana:** origen propio `discord-historico` y un período por semana ISO; el último lote de cada
   semana cierra ese período (genera su resumen).
3. **Sin duplicar:** lo ya enviado queda fuera y la cola deriva la clave del contenido, así repetir el envío
   reutiliza los mismos trabajos. El puente en vivo tampoco vuelve a analizar estos mensajes: los consulta en
   `POST /api/v1/puente/mensajes/analizados` y los trata como contexto.
4. **Confirmación:** en Ingesta, la persona confirma que se usará Gemini antes de enviar («Entiendo que se usará
   la IA…» y «Enviar al análisis»).

## Reversión

```sql
DROP TABLE IF EXISTS discord_importacion_mensajes;
DROP TABLE IF EXISTS discord_mensajes_historicos;
DROP TABLE IF EXISTS discord_importaciones;
```
Las tablas son aditivas; quitarlas no afecta `mensajes`, `activos` ni `trabajos_worker`. Las columnas
`solicitud`, `huella_solicitud`, `en_ingesta_vivo`, `estado_ia_captura` y `estado_ia_trabajo` se añaden con
`ADD COLUMN IF NOT EXISTS` a bases creadas con la versión anterior; viven en esas tablas nuevas y caen con ellas. Quitar además el
router en `backend/app/main.py` y no arrancar el runner.

## Pruebas

```bash
DISCORD_HISTORICO_TEST_DATABASE_URL=postgresql://USUARIO:CLAVE@127.0.0.1:15441/discord_historico_test \
  python -m pytest -q -p no:cacheprovider worker/tests/test_discord_historico.py
```
Discord es un `httpx.MockTransport` que solo acepta GET; la fixture impide usar otra base y hace fallar
cualquier intento de crear un cliente de Gemini.
