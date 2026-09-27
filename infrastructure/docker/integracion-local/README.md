# Preparar Docker Compose con imágenes ARM64: proxy, web, api, worker y postgres (healthchecks, reinicio automático y red privada)

## Aporte para revisión
Entorno de integración local reproducible. Depende de chore/validacion-contrato-fastapi, cuyos cambios están incluidos en esta rama. Ejecuta backend/main.py (mock), la web real, PostgreSQL, Nginx y un worker sonda. No sustituye el Compose raíz ni decide el backend oficial.

Desde la raíz, con Python 3 y Docker activos:

```sh
python infrastructure/docker/integracion-local/probar_integracion.py --platform linux/amd64
python infrastructure/docker/integracion-local/probar_integracion.py --platform linux/arm64
```

El script crea credenciales efímeras, puerto aleatorio en localhost, redes y volumen exclusivos. Construye las imágenes (frontend con lint y build), ejecuta las comprobaciones y retira sus contenedores y volumen incluso ante fallos. Las imágenes quedan como caché. Solo elimina recursos del proyecto temporal de prueba. Registra JSON y logs bajo docs/ junto al script; no se versionan los logs ni los resultados generados.

En máquinas AMD64, ARM64 requiere emulación disponible en Docker Desktop. Esto no prueba el despliegue en OCI.

## Configuración
- Cinco servicios con restart: unless-stopped y healthchecks.
- Solo Nginx publica un puerto en localhost; API, PostgreSQL, web y worker no publican puertos del host.
- Red database interna; API y worker comparten acceso a PostgreSQL. La sonda comprueba SELECT 1, no ejecuta el procesamiento real.
- Las variables de base de datos proceden del entorno de prueba; no usar secretos personales ni subir .env.
- El override compose.integracion.yml construye las aplicaciones desde este repositorio y ajusta sus healthchecks. El script usa siempre ambos archivos Compose; no ejecutar el archivo base aislado como si fuese el despliegue final.
- API_PROXY_TARGET=http://api:8000 se fija durante el build de la web. En desarrollo sin Docker, el reenvío usa localhost:8000 salvo configuración explícita.

## Pendiente de acuerdo con el equipo
backend/Dockerfile de esta propuesta arranca main:app. La rama de infraestructura existente propone backend.app.main:app en la misma ruta. Debe resolverse ese archivo común antes de fusionar. Las implementaciones Python no se modifican. Una arquitectura modular futura puede conservarse incorporando el contrato acordado; este PR no realiza esa migración.

El mock entrega contenido fijo y usa id; la incompatibilidad con id_mensaje se documenta, no se corrige aquí. PostgreSQL se verifica con una tabla de prueba independiente; el backend no guarda datos. Worker es sonda, OCI simulado, sin Gemini. HTTP/contrato comprobados; no se certifica interacción de navegador ni pipeline de producción. No declarar la actividad integral concluida por estas pruebas.

## Evidencia de esta entrega

Verificación local del 25 de septiembre de 2026: 34 comprobaciones aprobadas en linux/amd64 y 34 en linux/arm64 mediante emulación. Ambas ejecuciones terminaron con limpieza correcta. Incluyen salud de cinco servicios, contrato HTTP mock, conexión web/API, persistencia SQL de prueba y recuperación tras recrear servicios. Los informes JSON permanecen locales y están ignorados por Git. Esto no valida la VM, el worker real, Gemini ni la persistencia del backend real.
