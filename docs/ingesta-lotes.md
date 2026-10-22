# Ingesta de lotes y seguimiento de trabajos

## Entradas

| Ruta | Uso |
|---|---|
| `POST /api/mensajes/procesamientos` (multipart: `file`, `origen_comunidad`, `periodo_referencia`, `cierre_periodo`) | Panel `/ingesta`. |
| `POST /api/v1/trabajos` (JSON, cabecera opcional `Idempotency-Key`) | Puente de Discord e integraciones. |
| `GET /api/v1/trabajos/{id}` | Estado y resultado del trabajo. |
| `POST /api/v1/procesamientos` | **Obsoleto (mock)**: devuelve activos fijos y no guarda nada. Se conserva para scripts de validación; la interfaz ya no lo usa. |

## Formato del archivo

JSON (lista o `{"interacciones": [...]}`), JSONL o CSV en UTF-8; máximo **5 MiB** (el proxy de la
VM corta en 10 MB) y **500** registros distintos. Por registro: `id` (o `id_mensaje`), `autor`
(≤150), `canal` (≤50), `fecha` ISO 8601 con hora y zona (`2026-10-19T14:10:00Z`), `texto`; `tipo`
(≤50) es opcional y un `tipo` vacío se ignora.

**Precedencia de metadatos:** `origen_comunidad`, `periodo_referencia` y `cierre_periodo` del
formulario prevalecen sobre los que traiga el archivo; la respuesta lista en
`metadatos_archivo_ignorados` los que difieren.

## Deduplicación e idempotencia

- Registros idénticos repetidos en el archivo: se conservan una vez (`registros_duplicados_omitidos`).
- Mismo `id` con contenido distinto en el archivo: error 422 con los registros implicados.
- Mismo `id` ya guardado con otro contenido: 409 `conflicto_mensaje`.
- Mismo lote (contenido y metadatos): devuelve el trabajo existente (`reutilizado: true`), en el
  estado en que esté. Sin cabecera, la clave es `lote-v1-<sha256 del lote canónico>`.
- Misma `Idempotency-Key` con contenido distinto: 409 `conflicto_idempotencia`.
- Mismos mensajes con otros metadatos (por ejemplo otro período): otro lote, sin duplicar mensajes.

## Errores

`detail = {codigo, mensaje, ayuda, errores?: [{registro, id, campo, motivo}], errores_totales?}`.
Nunca incluye valores del archivo.

| HTTP | `codigo` |
|---|---|
| 400 | `formato_no_soportado` |
| 409 | `conflicto_mensaje`, `conflicto_idempotencia` |
| 413 | `archivo_demasiado_grande` (o HTML del proxy si supera 10 MB) |
| 422 | `archivo_invalido`, `archivo_malformado`, `codificacion_invalida`, `sin_interacciones`, `demasiados_registros`, `lote_invalido` |
| 503 | `servicio_no_disponible` |

## Seguimiento en el panel

Estados `recibido → procesando → terminado | error`. El panel consulta cada 2 s durante 30 s y luego
cada 5 s; se detiene al terminar, fallar o salir de la pantalla. Tras 5 fallos de red seguidos
(con espera creciente) muestra "Reintentar consulta"; más de 120 s sin terminar muestra un aviso.
Un trabajo reutilizado ya terminado se muestra con su resultado. "Ver resultados en curaduría"
abre `/curaduria?trabajo=<id>` (`GET /api/curaduria/activos?trabajo=<id>`).

## Resultado

- `persistencia: {postgres: "guardado", activos: N}`: los activos se guardaron en PostgreSQL.
- `almacenamiento: {capa: "objetos_externos_oci", estado: "no_persistido"}`: el lote en sí no se copia a
  OCI; lo que se copia en Object Storage es cada activo aprobado (ver `docs/oci-object-storage.md`).
- Trabajos con error de IA: `error_codigo` y, si el proveedor rechazó la petición,
  `resultado.diagnostico`: estado HTTP, categoría y valores de catálogo; nunca texto del proveedor
  ni del lote (ver `docs/gemini-grafo-worker.md`).

## Datos cargados: ocultar o eliminar lotes (solo administradores)

Al final de **Ingesta de datos** está la sección «Datos cargados». Lista cada lote (origen · período ·
vía de entrada) con sus mensajes, contenidos y si está visible u oculto. API en
`backend/app/api/routes/datos.py`; lógica en `backend/app/services/datos_cargados.py`.

- **Ocultar del panel** (reversible): marca los trabajos del lote como de prueba (`es_prueba`). Dejan
  de contar en Resumen, Analítica, Interacciones y Curaduría; «Mostrar en el panel» lo revierte.
- **Eliminar** (irreversible): primero muestra qué se borrará y pide escribir `ELIMINAR`. Borra los
  trabajos, los contenidos de Curaduría con su historial y banners, y solo los mensajes que ningún otro
  lote usa. Se niega si hay trabajos del lote en proceso, y pide confirmar aparte si borraría
  contenidos aprobados. No toca lo ya copiado en OCI ni el historial importado de Discord.
