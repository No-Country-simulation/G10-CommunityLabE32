# Contrato frontend: importación histórica de Discord

**Para:** frontend (panel «Discord») · **Estado:** backend en PR borrador, no desplegado.

**Pruebas hasta ahora**
- Automáticas, con Discord **simulado** y PostgreSQL local.
- Una lectura real limitada con Discord (canal de pruebas, un día, 3 mensajes), hecha **antes** de las últimas
  correcciones y no repetida después.

**Qué hace y qué no.** Este documento describe lo que el panel puede pedir y lo que responde el backend.
- Importar **solo** copia mensajes existentes de un canal autorizado a tablas protegidas.
- **No** procesa con IA, no publica, no responde en Discord, no envía alertas y no cierra períodos.

Detalle técnico (arquitectura, llamadas a Discord, almacenamiento, reversión): [`discord-historico.md`](discord-historico.md).

---

## 1. Autenticación

Todas las rutas exigen **rol operador** (política completa: [`politica-acceso.md`](politica-acceso.md)).
- Navegador: sesión por cookie HttpOnly `cl_sesion` + cabecera `X-CSRF-Token` en los POST. El frontend no
  envía tokens propios; el CSRF se obtiene al iniciar sesión o con `GET /api/auth/sesion`.
- Terminal: `X-Operador-Token: <token de operador>` (compatibilidad; en la VM, `sudo cl-token-operador`).
- Cada importación pertenece a quien la pidió (`usuario:<id>` o `operador:token-compartido`): un operador solo
  ve, consulta, cancela y reanuda las suyas (una ajena da 404); un administrador ve todas. La `Idempotency-Key`
  de una persona se acota a su cuenta; el frontend usa una clave nueva por cada previsualización confirmada.

| Caso | HTTP | `detail.codigo` |
|---|---|---|
| Sin sesión ni token, sesión vencida o revocada | 401 | `sesion_requerida` / `sesion_invalida` |
| Token de operador incorrecto | 401 | `token_invalido` |
| Cuenta sin rol operador / falta CSRF | 403 | `permiso_insuficiente` / `csrf_invalido` |
| El servidor no tiene `OPERADOR_TOKEN` (con cabecera de token) o `JWT_SECRET_KEY` (con sesión) | 503 | `acceso_no_configurado` / `autenticacion_no_configurada` |

El **token de Discord nunca llega al navegador**: vive solo en el backend.

**Errores.** Tienen siempre esta forma:

```json
{ "detail": { "codigo": "canal_no_autorizado", "mensaje": "Texto legible en español" } }
```

Muestra `mensaje` y decide el comportamiento por `codigo`. Los errores de validación de FastAPI (campos que faltan,
tipos incorrectos o campos extra) llegan como 422 con `detail` en forma de **lista**.

**Base:** `/api/v1/discord/historico`. Todas las peticiones con cuerpo son `application/json`.

### IDs de Discord

Todos los IDs (`canal_id`, `guild_id`, `message_id`, `autor_id`, `referencia`) son **cadenas** de 17 a 20 dígitos,
tanto en las peticiones como en las respuestas. **Nunca los conviertas a número**: superan
`Number.MAX_SAFE_INTEGER` y JavaScript los redondea. El identificador interno de un mensaje es
`id_mensaje = "discord-<message_id>"`, y el de una importación, `id = "imp-<hex>"`.

---

## 2. Flujo de la pantalla

```
[Canal] → Verificar → [Rango + zona + máx.] → Previsualizar → (confirmar alcance si se pide)
        → Importar (202) → sondear estado cada 2–3 s → resumen final → ver mensajes importados
```

### Campos del formulario

| Campo | Qué enviar |
|---|---|
| `canal_id` | Texto de 17 a 20 dígitos (en Discord: clic derecho en el canal → *Copiar ID*). El servidor se deduce del canal. |
| `desde`, `hasta` | `AAAA-MM-DD`. `hasta` incluye **el día completo**. Con hora, `AAAA-MM-DDTHH:MM` sin desplazamiento: se interpreta en `zona`. |
| `zona` | Zona IANA, por ejemplo `America/Guatemala`. |
| `max_mensajes` | Opcional, entero ≥ 1. Sin él se usa el tope del servidor (5000 por defecto). |

### Atajos con el mismo contrato

| Atajo | `desde` → `hasta` |
|---|---|
| Día | El mismo día en los dos campos |
| Semana | Lunes → domingo |
| Mes | Día 1 → último día |
| Año | 1-1 → 31-12 (requiere confirmación) |

