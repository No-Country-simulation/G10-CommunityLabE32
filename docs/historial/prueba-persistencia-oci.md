# Prueba de reinicio y persistencia — CommunityLab OCI

## Objetivo

Verificar la recuperación de los servicios, la persistencia
del volumen PostgreSQL y la disponibilidad de herramientas
después de reiniciar servicios y la VM de OCI.

## Entorno

- Sistema operativo: Ubuntu 24.04.5 LTS.
- Arquitectura: ARM64 (aarch64).
- Docker: 29.8.2.
- Docker Compose: v5.6.0.
- Rama Git: integracion-v1.0.

## Respaldos

Se verificaron dos archivos de respaldo con pg_restore --list:

- Respaldo manual: communitylab-2026-10-10-040954.dump.
- Respaldo automático: communitylab-auto-2026-10-10_045932.dump.

Ambos fueron reconocidos como archivos PostgreSQL de formato
CUSTOM, con 21 entradas en el índice.

La validación del índice no equivale a una restauración completa.
No se realizó una restauración de estos respaldos en esta prueba.

## Persistencia de PostgreSQL

Volumen Docker:

- Nombre: g10-communitylabe32_postgres_data.
- Controlador: local.
- Destino: /var/lib/postgresql/data.

Tablas verificadas antes y después de los reinicios:

- activos
- mensajes
- trabajos_worker

Conteos exactos observados antes y después del reinicio:
las tres tablas contenían cero registros.

## Reinicios ejecutados

1. Reinicio controlado del servicio PostgreSQL.
2. Reinicio de API, worker, web y proxy.
3. Reinicio completo de la VM mediante sudo reboot.

Resultados observados:

- Docker volvió a estar activo tras el reinicio de la VM.
- Los cinco contenedores aparecieron saludables.
- PostgreSQL aceptó conexiones.
- Las tres tablas continuaron presentes.
- El volumen PostgreSQL conservó su nombre y montaje.
- La web respondió HTTP 200 por HTTPS.

## Herramientas y paquetes

Versiones verificadas después del reinicio:

- Git: 2.43.0.
- Python: 3.12.3.
- curl: 8.5.0.
- OpenSSL: 3.0.13.
- docker-ce: 29.8.2.
- docker-ce-cli: 29.8.2.
- containerd.io: 2.3.6.
- docker-compose-plugin: 5.6.0.
- python3-venv: 3.12.3.
- ca-certificates: 20260601~24.04.1.

Docker estaba habilitado y activo mediante systemd.
Los contenedores usaban la política de reinicio unless-stopped.

## Conclusión

La VM se reinició y recuperó los servicios correctamente.
El volumen persistente y la estructura de las tablas
PostgreSQL se conservaron, y HTTPS volvió a responder HTTP 200.

La prueba no demuestra la persistencia de registros no vacíos,
porque las tres tablas estaban vacías antes del reinicio.
Tampoco incluye una restauración completa de respaldo ni una
prueba de recuperación ante pérdida o corrupción del volumen.
