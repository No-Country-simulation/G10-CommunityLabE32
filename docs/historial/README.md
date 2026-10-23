# Historial del proyecto

Documentos de etapas anteriores que se conservan como registro. **No describen el estado actual**: para eso
están el `README.md` de la raíz y el resto de `docs/`.

| Archivo | Qué registra |
|---|---|
| `compose-cinco-servicios.md`, `evidencia-compose-cinco-servicios.md`, `evidencia-docker.md` | Primer Docker Compose ARM64 (septiembre), cuando el worker era una sonda y la API un mock |
| `validacion-contrato-fastapi.md` | El endpoint mock inicial `POST /api/v1/procesamientos`, ya retirado |
| `prueba-persistencia-oci.md`, `prueba-escala-worker.md` | Pruebas de reinicio y de escala del worker en la primera VM |
| `arquitectura-pipeline.svg` | Primer borrador del diagrama de arquitectura (28/09); el vigente está en el README |
| `frontend-2.0/` | Notas de integración del frontend 2.0 con el backend (pendientes, ajustes y contratos) |
| `contratos/` | Contratos de integración acordados entre integrantes durante el desarrollo |
| `discord/` | Validaciones locales del lector y del bot (09/10) y revisión de los PR de Discord (13/10), antes de conectarlos al servidor real |
| `worker-local-03-10.md` | Guía para levantar el worker en local con Compose (03/10), antes de la cola actual en PostgreSQL |