### Pasos del flujo

1. **Confirmación.** Si la previsualización devuelve `limites.requiere_confirmacion = true`, muestra un checkbox
   («Confirmo importar este alcance») y envía `confirmar_alcance: true`. Se exige por encima de **31 días** o de
   **1000 mensajes**, umbrales configurables en el servidor.
2. **Importar lo previsualizado.** Cada operación calcula «ahora» por separado.
   - Si el rango termina hoy, crea la importación con `alcance_congelado` de la previsualización:

     ```json
     {"canal_id": "…", "desde": "<alcance_congelado.desde>", "hasta": "<alcance_congelado.hasta>", "zona": "<alcance_congelado.zona>", "max_mensajes": 100}
     ```

     Son instantes UTC con `Z` y no se recortan otra vez.
   - Si envías las fechas del formulario, el corte es el momento de la creación (advertencia
     `hasta_recortado_al_momento_de_la_solicitud`).
3. **Idempotencia.** Genera un UUID al pulsar «Importar» y mándalo en la cabecera `Idempotency-Key` (máx. 128
   caracteres).
   - **Mismo UUID y mismo cuerpo:** devuelve la importación original (`reutilizada: true`) con su corte. Vale para
     un doble clic o un reintento minutos después, aunque el rango termine hoy o la importación ya haya terminado.
   - **Mismo UUID con otro `canal_id`, `desde`, `hasta`, `zona` o `max_mensajes`:** 409 `clave_idempotencia_reutilizada`.
     `confirmar_alcance` no cuenta como cambio.
   - **Cuándo generar uno nuevo:** cada vez que el usuario cambie el formulario.
   - **Ojo con la huella:** es textual. `"2026-10-01"` y `"2026-10-01T00:00"` cuentan como solicitudes distintas.

---

## 3. Endpoints

| Método | Ruta | Respuesta |
|---|---|---|
| `POST` | `/verificar` | 200: acceso al canal |
| `POST` | `/previsualizar` | 200: rango, límites y conteo |
| `POST` | `/importaciones` | **202**: crea (o recupera por clave) |
| `GET` | `/importaciones?limite=20` | 200: lista (1–100, las más recientes primero) |
| `GET` | `/importaciones/{id}` | 200: estado y progreso |
| `POST` | `/importaciones/{id}/cancelar` | 200 |
| `POST` | `/importaciones/{id}/reanudar` | 200 / 409 |
| `GET` | `/importaciones/{id}/mensajes?limite=50&desplazamiento=0` | 200: mensajes importados (`limite` 1–200) |
| `GET` | `/importaciones/{id}/analisis` | 200: cuántos faltan por enviar al análisis, en cuántos lotes y semanas |
| `POST` | `/importaciones/{id}/analisis` | **202**: los encola en el worker (IA) / 409 si la importación no terminó |
| `GET` | `/estado` | 200: `disponible`, `sin_configurar` o `configuracion_invalida` (no consulta Discord) |

No existe ningún endpoint para publicar o borrar importaciones.

### Envío al análisis

Importar **no** usa la IA. Enviar al análisis es un paso aparte y explícito:
- Solo entra lo que aún **no está en `mensajes`**: lo que llegó por el lector en vivo lo procesa su propio
  lote, y los mensajes sin texto se omiten.
- Cada mensaje se convierte igual que en el lector en vivo (`discord-<id>`, autor = id del autor,
  canal = `discord_<canal_id>`), así que no hay conflictos con la ingesta en vivo.
- Los lotes usan el origen `discord-historico` y un período por semana ISO (`2026-W36`); el último lote de
  cada semana cierra ese período (alertas y borradores). Máximo 500 mensajes por lote.
- Repetirlo no duplica: lo enviado ya está en `mensajes` y un lote idéntico reutiliza su trabajo.
- Consume cuota de Gemini (una llamada por bloque de mensajes, como cualquier lote).

### 3.1 `POST /verificar`

Comprueba el acceso. No lee mensajes ni guarda nada.

Orden de comprobación:
1. Formato del ID.
2. **Lista de canales autorizados**, propia de esta herramienta y distinta de la del lector en vivo. Si el canal no
   está, se responde 403 **sin consultar Discord**.
3. Canal.
4. Servidor.
5. Bot miembro del servidor.
6. Permisos efectivos «Ver canal» y «Leer historial de mensajes».
7. Tipo de canal.

