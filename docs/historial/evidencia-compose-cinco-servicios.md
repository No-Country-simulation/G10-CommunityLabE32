# Evidencia local — Compose de cinco servicios

Validación del 28/09/2026 sobre `main` a4ba9d1e6b4db21a96d222721e5139fe4b3517e9 más los cambios de esta entrega. Backend, Dockerfile del backend y contrato mock existentes sin modificaciones.

| Plataforma | Comprobaciones satisfactorias | Inicio UTC | Fin UTC |
| --- | --- | --- | --- |
| linux/amd64 | 44/44 | 2026-09-28T14:25:33.967835+00:00 | 2026-09-28T14:26:22.051713+00:00 |
| linux/arm64 | 44/44 | 2026-09-28T14:26:08.407324+00:00 | 2026-09-28T14:28:43.488855+00:00 |

AMD64 se ejecutó localmente en Docker Desktop; ARM64 se ejecutó mediante emulación. En ambas se comprobó `uname -m` dentro de los cinco contenedores (`x86_64` y `aarch64`, respectivamente). No se ejecutó en OCI.

## Qué se verificó

- Cinco servicios saludables, con imágenes ejecutándose en la arquitectura solicitada y política `unless-stopped`.
- Redes frontend y database internas. PostgreSQL, API, web y worker sin puertos publicados; solo proxy accesible desde localhost.
- Arranque del backend modular `backend.app.main:app`; conectividad TCP API–PostgreSQL y consultas SQL del worker sonda.
- Página Next.js mediante Nginx y POST `/api/v1/procesamientos` tanto por proxy como por el reenvío de Next.js.
- Contrato mock: respuesta 200, tres formatos (LinkedIn, FAQ y newsletter), alerta interna separada, seis entradas y referencias del lote ficticio.
- Errores 422 para entradas incompletas, JSON malformado, mensajes sin texto y tipos inválidos; 405 para GET.
- Rechazo 422 de `id_mensaje` en lugar de `id`: es una diferencia conocida con el esquema de ingesta posterior, no se cambió el contrato para ocultarla.
- Persistencia de una tabla desechable después de reiniciar PostgreSQL; recuperación del proxy tras recrear API/web; reinicio automático del worker después de una caída provocada dentro del proceso.
- Construcción de frontend con `npm ci`, lint y build. Retirada completa de los contenedores, redes y volúmenes de cada proyecto de prueba.

## Reproducir

```sh
python infrastructure/docker/validacion/probar_integracion.py --platform linux/amd64
python infrastructure/docker/validacion/probar_integracion.py --platform linux/arm64
```

Cada ejecución utiliza credenciales efímeras y un puerto/proyecto aislados. Los informes completos y logs locales quedan en `infrastructure/docker/validacion/resultados/`, excluidos de Git. La guía de arranque está en [compose-cinco-servicios.md](compose-cinco-servicios.md).

## Límites del resultado

El worker es una sonda de infraestructura, no procesa IA. La API conserva el mock fijo y no persiste resultados; la tabla de prueba solo demuestra persistencia de PostgreSQL. No se probó Gemini, ingesta, HTTPS, una VM ni datos reales. La adaptación de `id_mensaje` corresponde a la integración posterior del dataset.

Durante la preparación se corrigió el acceso al proxy desde el host y la forma de simular la caída del worker: una parada manual con Docker no demuestra recuperación automática. Las ejecuciones finales de la tabla terminaron satisfactoriamente.

Este PR entrega la configuración y evidencia para revisión. La revisión del equipo y su fusión en main siguen pendientes; no equivale a una nueva aprobación de Tarek ni al cierre del despliegue.
