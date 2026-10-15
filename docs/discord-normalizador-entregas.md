# Normalizador y entrega durable de Discord

Este cambio completa la entrega local JSONL -> normalizador -> HTTP -> cola PostgreSQL.
No añade un servicio permanente, no configura proveedores de IA ni despliega la VM.

## Ejecutar

Desde la raíz, después de levantar API, PostgreSQL y worker:

```text
python -B pipelines/communitylab/prueba_integracion_discord.py --archivo exports/mensajes.jsonl --estado datos/entregas.sqlite3 --url http://127.0.0.1:8080/api/v1/trabajos --periodo 2026-W42
```

Conserve el mismo `--estado` para exportaciones sucesivas del mismo origen/período y destino,
aunque cambie el nombre del JSONL. Por defecto se usa `ARCHIVO.entregas.sqlite3`.
El JSONL solo se lee; SQLite contiene payloads y estados y debe estar en almacenamiento
privado y persistente. No comparta ni suba sus datos a Git. No borre este archivo para reintentar.
La simulación usa archivos temporales salvo que se indique un `--estado` explícito.

- Primero se validan todos los registros. Si alguno es inválido, no se envía un lote parcial.
- Las fechas requieren `YYYY-MM-DDTHH:MM:SS[.fracción](Z|±HH:MM)`, con hasta seis decimales.
  Se comprueba el calendario, se exige zona explícita y Discord se normaliza a UTC.
- Se guardan los lotes exactos antes del primer POST, hasta 500 mensajes por lote.
- Se envía una clave estable `Idempotency-Key`. Si cae después del POST y antes del checkpoint,
  se reenvía el mismo payload y clave: PostgreSQL devuelve el mismo trabajo.
- Tras recibir el ID, se guarda y se retoma su consulta al reiniciar. Solo `terminado`
  se considera completado. Un trabajo `error` requiere revisión; no se recrea automáticamente.
- Los IDs ya planificados no se agrupan de nuevo cuando crece la exportación. Un ID con
  contenido distinto se rechaza. Esto requiere conservar y reutilizar el SQLite.
- `--sin-esperar` confirma aceptación, no finalización. Una ejecución posterior sin esa
  opción consulta el mismo trabajo y actualiza su estado.
- `--cierre` corresponde a una exportación final e inmutable del período. No cambiar esa
  opción ni añadir mensajes a un período que ya se planificó con cierre. Para captura
  incremental use el modo sin cierre; la orquestación de cierre continuo queda fuera de este CLI.

## Backend e idempotencia

Sin cabecera, `/api/v1/trabajos` calcula la clave del lote validado: ordena los mensajes
por ID y canoniza las fechas a UTC. Repetir el mismo lote, aun concurrentemente o tras
reiniciar, devuelve su trabajo y estado actuales. Cambiar origen, período, cierre o
contenido define otro lote. No se hace deduplicación global entre lotes parcialmente
solapados: para exportaciones crecientes se utiliza el estado durable del puente.

Una cabecera explícita permite una identidad definida por el cliente. Reutilizarla con
otro contenido devuelve HTTP 409. Un reprocesamiento intencional puede usar una clave
nueva, tras revisar sus efectos; los cambios de contenido de un ID fuente siguen prohibidos.
La idempotencia no promete recuperarse de pérdida de la base de datos del servidor.

La API valida fechas antes de encolar (HTTP 422) y la cola también valida llamadas directas.
La respuesta de un reenvío informa el estado actual, no siempre `recibido`.

## Migración y compatibilidad

`python -m worker.init_db` aplica una migración aditiva e idempotente: añade
`clave_idempotencia` nullable e índice único a `trabajos_worker`, sin borrar datos.
Ejecutar db-init antes de actualizar API y workers. Los trabajos históricos conservan
su ID y resultado; no se les asignan claves retroactivamente, por lo que el sistema
no puede reconocer automáticamente reenvíos de trabajos anteriores a la migración.
Respaldar PostgreSQL antes de actualizar producción. No usar `down -v` en la VM.

## Verificación

Las pruebas del repositorio cubren fechas, exportaciones crecientes, lotes pendientes,
reinicios de la cola local, fallo entre POST y checkpoint, conservación del JSONL,
envíos concurrentes en PostgreSQL, ausencia de activos duplicados por reenvío,
HTTP 409/422 y migración sobre una tabla existente. Se integran en los workflows
de grafo, bot y procesador. Discord/IA externos se simulan en esas suites.