```json
// Petición
{ "canal_id": "222222222222222222" }
// 200
{
  "canal": { "id": "222222222222222222", "nombre": "general-ficticio", "tipo": 0, "tipo_nombre": "texto" },
  "servidor": { "id": "111111111111111111", "nombre": "Servidor ficticio" },
  "autorizado_en_herramienta": true,
  "bot_en_servidor": true,
  "permisos": { "ver_canal": true, "leer_historial": true },
  "tipo_soportado": true
}
```

### 3.2 `POST /previsualizar`

Hace lo mismo que `/verificar`, normaliza el rango y lee **una sola página** de Discord (hasta 100 mensajes) para
estimar. No guarda nada.

```json
// Petición
{ "canal_id": "222222222222222222", "desde": "2026-09-01", "hasta": "2026-09-20",
  "zona": "America/Guatemala", "max_mensajes": 1000, "incluir_muestra": true }
// 200 (campos de /verificar, más:)
{
  "rango": {
    "inicio_utc": "2026-09-01T06:00:00Z", "fin_utc_exclusivo": "2026-09-21T06:00:00Z",
    "zona": "America/Guatemala",
    "inicio_local": "2026-09-01T00:00:00-06:00", "fin_local_exclusivo": "2026-09-21T00:00:00-06:00",
    "dias": 20.0
  },
  "alcance_congelado": { "desde": "2026-09-01T06:00:00Z", "hasta": "2026-09-21T06:00:00Z",
                         "zona": "America/Guatemala" },
  "limites": {
    "max_mensajes": 1000, "max_mensajes_configurado": 5000, "max_dias": 400,
    "requiere_confirmacion": false, "umbral_confirmacion": { "dias": 31, "mensajes": 1000 }
  },
  "conteo": { "tipo": "desconocido", "minimo": 100, "estimacion_aproximada": 240,
              "nota": "Estimación por densidad de la primera página; el total exacto se conoce al importar." },
  "alcance": "canal_sin_hilos",
  "advertencias": ["se_excluyen_bots_webhooks_y_mensajes_de_sistema"],
  "llamadas_discord": 6,
  "muestra": [ { "id_mensaje": "discord-1551442850611200239", "fecha": "2026-09-21T04:00:00Z",
                 "autor_id": "700000000000000001", "texto": "mensaje ficticio 239" } ]
}
```

**Tipos de conteo**

| `conteo.tipo` | Campos | Cómo mostrarlo |
|---|---|---|
| `exacto` | `mensajes_en_rango`, `importables` | «Se importarán N mensajes» |
| `desconocido` | `minimo`, `estimacion_aproximada`, `nota` | «Al menos N (estimado ~M)». Nunca como exacto. |

**Muestra.** Solo llega si se pide (`incluir_muestra: true`): como máximo 5 mensajes de 200 caracteres. No se guarda.
No la dejes en caché ni la registres.

**Advertencias**, para mostrarlas como avisos, no como errores:

| Código | Significado |
|---|---|
| `hilos_detectados_no_incluidos:N` | Hay N hilos cuyos mensajes **no** se importan (la importación quedará parcial) |
| `contenido_vacio:N (…)` | N mensajes sin texto: puede faltar el intent *Message Content* del bot |
| `se_excluyen_bots_webhooks_y_mensajes_de_sistema` | Aviso fijo |
| `hasta_recortado_al_momento_de_la_solicitud` | El fin se recortó a «ahora» |
| `desde_ambigua_se_uso_la_primera_ocurrencia` / `hasta_…` | Hora repetida por un cambio de horario; se tomó la primera |
| `desde_inicio_del_dia_ajustado_por_cambio_de_horario` / `hasta_…` | La medianoche no existe ese día en la zona; el día empieza en su primer instante válido (p. ej. 01:00) |
| `desde_ajustado_al_inicio_de_discord_2015` | El inicio era anterior a Discord |

### 3.3 `POST /importaciones` → 202

Cabecera opcional: `Idempotency-Key: <uuid>`.

```json
// Petición
{ "canal_id": "222222222222222222", "desde": "2026-09-01", "hasta": "2026-09-20",
  "zona": "America/Guatemala", "max_mensajes": 1000, "confirmar_alcance": false }
// 202
{ "importacion": { "id": "imp-…", "estado": "pendiente", "…": "ver §4" },
  "reutilizada": false, "advertencias": [] }
// 202 al repetir con la misma Idempotency-Key y el mismo cuerpo
{ "importacion": { "id": "imp-… (la misma)", "estado": "completada", "…": "corte original" },
  "reutilizada": true, "advertencias": [] }
```

