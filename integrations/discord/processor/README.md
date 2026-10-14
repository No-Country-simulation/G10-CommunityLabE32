# Procesador integrado Fabián + Paulo + Gemini

## Comportamiento

Un mensaje autorizado pasa por el análisis local TF-IDF de Fabián. Su hipótesis,
no vinculante, acompaña al mensaje a Gemini; Gemini confirma/corrige señales y
redacta la salida. Se aplica el validador estricto discord-decision-v1 antes de
que el transporte persista o publique. Solo hay una decisión final y una consulta
por evento, sin reintentos automáticos ni cambio de modelos.

- Duda sin bloqueo: responder al mensaje original.
- Bloqueo (incluso combinado con duda/logro): solo alerta interna.
- Logro o charla: registrar sin responder.
- Error, timeout, respuesta incompleta o inválida: failed_processing, sin envío.
- Un procesador que lance ReviewRequired deja needs_review, sin reintento automático.
  El estado es visible en status; no se implementa una interfaz de aprobación.

El adaptador integrado usa Gemini para resolver la ambigüedad de la hipótesis
local; la marca local de revisión semántica no equivale a aprobación humana.
No existe garantía de exactitud semántica: la evaluación real y revisión de las
respuestas sigue siendo necesaria.

El contexto conversacional y los modelos neuronales opcionales de Fabián siguen
siendo herramientas separadas. No se activan en este adaptador: no descarga pesos,
no retiene conversaciones y procesa reintentos del mismo mensaje de forma
independiente. El análisis local no reduce aquí las llamadas a Gemini. No se envían
IDs ni nombres de autor como metadatos; sí se transmite el contenido del mensaje.

## Instalación y ejecución

Python 3.12. Desde la raíz del repositorio:

```powershell
python -m pip install -r integrations/discord/bot/requirements.txt -r integrations/discord/processor/requirements.txt
$env:PYTHONPATH = "$PWD/integrations/discord/bot;$PWD/integrations/discord/processor"
$env:COMMUNITYLAB_GEMINI_ENABLE = '1'
$env:COMMUNITYLAB_GEMINI_MODEL = 'gemini-3.5-flash-lite'
python -B -m bot_discord --config RUTA_CONFIG_LOCAL listen --connect --processor community_processor.integrated:procesar
```

GEMINI_API_KEY y DISCORD_BOT_TOKEN deben existir en el entorno, sin guardarlos en
el repositorio ni pegarlos en comandos literales. En Linux separar PYTHONPATH con
`:`. La configuración es la del transporte existente: servidor, canales de entrada,
canal interno separado y roles/usuarios internos autorizados. Copiar y completar
config.example.json fuera del repositorio. El modelo es configurable, sin fallback
automático. Tener una clave no garantiza cuota ni acceso al modelo.

El módulo legacy community_processor:procesar mantiene el proveedor OpenRouter
para compatibilidad con las pruebas previas; no es la entrada recomendada para
esta entrega integrada.

## Pruebas sin servicios externos

```text
python -m pip install -r integrations/discord/bot/requirements-validacion.lock.txt -r integrations/discord/processor/requirements.txt
python -B integrations/discord/processor/tools/validate.py --junit resultados.xml
```

Incluye clasificador, procesador, lector, transporte, grafo y worker. Sin una BD
configurada se omiten los casos PostgreSQL. Para el conjunto completo, usar una
BD DESECHABLE worker_local en 127.0.0.1:15439, establecer WORKER_TEST_DATABASE_URL
y añadir --postgres. Las pruebas limpian sus tablas; el ejecutor rechaza otros
destinos. Red externa bloqueada, Discord/Gemini simulados. El workflow integrado
incluye Windows/Linux y un job Linux con PostgreSQL; todavía debe correr en GitHub
cuando se publique la entrega.

## Pruebas reales, opt-in

```text
python -B integrations/discord/processor/tools/live.py check-ia --connect --evidence-dir RUTA_EVIDENCIAS
python -B integrations/discord/processor/tools/live.py evaluate --connect --evidence-dir RUTA_EVIDENCIAS
python -B integrations/discord/processor/tools/live.py listen --connect --config RUTA_CONFIG_LOCAL --evidence-dir RUTA_EVIDENCIAS
```

check-ia hace una consulta ficticia; evaluate ejecuta hasta 20 casos ES/PT y se
interrumpe ante errores del proveedor/contrato. Consumirán cuota. listen también
envía respuestas y alertas reales; usar servidor de pruebas. Solo recibe mensajes
nuevos tras estado=listo. Ctrl+C termina y guarda un informe de estados sin texto
de mensajes ni credenciales. status consulta el almacenamiento sin conectarse.

Antes de cerrar la actividad: evaluar calidad, probar los tres tipos de mensaje,
canales excluidos, bot/webhook, pérdida de permisos y reiniciar sin repetir envíos.
Una batería automática no demuestra estas propiedades con permisos reales.
