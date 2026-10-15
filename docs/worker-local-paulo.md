# Worker local de Paulo — 03/10/2026

Entrega en borrador sobre PR #16 (e6e4bb5), para revisión y pruebas del equipo.
La base del PR es `integracion-ian-tareck`, no `main`: requiere sus modelos,
routers y frontend. No fusionar hasta resolver los pendientes al final de esta guía.

## Qué implementa

El worker reserva un lote en PostgreSQL, ejecuta el grafo del PR14, guarda sus
activos y deja un estado consultable. Cada fallo de procesamiento termina ese
trabajo en `error` sin detener el siguiente. Se ejecuta como servicio de Compose,
con comprobación de salud, proceso hijo con límite de tiempo y apagado controlado.

El adaptador PostgreSQL y los endpoints nuevos son una propuesta de integración
para revisar con Fredy. Completan lo necesario para probar realmente la parte de
Paulo; no implican que Fredy ya haya aceptado este contrato.

## Contrato

`POST /api/v1/trabajos` recibe origen_comunidad, periodo_referencia,
cierre_periodo e interacciones con id, autor, fecha, canal y texto. `tipo` es opcional.
Responde 202 con procesamiento_id, estado y consulta. El GET de consulta devuelve
estado, intentos, historial, resultado y error_codigo. La UI de ingesta usa
`POST /api/mensajes/procesamientos` con archivo y los mismos metadatos.

Archivos UTF-8 JSON, JSONL y CSV: máximo 5 MiB y 500 registros normalizados.
Se admite id_mensaje como alias al cargar archivos. Registros exactamente iguales
se deduplican; un ID repetido con contenido distinto se rechaza. No se inventan
autores, fechas ni identificadores. Cada envío crea un trabajo nuevo: no hay
idempotencia entre solicitudes HTTP repetidas.

Estados: recibido → procesando → terminado/error. Las reservas duran 30 segundos,
se renuevan durante el procesamiento y tienen token por intento. Una reserva
vencida vuelve a recibido, hasta tres intentos; después pasa a error. Los errores
del procesador no se reintentan automáticamente. Tiempo máximo por lote: 120 s.
Dos workers usan FOR UPDATE SKIP LOCKED. Un token viejo no puede sobrescribir el
resultado. Los activos y el estado final se guardan en una sola transacción.
La ejecución es al menos una vez: tras una interrupción puede repetirse una llamada
a IA, aunque la persistencia final del trabajo no duplique sus activos.

Los activos quedan como generado, nunca aprobados automáticamente. Los bloqueos
se guardan en resultado.alertas_internas; no se envían a Discord ni se publican.
El dashboard heredado aún calcula sus alertas por heurística de texto/tipo y no
por esa lista. Sentimiento tampoco se calcula en este worker.

## Modos

WORKER_MODE=simulado usa señales sintéticas derivadas del campo tipo y marca los
resultados y títulos como simulados. Sirve para comprobar el circuito; no mide
calidad de IA. WORKER_MODE=openrouter requiere clave y conecta los nodos presentes
en PR16. Se corrigieron localmente sus errores silenciosos. Las pruebas de errores
del proveedor usan dobles; no se consumió una API ni se verificó su fallback real.
Tian debe revisar esta corrección junto con la versión diferente de su PR15.

## Ejecutar en este equipo

Requisitos: Git, Docker Desktop con contenedores Linux y Python 3.12. Desde un
clon nuevo, seleccionar `feature/worker-compose-paulo` y situarse en la raíz.
Los comandos siguientes son PowerShell. No requieren cuenta ni clave de OpenRouter.

Crear la configuración privada de prueba una sola vez. No sobrescribirla si ya
existe un volumen de este proyecto con otra contraseña. Los puertos 18092 y 15439
deben estar libres; detener antes otras pruebas que los estén usando.

```powershell
if (Test-Path .env.worker-local) { throw 'Ya existe .env.worker-local; conservar su configuración.' }
$claveLocal = [guid]::NewGuid().ToString('N')
@"
POSTGRES_USER=worker_local
POSTGRES_PASSWORD=$claveLocal
POSTGRES_DB=worker_local
DOCKER_PLATFORM=linux/amd64
HTTP_BIND_ADDRESS=127.0.0.1
HTTP_PORT=18092
WORKER_MODE=simulado
API_IMAGE=communitylab-worker-api:local
WEB_IMAGE=communitylab-worker-web:local
WORKER_IMAGE=communitylab-worker-runtime:local
"@ | Set-Content .env.worker-local -Encoding utf8
```