- El 202 significa que quedó **en cola**. La descarga la hace el **runner**, un proceso aparte (§7). Sin runner
  activo, la importación se queda en `pendiente`.
- Recuperar una importación por su clave sigue exigiendo el token y que el canal esté autorizado. Si el canal se
  retiró de la lista, responde 403 `canal_no_autorizado`.

### 3.4 Consultar, cancelar y reanudar

- **`GET /importaciones/{id}`:** devuelve el objeto Importación (§4). Sondéalo mientras esté `pendiente` o
  `ejecutando`.
- **`POST …/cancelar`:**
  - si estaba `pendiente`, pasa a `cancelada` al instante;
  - si estaba `ejecutando`, marca `cancelacion_solicitada: true` y el runner se detiene antes de la siguiente página;
  - lo importado hasta entonces se conserva.
- **`POST …/reanudar`:** solo funciona con `estado = error` y `error.reanudable = true`. Vuelve a `pendiente` y
  continúa desde el cursor guardado, sin duplicar. En otro caso, 409 `no_reanudable`.

### 3.5 `GET /importaciones/{id}/mensajes`

```json
{ "total": 240, "items": [
  { "id_mensaje": "discord-1551442850611200239", "message_id": "1551442850611200239",
    "autor_id": "700000000000000001", "fecha": "2026-09-21T04:00:00+00:00", "editado_en": null,
    "capturado_en": "2026-10-19T05:58:00+00:00",
    "texto": "mensaje ficticio 239", "contenido_disponible": true, "tipo_discord": 0,
    "adjuntos": [], "referencia": null, "texto_ultima_version": null,
    "en_ingesta_vivo": false, "estado_ia_captura": "sin_evidencia",
    "estado_ia": "sin_evidencia", "estado_ia_trabajo": null, "procesado_ia": false,
    "resultado": "insertado" } ] }
```

**`estado_ia`** se calcula en el momento de la consulta: no queda viejo si el mensaje se procesa después por otra vía.

| Valor | Significado | Cómo mostrarlo |
|---|---|---|
| `sin_evidencia` | Ningún trabajo de IA contiene este mensaje | «Sin procesar» |
| `pendiente` | Está en un trabajo `recibido` o `procesando` | «En proceso» |
| `fallido` | Solo aparece en trabajos con `error` | «Falló el procesamiento» |
| `procesado` | Aparece en un trabajo `terminado` | «Procesado» |

- `procesado_ia` es `true` solo si `estado_ia = procesado`. `estado_ia_trabajo` es el trabajo que respalda ese estado.
- `estado_ia_captura` es lo observado al importar; es un dato histórico. Usa `estado_ia`.
- `en_ingesta_vivo`: el mensaje ya estaba guardado por la ingesta en vivo. **No** significa que se haya procesado.
- `adjuntos`: solo `id`, `filename`, `content_type` y `size`. **No hay URL** (los enlaces de Discord caducan).
- `texto: ""` con `contenido_disponible: false` se muestra como «contenido no disponible», no como «mensaje vacío».
- `texto_ultima_version` no nulo: el mensaje se editó después de la primera captura. `texto` conserva la primera.
- `resultado` en esta importación:
  - `insertado`: nuevo;
  - `existente`: lo trajo otra importación;
  - `existente_en_vivo`: ya estaba en la ingesta en vivo;
  - `editado`: ya existía y cambió.

---

## 4. Objeto Importación y estados

**Campos de identificación y alcance**
- `id`, `guild_id`, `canal_id`, `canal_nombre`, `canal_tipo`.
- `desde_utc`, `hasta_utc` (exclusivo), `zona`, `desde_local`, `hasta_local`: el rango **efectivo**, congelado al
  crear.
- `solicitud`: parámetros tal como se pidieron. `huella_solicitud`: la huella de idempotencia.
- `max_mensajes`, `solicitante`.

**Campos de estado:** `estado`, `cancelacion_solicitada`, `limite_alcanzado`, `motivos_parcial`, `alcance`, `error`,
`intentos`, `creado`, `iniciado`, `finalizado` y `ultimo_avance`.

**Contadores**

| Campo | Significado |
|---|---|
| `paginas` | Páginas leídas de Discord |
| `examinados` | Mensajes vistos, incluidos los que quedan fuera del rango |
| `en_rango` | Mensajes dentro del rango |
| `insertados`, `existentes`, `existentes_en_vivo`, `editados` | Resultado por mensaje (§3.5) |
| `descartados` | Objeto con las claves presentes, p. ej. `{"bot": 1, "sistema": 2}` (posibles: `bot`, `webhook`, `sistema`, `fuera_de_rango`) |
| `hilos_detectados` | Hilos encontrados; sus mensajes no se importan |

