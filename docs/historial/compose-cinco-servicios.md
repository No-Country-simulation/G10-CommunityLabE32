# Preparar Docker Compose ARM64: cinco servicios

Actividad 7 de la semana 1 (22–24/09), Fredy Pachon y Paulo Andres Escobar Solorzano. Esta entrega completa la configuración conjunta para la fase mock sobre la base `main` a4ba9d1.

## Base y coordinación

El 24/09 Tareck dejó la estructura del backend/PostgreSQL y solicitó la configuración Docker y las pruebas. El 25–26/09 incorporó el contrato mock de Ian en la estructura modular. Esa versión llegó a main mediante el PR #7. El 26/09 Paulo comunicó que la integración restante se uniría conjuntamente el lunes.

Esta propuesta usa esa base integrada: conserva sin cambios `backend/Dockerfile`, `backend/app/` y `backend/main.py`. Docker sigue arrancando `backend.app.main:app`, con `POST /api/v1/procesamientos` y `/health`. No incorpora los avances posteriores de SQLite/ingesta que siguen en ramas separadas. No representa una aprobación nueva de Tareck: requiere revisión del equipo antes de fusionar.

## Cambios

- Compose raíz de cinco servicios: proxy Nginx, web Next.js, API modular FastAPI, worker sonda y PostgreSQL.
- Healthchecks y `restart: unless-stopped` para los cinco servicios; PostgreSQL con volumen persistente.
- PostgreSQL solo conectado a la red `database` con `internal: true`. API y worker acceden a ella; web y proxy no pertenecen a esa red.
- Solo proxy publica un puerto del host, restringido por defecto a `127.0.0.1:8080`. API, web, worker y PostgreSQL no publican puertos.
- La red `frontend` también es interna. El proxy se conecta adicionalmente a `outbound` para admitir el puerto publicado en Docker Desktop; API y worker conservan salida para futuras integraciones externas. PostgreSQL no tiene salida externa.
- Nginx conserva el prefijo `/api/` y resuelve los servicios por DNS de Docker también después de recrearlos.
- Web en Node 22 con instalación reproducible `npm ci`, lint/build y usuario no root. El reenvío de Next.js usa `http://api:8000` dentro de Docker.
- Plataformas configurables: ARM64 por defecto; AMD64 para desarrollo o pruebas.
- `.env.example` sin contraseña y contextos Docker que excluyen credenciales y dependencias locales.

## Arranque manual local

1. Copiar `.env.example` como `.env` en la raíz.
2. Definir una contraseña propia en `POSTGRES_PASSWORD`; nunca publicar `.env`.
3. Mantener `DOCKER_PLATFORM=linux/arm64` en una máquina ARM64. Para Intel/AMD usar `linux/amd64`, o ARM64 si Docker tiene emulación.
4. Ejecutar desde la raíz:

```sh
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
```

5. Abrir `http://127.0.0.1:8080`. La página usa el contrato mock. El proxy también admite `POST /api/v1/procesamientos`.
6. Detener conservando los datos: `docker compose down`. Usar `--volumes` únicamente si se quiere borrar deliberadamente la base local.

El proxy permanece local por defecto. Publicar una URL de servidor, HTTPS, reglas de entrada y secretos reales requiere la configuración de despliegue correspondiente. No exponer PostgreSQL ni la API directamente.

## Prueba reproducible del Compose raíz

Python 3 y Docker Compose disponibles; ARM64 emulada requiere soporte de emulación de Docker.

```sh
python infrastructure/docker/validacion/probar_integracion.py --platform linux/amd64
python infrastructure/docker/validacion/probar_integracion.py --platform linux/arm64
```

Cada ejecución genera un proyecto, puerto, imágenes y credenciales efímeros. No carga el `.env` personal. Construye y ejecuta el Compose raíz, comprueba los cinco servicios y retira exclusivamente sus contenedores/redes/volumen de prueba. Conserva las imágenes como caché. Los resultados JSON y logs quedan en `infrastructure/docker/validacion/resultados/`, ignorados por Git; la síntesis verificable de la entrega está en `docs/evidencia-compose-cinco-servicios.md`.

Incluye salud y arquitectura de cada servicio, aislamiento/puertos, reinicio, recorrido web/proxy/API, contrato válido y errores esperados, consulta SQL desde el worker, conectividad TCP de API a PostgreSQL, persistencia tras reinicio y recuperación de API/web/worker.

## Límites y relación con actividades posteriores

El worker es expresamente una sonda: ejecuta `SELECT 1` y mantiene un pulso de salud. No procesa lotes, no invoca Gemini ni implementa LangGraph. La actividad posterior del worker asíncrono y estados de procesamiento sigue pendiente.

El endpoint de la API devuelve un mock fijo, no guarda los resultados en PostgreSQL. La prueba de persistencia usa una tabla desechable de infraestructura. La conexión TCP de la API no demuestra persistencia del backend.

ARM64 emulada no es evidencia de OCI. Esta actividad de preparación puede validarse localmente; no acredita despliegue público ni operación en una VM. El dataset posterior usa `id_mensaje`, mientras el contrato mock conserva `id`; se documenta el rechazo 422 sin cambiar el contrato de Ian.

## Cierre de aporte y actividad conjunta

La configuración anterior de Paulo estaba en el PR #6, fusionado en la rama de validación y no en main. Esta propuesta parte del main posterior al PR #7 para completar los elementos que aún faltaban sin volver a crear otro backend.

La entrega técnica puede reportarse como configurada y validada localmente si ambas pruebas terminan correctamente. La integración en main y el cierre compartido requieren revisión y fusión de este PR por el equipo. No marcar desplegado en OCI ni implementado el worker real.
