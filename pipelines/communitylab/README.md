# Pipeline de IA de CommunityLab (LangGraph + Gemini)

Grafo de LangGraph que convierte un lote de mensajes de la comunidad en análisis (sentimiento, tipo y tema),
borradores editoriales y alertas internas. Lo ejecuta el **worker** (`worker/`) con cada trabajo de la cola de
PostgreSQL, en modo `gemini` (producción) o `simulado` (sin red). El diagrama y las reglas del router están en
el [README principal](../../README.md#5-pipeline-de-ia-langgraph--gemini).

Autoría: orquestación y router de Paulo; análisis y puntuación con Gemini sobre el contrato acordado con
Santiago; prompts y generadores de Fabián; integración con el worker y la persistencia junto con Fredy.

## Módulos

| Módulo | Qué hace |
|---|---|
| `grafo.py` | Estado, nodos y recorrido: ingesta → análisis → puntuación → router → generadores o alerta → consolidación |
| `router_base.py` | Router determinista: bloqueo > duda recurrente > logro; cierre de período → resumen semanal |
| `analisis_gemini.py`, `componentes_gemini.py`, `gemini.py` | Análisis y puntuación con Gemini (salida estructurada, bloques con alias, presupuesto por lote) |
| `generadores/` | Post LinkedIn/X, FAQ o tip técnico, *Community Highlights*, versiones para redes y controles de fidelidad |
| `temas.py` | Agrupa temas casi iguales (tildes, artículos, plural) para Analítica y para detectar dudas recurrentes |
| `paquete.py` | Paquete de distribución con la forma del enunciado (respuesta de `POST /api/v1/procesar` y objeto en OCI) |
| `normalizador_discord.py`, `puente_discord.py`, `entregas_discord.py` | Discord en vivo: normalización, puente bandeja → API y entregas durables |
| `fechas.py`, `autores.py`, `diagnostico.py` | Fechas UTC, nombre visible de autores y diagnóstico seguro de errores del proveedor |
| `simulados.py`, `gemini_falso.py` | Dobles deterministas para pruebas y para el modo `simulado` |

## Ejecutar desde la raíz del repositorio

Python 3.12. Crear un entorno virtual e instalar las dependencias del módulo:

```sh
python -m venv .venv
# Activar .venv según el sistema antes de los siguientes comandos.
python -m pip install -r pipelines/communitylab/requirements-lock.txt
python -m unittest discover -s pipelines/communitylab/tests -v
python -m pipelines.communitylab
```

En Windows puede usarse `.venv\Scripts\python.exe` en lugar de `python`; en Linux/macOS, `.venv/bin/python`. No se necesita cuenta de LangGraph, clave Gemini, Docker ni base de datos para esta demo. La instalación descarga dependencias; las pruebas del grafo bloquean conexiones y usan datos sintéticos.

La demo escribe JSON en la terminal: **3 borradores simulados y 1 alerta interna**. No modifica archivos. `completado_local` indica que el lote se procesó sin errores. Los textos llevan la marca `SIMULADO — NO PUBLICAR`.

## Interfaz de integración

```python
from pipelines.communitylab import ejecutar_lote, preparar_entrada
from pipelines.communitylab.simulados import crear_componentes

# lote normalizado y señales manuales: ejemplos/entrada.json y senales_simuladas.json
salida = ejecutar_lote(lote, crear_componentes(senales))
```

`Componentes` agrupa los cinco callbacks (análisis, puntuación y tres generadores): `crear_componentes_gemini()` usa Gemini y `crear_componentes()` usa dobles simulados. Contrato original en [docs/historial](../../docs/historial/contratos/CONTRATO_PARA_SANTIAGO.md). `ejecutar_lote` desactiva trazas remotas únicamente durante su ejecución, sin alterar variables del proceso anfitrión. Las implementaciones externas que se inyecten son responsables de sus propias llamadas y reintentos.

## Recorrido y errores

Ingesta → análisis → puntuación → router → decisión pendiente → generador o alerta → siguiente decisión → consolidación. [Diagrama del grafo compilado](grafo.mmd).

Las decisiones se procesan secuencialmente. El lote vacío va directamente a consolidación sin consumir IA. Cada generador recibe solo sus fuentes, nunca el lote completo. Los IDs y fuentes se validan antes de aceptar su salida. Un error corta el flujo y devuelve `estado=error` sin activos ni alertas parciales; registra etapa y tipo, sin copiar mensajes de excepción potencialmente sensibles.

Los IDs son deterministas por comunidad/período/ruta/fuentes; no resuelven versionado ni idempotencia de base de datos. Se exige fecha/canal no vacíos, pero no se interpretan fechas ni se filtra el período. La ingesta debe entregar un lote ya seleccionado.

## Validación

Las pruebas de `pipelines/communitylab/tests/` cubren el router, el grafo, el cliente Gemini con transporte
falso, los generadores y la fidelidad, la agrupación de temas, el paquete del enunciado y el puente de Discord.
No usan red ni claves. El workflow «Grafo local» las ejecuta en cada PR, en Ubuntu y Windows con Python 3.12.

Referencia: [API oficial de StateGraph](https://reference.langchain.com/python/langgraph/graph/state/StateGraph). LangGraph está fijado en 1.2.12; dependencias transitivas en `requirements-lock.txt`.