**Estados**

| `estado` | Qué mostrar | ¿Final? | Acciones |
|---|---|---|---|
| `pendiente` | «En cola» | No | Cancelar |
| `ejecutando` | Barra indeterminada, contadores y «último avance hace X s» | No | Cancelar |
| `completada` | «Completa: N nuevos, E ya existían» | Sí | Ver mensajes |
| `completada_con_limite` | «**Parcial**», con el motivo de `motivos_parcial` (pueden venir ambos):<br>`max_mensajes` → «se alcanzó el máximo de N; hay más en el rango»;<br>`hilos_excluidos` → «había hilos que no se importaron» | Sí | Ver mensajes · nueva importación |
| `cancelada` | «Cancelada; lo importado se conserva» | Sí | Ver mensajes |
| `error` | `error.codigo` traducido (§5) | Sí | Reanudar solo si `error.reanudable` |

**Progreso sin total conocido.** Discord no informa el total.
- **No muestres un porcentaje.** Usa una barra indeterminada con `insertados + existentes + existentes_en_vivo + editados`.
- Si `ultimo_avance` lleva más de ~2 minutos sin cambiar en `ejecutando`, muestra «sin avance reciente». El runner
  puede haberse detenido; la importación se retoma sola cuando vuelve.

---

## 5. Errores y límites

### Verificación

| `codigo` | HTTP | Mensaje sugerido |
|---|---|---|
| `canal_id_invalido` | 422 | El ID del canal debe tener entre 17 y 20 dígitos |
| `canal_no_autorizado` | 403 | Este canal no está autorizado para importación histórica |
| `canal_inaccesible` | 403 | El bot no puede ver este canal o no existe |
| `servidor_no_coincide` | 403 | El canal no pertenece al servidor autorizado |
| `bot_fuera_del_servidor` | 403 | El bot no está en ese servidor |
| `permisos_insuficientes` | 403 | El bot necesita «Ver canal» y «Leer historial de mensajes» |
| `tipo_no_soportado` | 422 | Solo canales de texto o de anuncios |

### Rango y límites (422)

| `codigo` | Mensaje sugerido |
|---|---|
| `fecha_invalida` | Fecha con formato incorrecto (AAAA-MM-DD) |
| `zona_invalida` | Zona horaria desconocida |
| `hora_inexistente` | Esa hora no existe en la zona por el cambio de horario |
| `fecha_local_inexistente` | Ese día no existe en la zona elegida |
| `rango_invertido` | «Desde» debe ser anterior a «hasta» |
| `fecha_futura` | El inicio no puede estar en el futuro |
| `rango_excesivo` | El rango supera el máximo (400 días por defecto) |
| `rango_anterior_a_discord` | El rango termina antes de 2015 |
| `limite_invalido` | `max_mensajes` supera el tope del servidor |

### Conflictos (409)

| `codigo` | Acción sugerida |
|---|---|
| `confirmacion_requerida` | Mostrar el checkbox y reenviar con `confirmar_alcance: true` |
| `importacion_activa_en_el_canal` | Ya hay una en curso para ese canal; `detail.importacion` la trae, así que puedes navegar a ella |
| `clave_idempotencia_reutilizada` | Generar una nueva `Idempotency-Key` |
| `no_reanudable` | La importación no se puede reanudar |

### Servicio

| `codigo` | HTTP | Mensaje sugerido |
|---|---|---|
| `importacion_no_encontrada` | 404 | Importación no encontrada |
| `discord_no_configurado`, `configuracion_invalida`, `credencial_discord_invalida` | 503 | La importación de Discord no está disponible en el servidor; avisa a soporte |
| `limite_discord`, `error_transitorio_discord`, `error_discord` | 502 | Discord no respondió; inténtalo más tarde |

### Dentro de `importacion.error`

| `error.codigo` | `reanudable` |
|---|---|
| `limite_discord`, `error_transitorio_discord`, `reintentos_agotados` | Sí |
| `sin_permiso_discord`, `no_encontrado_discord` (permiso revocado o canal eliminado) | No |
| `cursor_sin_avance` | No |
| `canal_no_autorizado`, `permisos_insuficientes`, `tipo_no_soportado` | No |

`error` nunca contiene el token ni texto de mensajes.