En equipo ARM cambiar DOCKER_PLATFORM a linux/arm64; esa plataforma no se validó
en esta entrega. Mantener el nombre del proyecto para aislar sus datos.

```powershell
docker compose --env-file .env.worker-local -p communitylab-paulo-worker -f docker-compose.yml -f compose.worker-local.yml up -d --build --wait --scale worker=2
```

Abrir http://127.0.0.1:18092. El puerto PostgreSQL local es 15439. El servicio
db-init crea las tablas que faltan, sin cargar datasets ni borrar datos existentes.
No sustituye un sistema de migraciones sobre una base de producción ya poblada.
El override local abre el puerto PostgreSQL solo en loopback: no usarlo en la VM.

## Repetir pruebas

Crear el entorno de pruebas en un clon nuevo:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest==9.1.1 httpx
```

Docker instala sus dependencias por separado. Ejecutar las pruebas PostgreSQL SOLO sobre esta base:
la fixture vacía mensajes, activos y trabajos_worker de worker_local.

```powershell
docker compose --env-file .env.worker-local -p communitylab-paulo-worker -f docker-compose.yml -f compose.worker-local.yml stop worker
$claveLocal = ((Get-Content .env.worker-local | Where-Object { $_ -match '^POSTGRES_PASSWORD=' }) -split '=', 2)[1]
$env:WORKER_TEST_DATABASE_URL="postgresql://worker_local:${claveLocal}@127.0.0.1:15439/worker_local"
.\.venv\Scripts\python.exe -m pytest worker/tests pipelines/communitylab/tests -q
docker compose --env-file .env.worker-local -p communitylab-paulo-worker -f docker-compose.yml -f compose.worker-local.yml up -d --wait --scale worker=2
.\.venv\Scripts\python.exe -m worker.tests.smoke_compose
```

La prueba HTTP añade datos sintéticos y guarda evidencia fuera del clon.
Para apagar conservando el volumen:

```powershell
docker compose --env-file .env.worker-local -p communitylab-paulo-worker -f docker-compose.yml -f compose.worker-local.yml down
```

## Integración pendiente

Revisar primero con Fredy la tabla trabajos_worker, API asíncrona, límites y política
de recuperación. Coordinar con Tian agent_nodes.py y PR15; con Ian los formularios
y las correcciones del frontend. Tarek/Fredy pueden consolidarlo en la rama del PR16
y repetir las pruebas antes del merge. No aplicar este cambio directamente sobre
main sin incorporar primero el código base del PR16.

El endpoint anterior /api/v1/procesamientos conserva su respuesta mock y no
alimenta esta cola. Se mantiene para no sustituir silenciosamente su contrato
sin el acuerdo de backend; la ingesta del frontend sí usa la cola nueva.
OCI, VM/ARM64, modelos externos y carga de producción quedan fuera de lo validado.

## Pendientes conocidos: no listo para fusionar

- F14: el worker admite autor de más de 150 caracteres y canal/tipo de más de 50,
  pero el esquema de respuesta de Interacciones los rechaza. Se reprodujo POST
  202 seguido de GET 500 con canal de 51 caracteres. Falta validar antes de guardar.
- F21: un ID existente con otro tipo se acepta y conserva el tipo anterior en
  mensajes. Falta acordar si tipo es inmutable o pertenece a cada análisis.
- F15: este cambio depende de #16. Tras integrar o actualizar su base, hay que
  revisar el diff, rebasar cuando corresponda y volver a probar antes de apuntar a main.
- F08/F10: combinar #15/#10 requiere acordar agent_nodes.py y requirements.txt;
  no resolver el conflicto reemplazando archivos completos y perdiendo validaciones.
- En la UI aún falta paginación de curaduría y alinear el botón de aprobar con
  generado → revisado → aprobado. Los KPIs siguen usando heurísticas heredadas.

Los IDs F corresponden a la auditoría del 03/10/2026. Se comprobaron 52 pruebas
existentes (con cinco advertencias heredadas de Pydantic), construcción de imágenes
y cuatro lotes/12 activos con dos workers en modo simulado. Las pruebas ampliadas
encontraron F14/F21: un resultado verde de la suite existente no cubre esos casos.
Este borrador incluye también correcciones locales de imports, dependencias,
lint e IA necesarias para probar el conjunto; Ian, Fredy y Tian deben revisarlas.
