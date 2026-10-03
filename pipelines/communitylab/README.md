# Grafo local de CommunityLab — aporte de Paulo

Implementa la parte de orquestación de «Construir el grafo en LangGraph en la VM» (semana 2, Paulo y Santiago). El reparto fue aceptado por Santiago; el contrato técnico concreto sigue pendiente de validación conjunta. Esta entrega se mantiene independiente para poder revisarla antes de conectar los componentes reales.

## Alcance implementado

- Estado compartido: lote, fuentes, análisis, puntuaciones, decisiones, borradores, alertas, errores y traza.
- Grafo real de LangGraph con ingesta, análisis, puntuación, router, selección condicional de generadores y consolidación.
- Adaptador para la salida normalizada de José (`list[dict]` o modelos Pydantic `Interaccion`).
- Router de cuatro rutas de Paulo; bloqueo siempre queda fuera de los generadores de contenido.
- Interfaces inyectables para análisis, puntuación y generadores de Santiago. Los incluidos aquí son dobles de prueba explícitamente simulados.
- Consolidación de borradores y alertas internas con referencias a las fuentes.

Santiago conserva la implementación de análisis y generación Gemini y la coordinación del puntuador con José. Los prompts son de Fabian. Worker, estados de trabajos y persistencia pertenecen a la actividad con Fredy.

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

La demo escribe JSON en la terminal: **3 borradores simulados y 1 alerta interna**. No modifica archivos. `completado_local` indica éxito de esa ejecución; no significa que la actividad del Plan esté terminada. Los textos llevan la marca `SIMULADO — NO PUBLICAR`.

## Interfaz de integración

```python
from pipelines.communitylab import ejecutar_lote, preparar_entrada
from pipelines.communitylab.simulados import crear_componentes

# lote normalizado y señales manuales: ejemplos/entrada.json y senales_simuladas.json
salida = ejecutar_lote(lote, crear_componentes(senales))
```

`Componentes` permite reemplazar los cinco callbacks síncronos de prueba por las funciones de Santiago. Ver [contrato](CONTRATO_PARA_SANTIAGO.md). `ejecutar_lote` desactiva trazas remotas únicamente durante su ejecución, sin alterar variables del proceso anfitrión. Las implementaciones externas que se inyecten son responsables de sus propias llamadas y reintentos.

## Recorrido y errores

Ingesta → análisis → puntuación → router → decisión pendiente → generador o alerta → siguiente decisión → consolidación. [Diagrama del grafo compilado](grafo.mmd).

Las decisiones se procesan secuencialmente. El lote vacío va directamente a consolidación sin consumir IA. Cada generador recibe solo sus fuentes, nunca el lote completo. Los IDs y fuentes se validan antes de aceptar su salida. Un error corta el flujo y devuelve `estado=error` sin activos ni alertas parciales; registra etapa y tipo, sin copiar mensajes de excepción potencialmente sensibles.

Los IDs son deterministas por comunidad/período/ruta/fuentes; no resuelven versionado ni idempotencia de base de datos. Se exige fecha/canal no vacíos, pero no se interpretan fechas ni se filtra el período. La ingesta debe entregar un lote ya seleccionado.

## Pendientes antes de integrar

1. **José / PR #10:** su puntuador devuelve un total de hasta 40 y destaca desde 12; el contrato local espera 0–1 y el router usa 0.60. Acordar conversión y criterio, no conectar directamente. Las señales semánticas siguen pendientes de Santiago.
2. **Fredy / PR #12:** unificar `almacenamiento_oci` frente a `almacenamiento`. La salida de este grafo es interna y declara `no_persistido`; no sustituye `IngestaResponse`.
3. **Ian / PR #13:** adaptar `post_linkedin_x`, `faq_tip_tecnico`, `community_highlights` y estado `borrador` a los formatos/estados de curaduría y definir `titulo` y persistencia.
4. Acordar `cierre_periodo`, reglas provisionales del router y fuentes; conectar los callbacks reales, probar el flujo completo y después la VM.
5. Conectar el worker y Docker en una integración posterior. Los contenedores actuales no instalan ni invocan este módulo.

No se modifica el backend, el frontend, Compose ni el worker existente. El módulo no se importa automáticamente en servicios actuales. La actividad compartida no se marca completa y no incluye IA real ni despliegue.

## Validación

28 pruebas autocontenidas: cuatro rutas, exclusión de bloqueos, lotes vacíos/sin rutas, contratos inválidos, errores, trazabilidad, independencia entre ejecuciones, 100 logros, importación como paquete y demo desde raíz. El workflow dedicado las ejecuta en Ubuntu y Windows con Python 3.12. Estas pruebas no requieren la carpeta local de Paulo ni ramas pendientes.

El trabajo local previo comprobó además JSON/CSV contra una copia del módulo de ingesta de José; esa evidencia no sustituye pruebas con la versión conjunta final de los PR #10/#12/#13.

`router_base.py` conserva la lógica del router local original; se normalizaron finales de línea a LF. SHA-256 del archivo de origen: `2DB9865ED44F1D07BF44A2D57DFEC7F58696961BD1D33D8784F4EA60A577C08C`. Los umbrales, prioridad bloqueo > duda recurrente > logro y agregación del período siguen siendo propuestas pendientes de validación técnica.

Referencia: [API oficial de StateGraph](https://reference.langchain.com/python/langgraph/graph/state/StateGraph). LangGraph está fijado en 1.2.12; dependencias transitivas en `requirements-lock.txt`.