**Límites por defecto** (configurables con `DISCORD_HISTORICO_*`):
- 5000 mensajes por importación;
- 400 días de rango;
- confirmación por encima de 31 días o de 1000 mensajes;
- una importación activa por canal.

---

## 6. Canales admitidos

| Tipo | Admitido |
|---|---|
| Texto (`0`) y anuncios (`5`) | Sí |
| Hilos (`10`, `11`, `12`), foros (`15`), medios (`16`), voz (`2`), escenario (`13`), categorías (`4`) | **No**: 422 `tipo_no_soportado` |

Los mensajes **dentro** de hilos no se importan. Si se detectan hilos, la importación termina como parcial
(`hilos_excluidos`). También se excluyen siempre los bots, los webhooks y los mensajes de sistema.

---

## 7. Ejecutar y probar en local

No hace falta Discord real ni Gemini. Comandos para bash (Linux, macOS o Git Bash), desde la raíz del repositorio,
con un entorno que tenga `backend/requirements.txt` instalado.

**1. PostgreSQL desechable**

```bash
docker run -d --name cl-historico-dev -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=communitylab -p 127.0.0.1:15450:5432 postgres:16-alpine
```

**2. Variables** (valores ficticios, solo para local)

```bash
export DATABASE_URL=postgresql+asyncpg://dev:dev@127.0.0.1:15450/communitylab OPERADOR_TOKEN=operador-local DISCORD_HISTORICO_TOKEN=token-ficticio DISCORD_HISTORICO_AUTORIZADOS='{"111111111111111111":["222222222222222222"]}' DISCORD_API_BASE=http://127.0.0.1:15442/api/v10 DISCORD_HISTORICO_BASE_PRUEBA=1 DISCORD_HISTORICO_INTERVALO=1
```

**3. Esquema**

```bash
python -m worker.init_db
```

**4. Discord falso**, en otra terminal:

```bash
python -m uvicorn --app-dir tools discord_falso_historico:app --host 127.0.0.1 --port 15442
```

**5. API**, en otra terminal con las mismas variables:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**6. Runner**, el proceso que ejecuta las importaciones, en otra terminal:

```bash
python -m backend.app.discord_historico.runner
```

**7. Probar**, por ejemplo:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/discord/historico/previsualizar -H 'X-Operador-Token: operador-local' -H 'Content-Type: application/json' -d '{"canal_id":"222222222222222222","desde":"2026-09-01","hasta":"2026-09-20","zona":"America/Guatemala","max_mensajes":1000}'
```

El Discord falso tiene el canal `222222222222222222` del servidor `111111111111111111`, con estos datos:
- 240 mensajes ficticios cada 2 h desde el 01-09-2026 (hora de Guatemala);
- 1 mensaje de bot;
- 1 mensaje anterior al rango.

`GET http://127.0.0.1:15442/_registro` muestra las peticiones recibidas, que son solo GET.

`DISCORD_API_BASE` **solo** se acepta con `DISCORD_HISTORICO_BASE_PRUEBA=1` y host `127.0.0.1`, `localhost` o
`discord-falso`. En cualquier otro caso se usa `https://discord.com/api/v10`.

**Pruebas automáticas.** Exigen exactamente `127.0.0.1:15441/discord_historico_test`, una base desechable:

```bash
DISCORD_HISTORICO_TEST_DATABASE_URL=postgresql://USUARIO:CLAVE@127.0.0.1:15441/discord_historico_test python -m pytest -q -p no:cacheprovider worker/tests/test_discord_historico.py
```

**En la VM:** el runner **no** está todavía en `docker-compose.yml` ni desplegado. Añadirlo como servicio es un paso
posterior que requiere autorización.

---

## 8. Después de importar

**Qué ocurre**
- Los mensajes quedan en las tablas protegidas `discord_mensajes_historicos` y `discord_importacion_mensajes`.
- Solo se ven por `GET …/importaciones/{id}/mensajes`, con el token.

**Qué NO ocurre automáticamente**
- No se procesan con IA: `estado_ia` no cambia al importar.
- No aparecen en `/api/mensajes` ni en el panel público.
- No se generan activos ni banners y no se publica nada.
- El bot no responde y no se envían alertas.
- No se cierra ningún período.
- No se descarga ningún adjunto.

**Procesar con IA (fase 3)** está **sin implementar**. Será una acción explícita aparte, con estimación de costo y
autorización; el plan está en [`discord-historico.md`](discord-historico.md). El frontend no debe ofrecer ese botón
todavía.
