# Evidencia del redespliegue del worker

## 1. Identificación

- Proyecto: CommunityLab
- Rama: `integracion-v1.0`
- Commit desplegado: `00b857a`
- Servicio actualizado: `worker`
- Imagen: `communitylab-worker:local`
- Modo de ejecución: `simulado`
- Fecha de validación: 2026-10-16 UTC

## 2. Procedimiento realizado

1. Se verificó la cola de trabajos: un trabajo histórico terminado y ningún trabajo pendiente.
2. Se reconstruyó la imagen mediante `docker compose build worker`.
3. Se actualizó únicamente el servicio worker mediante `docker compose up -d --no-deps worker`.
4. Se comprobó que el contenedor iniciara en modo simulado.
5. Se consultó la API a través del proxy HTTPS.
6. Se creó un trabajo de prueba mediante `POST /api/v1/trabajos`.
7. Se consultó el resultado mediante `GET /api/v1/trabajos/{identificador}`.
8. Se verificaron los indicadores del dashboard, los activos y el estado de los servicios.

No se ejecutó `db-init` ni se reprocesó el trabajo histórico.

## 3. Resultado de la prueba funcional

- Identificador del trabajo: `fc334260-05c5-4b90-b914-b80a08c2061a`
- Estado final: `terminado`
- Intentos: 1
- Estado del resultado: `completado_local`
- Errores: ninguno
- Modo simulado: sí
- Activos generados: 1
- Formato generado: `post_linkedin_x`
- Estado del activo: `generado`
- Almacenamiento externo: `no_persistido`

El historial del trabajo fue `recibido → procesando → terminado`.

## 4. Persistencia verificada

Los indicadores consultados después de la prueba mostraron:

- Mensajes registrados: 4
- Activos generados: 1
- Activos aprobados: 0
- Alertas internas: 0

El activo quedó registrado en PostgreSQL y fue devuelto por el endpoint de curaduría.

ID del activo: `act-c21a76b812abad503c7770f8316c24707b8d5363`

El contenido está marcado como `[SIMULADO — NO PUBLICAR]`. No representa una publicación real.

La persistencia en PostgreSQL no implica persistencia en almacenamiento externo: el resultado del pipeline informó `almacenamiento.estado=no_persistido`.

## 5. Estado de los servicios

En la comprobación final, los cinco servicios siguientes aparecieron en ejecución y saludables:

- API
- PostgreSQL
- Proxy
- Web
- Worker

El worker utilizó la imagen `communitylab-worker:local` y permaneció saludable después de la prueba.

## 6. Alcance y limitaciones

Esta evidencia registra un redespliegue manual del worker y una prueba funcional controlada en modo simulado.

No certifica la ejecución del procedimiento formal completo descrito en `docs/operacion-vm.md`, que incluye respaldo, prueba de restauración, migración y verificación automatizada.

Tampoco certifica la integración con Gemini, la publicación real de contenido ni la persistencia en almacenamiento externo.

## 7. Conclusión

El worker actualizado procesó correctamente un trabajo nuevo en modo simulado, generó un activo y lo persistió en PostgreSQL. Los servicios permanecieron saludables durante la validación.

El código desplegado ya estaba versionado en `integracion-v1.0` en el commit `00b857a`. Este documento registra la evidencia del despliegue y no sustituye el procedimiento formal de actualización de la VM.
