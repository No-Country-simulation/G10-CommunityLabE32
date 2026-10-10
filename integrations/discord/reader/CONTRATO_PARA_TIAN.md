# Evento fuente de Discord para Santiago

Formato técnico propuesto el 07/10/2026, pendiente de acuerdo. La división de
responsabilidades sí fue confirmada por Santiago en el mensaje compartido por Paulo. El lector de Paulo entrega un objeto
por mensaje; no construye aún un lote `IngestaRequest` ni una `Interaccion` final.
El ejemplo de `examples/mensaje_ficticio.json` usa exclusivamente datos ficticios.

| Campo | Tipo | Significado |
|---|---|---|
| schema_version | cadena | `discord-source-v1` |
| message_id | cadena | ID original del mensaje; conservar para trazabilidad |
| guild_id | cadena | ID del servidor autorizado |
| channel_id | cadena | ID del canal autorizado |
| author_id | cadena | ID estable del autor, sin copiar su nombre visible |
| created_at | cadena | Fecha original en ISO 8601 con zona UTC |
| content | cadena | Texto original; no se recorta ni clasifica |

Entrega inicial mediante JSONL exportado desde la bandeja local. Cada línea es un
objeto con estos campos, en orden de recepción persistida. Exportar varias veces
incluye de nuevo los mensajes anteriores; el consumidor debe deduplicar por servidor
e ID. El lector no promete entrega exactamente una vez al pipeline ni acusa recibo
de consumo. No leer el archivo mientras todavía se está exportando.

## Normalización que corresponde a Tian

En el contrato de main `61ddc4b`, `Interaccion` requiere `id`, `autor`,
`canal`, `tipo`, `fecha` y `texto`. `autor` admite hasta 150 caracteres y `canal`
y `tipo` hasta 50. La correspondencia propuesta es:

- `message_id` hacia `id`, acordando si se agrega un prefijo para evitar colisiones
  con IDs de lotes de otras fuentes.
- `author_id` hacia una identidad estable en `autor`. Acordar seudónimos si hace
  falta mostrarlos en pantalla. Un ID no es anonimización ni consentimiento.
- `channel_id` hacia `canal`, o hacia un alias acordado que respete el límite.
- `created_at` hacia `fecha` y `content` hacia `texto`.
- `tipo`, `origen_comunidad` y `periodo_referencia`: definición de Tian y el equipo.
  No inferir que `tipo` sea la clasificación de IA.

Tian deberá definir validaciones, registros rechazados y agrupación de mensajes.
La conexión al worker depende del contrato definitivo con backend: no enviar esta
salida directamente a `/api/v1/procesamientos` suponiendo que ya procesa con IA.

## Criterio de cierre conjunto

Un mensaje ficticio publicado por una persona en un canal de pruebas autorizado
debe guardarse una sola vez, normalizarse al esquema acordado y llegar al flujo de
procesamiento correcto. Un mensaje de canal no autorizado, privado o de un bot no
debe entrar. Esta comprobación conjunta todavía no se ha realizado.
