# Conexión de Santiago — propuesta técnica local v1

La distribución de responsabilidades fue aceptada; este contrato concreto debe validarse conjuntamente. No se le atribuye a Santiago ninguna de las funciones simuladas.

## Entrada desde José

`preparar_entrada(interacciones, origen_comunidad=..., periodo_referencia=..., cierre_periodo=True/False)` acepta una lista de diccionarios normalizados o modelos Pydantic con `model_dump()`. Conserva `id`, `autor`, `canal`, `fecha`, `texto` y opcionalmente `tipo`. La metadata debe proporcionarla el llamador; el cierre del período nunca se infiere del texto. El ejemplo completo está en `ejemplos/entrada.json`.

El grafo exige strings no vacíos e IDs únicos. La ingesta de José puede aceptar fecha/canal vacíos; en ese caso el grafo lo rechaza explícitamente y debe resolverse en la frontera de ingesta. No se inventan esos datos. La ingesta hace normalización y deduplicación; este adaptador solo recibe su salida.

## Funciones que aporta Santiago

| Función | Entrada | Salida |
|---|---|---|
| `analizar(lote)` | Metadata del lote y lista de interacciones. | Mapa por ID con `es_logro`, `es_duda`, `es_bloqueo` (booleanos) y `tema` (string). |
| `puntuar(peticion)` | `{"lote": lote, "analisis": mapa}` | Mapa por ID con un número finito de relevancia entre 0 y 1. |
| `generar_post(peticion)` | Ruta, formato, comunidad, período, IDs fuente e interacciones seleccionadas. | `{"copy": "texto no vacío", "fuentes": ["id", ...]}`. |
| `generar_faq(peticion)` | Igual, para las dudas recurrentes seleccionadas. | Mismo formato. |
| `generar_highlights(peticion)` | Igual, para el resumen del período sin bloqueos. | Mismo formato. |

Ejemplo de análisis:

```json
{"m-01": {"es_logro": true, "es_duda": false, "es_bloqueo": false, "tema": "empleo"}}
```

Ejemplo de puntuación:

```json
{"m-01": 0.95}
```

Debe haber exactamente una entrada por cada ID recibido, sin omisiones ni IDs inventados. Una duda requiere tema no vacío; las dudas de un mismo asunto deben compartir una clave de tema. El grafo junta análisis y puntuación para alimentar el router existente. El generador debe devolver exactamente las fuentes recibidas (se admite otro orden), sin duplicarlas o sustituirlas.

Ejemplo de conexión (una vez que Santiago entregue sus funciones síncronas):

```python
from pipelines.communitylab import Componentes, ejecutar_lote

componentes = Componentes(
    analizar=analizar_real,
    puntuar=puntuar_real,
    generar_post=post_real,
    generar_faq=faq_real,
    generar_highlights=highlights_real,
    simulado=False,
)
salida = ejecutar_lote(lote_normalizado, componentes)
```

Las funciones anteriores son nombres ilustrativos, no módulos reales incluidos. Para probar hoy se usa `crear_componentes` de `simulados.py` y `simulado=True`. La bandera la declara el integrador: no certifica por sí misma que se haya llamado a Gemini. No se soportan callbacks async directamente en esta versión; deberán adaptarse o acordarse una integración asíncrona posterior.

## Reglas conservadas del router de Paulo

- Bloqueo tiene prioridad y queda fuera de todo contenido.
- Relevancia mínima 0.60, configurable.
- Duda recurrente: tema normalizado compartido por al menos 2 autores distintos.
- Logro: si es elegible y no fue clasificado como duda recurrente.
- Highlights: cierre explícito del período con fuentes relevantes sin bloqueos; puede incluir fuentes ya usadas en post o FAQ.

Estos valores siguen siendo provisionales. La sugerencia previa de Santiago de utilizar `tipo` no se convierte aquí en una regla que eluda el análisis.

## Salida para el futuro worker

`ejecutar_lote` devuelve `estado`, `simulado`, metadata, `activos_distribucion_generados`, `alertas_internas`, referencias `fuentes`, `enrutamiento`, `errores`, `almacenamiento` y `traza`.

El estado exitoso es `completado_local`; cada activo permanece en `borrador`. Las alertas tienen `visibilidad=interna`. Si cualquier componente falla, devuelve `estado=error` y no entrega activos ni alertas parciales. El enrutamiento puede conservar decisiones para diagnóstico, pero no representa resultados generados. Los errores identifican nodo y tipo; nunca incluyen automáticamente el texto de una excepción externa.

El worker deberá traducir el resultado a los estados y persistencia que acuerden Paulo y Fredy. Este grafo no publica ni guarda en PostgreSQL/OCI. La política de timeout/reintentos de Gemini corresponde a Santiago; si su función termina con excepción, el grafo marca el lote como fallido. Las pruebas reales conjuntas y en VM permanecen pendientes.
