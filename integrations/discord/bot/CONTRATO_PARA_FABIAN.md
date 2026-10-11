# Propuesta de intercambio con Fabián

La división de responsabilidades fue aceptada. Este contrato técnico es una
propuesta del 08/10/2026 pendiente de confirmación con Fabián.

Paulo entrega el transporte, control de acceso, persistencia, deduplicación y
ejecución de respuestas/alertas. Fabián entrega clasificación, prompts y contenido.
Ambos validan la integración. La entrega compartida está prevista para el 09/10.

## Función de conexión

Un módulo importable, por ejemplo `fabian_adapter.py`, debe exponer:

```python
async def procesar(evento: dict) -> dict:
    # Invocar aquí la lógica de Fabián y devolver discord-decision-v1.
    # No llamar a Discord ni realizar publicaciones desde esta función.
    raise NotImplementedError("Incorporar la lógica de Fabián")
```

El ejemplo es una interfaz, no una implementación terminada. El transporte se
inicia con `--processor fabian_adapter:procesar`. El procesador recibe una copia
del evento y no puede cambiar el destino alterándola. No bloquear el event loop:
usar cliente HTTP async o `asyncio.to_thread` para llamadas síncronas. Configurar
timeout propio en el proveedor y respetar cancelación. El transporte aplica
`processor_timeout` (60 segundos por defecto) a la función cooperativa asíncrona.

## Entrada exacta

```json
{
  "schema_version": "discord-source-v1",
  "message_id": "600",
  "guild_id": "100",
  "channel_id": "200",
  "author_id": "700",
  "created_at": "2026-10-08T12:00:00+00:00",
  "content": "¿Cómo puedo manejar una excepción en Python?"
}
```

Todos los IDs son cadenas decimales. La fecha incluye zona horaria. Los IDs de
este documento son ficticios. Se conserva texto original y no se envían nombre
visible, roles, token ni datos de otros mensajes. Fabián decide qué contexto
adicional necesita; no se inventa acceso a historial ni una base de conocimiento.

## Salida exacta

```json
{
  "schema_version": "discord-decision-v1",
  "message_id": "600",
  "es_duda": true,
  "es_logro": false,
  "es_bloqueo": false,
  "tema": "python",
  "respuesta": "Respuesta técnica elaborada por la lógica de Fabián.",
  "alerta": ""
}
```

| Campo | Regla |
|---|---|
| `schema_version` | Exactamente `discord-decision-v1`. |
| `message_id` | El mismo ID de la entrada, sin inventar ni cambiar fuentes. |
| `es_duda`, `es_logro`, `es_bloqueo` | Booleanos JSON, no cadenas. Los nombres coinciden con las señales del repositorio. |
| `tema` | Texto no vacío, hasta 100 unidades UTF-16. |
| `respuesta` | Para duda sin bloqueo: texto no vacío, hasta 1900 unidades UTF-16. En los demás casos, cadena vacía. |
| `alerta` | Para bloqueo: resumen interno no vacío, hasta 1700 unidades UTF-16. En los demás casos, cadena vacía. |

No se aceptan campos extra, destinos, archivos ni instrucciones para ejecutar
código. No se recortan respuestas largas silenciosamente: una salida inválida
queda como fallo de contrato y no se publica. Los límites conservadores dejan
espacio para el encabezado y enlace de fuente de las alertas; emojis pueden
ocupar dos unidades UTF-16.

## Decisiones de transporte

| Señales | Acción de Paulo |
|---|---|
| Bloqueo, con o sin duda/logro | Solo alerta al canal interno con enlace al mensaje fuente. Nunca respuesta pública. |
| Duda sin bloqueo | Respuesta al mensaje original en su canal autorizado. |
| Logro/testimonio sin duda ni bloqueo | Guardar detección localmente, sin publicación automática. |
| Ninguna señal | Guardar resultado sin responder. |

Si una señal combina duda y logro sin bloqueo, se responde la duda; el logro
también queda registrado. Si Fabián devuelve simultáneamente bloqueo y texto de
respuesta pública, se rechaza toda la decisión: debe corregirla antes de reintentar.

`es_logro` se utiliza como señal de testimonio/logro para alinearse con el
repositorio; confirmar juntos si Fabián necesita una distinción adicional.
El bot no interpreta esta señal como consentimiento para publicar.

## Errores y responsabilidades

Si el proveedor falla o no hay resultado válido, la función debe lanzar una
excepción; no inventar éxito ni un mensaje genérico que termine publicado.
El transporte guarda un código de error sin texto de la excepción y continúa con
el siguiente mensaje. Los reintentos de procesamiento son explícitos para evitar
bucles y consumo inesperado de IA. La función no debe tener efectos externos de
publicación, ya que una ejecución interrumpida antes del envío puede repetirse.

No conectar automáticamente esta salida a los endpoints de ingesta del backend:
el bot responde por mensaje, mientras el pipeline existente genera borradores de
contenido y alertas por lote. Su unión definitiva requiere acordar el adaptador
con Fabián y, cuando afecte la ingesta, con Santiago/backend.

## Prueba de cierre con ambos

1. Una duda ficticia recibe una sola respuesta al mensaje correcto.
2. Un testimonio queda detectado sin publicación automática.
3. Un bloqueo genera una sola alerta, visible únicamente en el destino interno.
4. Bots, webhooks, DMs y otros canales no activan el procesamiento.
5. Al repetir un evento o reiniciar el bot no se repite un envío confirmado.
6. Confirmar permisos reales y un fallo controlado del procesador sin exponer datos.

Estas comprobaciones ya tienen pruebas automatizadas con dobles locales. La
prueba conjunta con la lógica final de Fabián y Discord real todavía está pendiente.
