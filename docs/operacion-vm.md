# Operación de CommunityLab en la VM

VM OCI ARM64. Repositorio en `/home/tareck/G10-CommunityLabE32`, proyecto Compose
`g10-communitylabe32`. Comandos como root (o `sudo`) desde esa carpeta.

## Invocación canónica

El `.env` privado de la VM (permisos 600, fuera de Git) define los archivos de Compose una sola vez,
para que **cualquier** `docker compose` (despliegue, hooks de certbot, scripts `cl-*`) use la misma
configuración y nunca omita HTTPS ni los servicios de Discord:

```text
COMPOSE_PROJECT_NAME=g10-communitylabe32
COMPOSE_PATH_SEPARATOR=:
COMPOSE_FILE=docker-compose.yml:compose.https.yml:compose.discord.yml
```

Comprobación (no muestra secretos): `docker compose config --services` debe listar proxy, web, api,
worker, postgres, db-init, discord-reader, discord-bridge y discord-bot; y
`docker compose config | grep -c 443` debe ser mayor que 0. No usar `docker compose config` completo
en pantalla compartida: resuelve variables.

Los hooks de certbot (`/usr/local/sbin/communitylab-certbot-pre|post`) hacen `cd` a la carpeta y
ejecutan `docker compose stop|up -d proxy`; con `COMPOSE_FILE` en `.env` heredan el override HTTPS.
Si faltara una variable obligatoria de Discord, `docker compose` fallaría y el post-hook dejaría el
proxy detenido: verificar `docker compose config --quiet` tras cualquier cambio del `.env`.

## Variables privadas (solo nombres)

| Variable | Servicio |
|---|---|
| `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` | postgres, api, worker |
| `WORKER_MODE=gemini`, `WORKER_TIMEOUT`, `GEMINI_API_KEY`, `GEMINI_MODELOS`, `GEMINI_*` | worker |
| `DISCORD_BOT_TOKEN` (y opcional `DISCORD_LECTOR_TOKEN`) | discord-reader, discord-bot |
| `GEMINI_API_KEY`, `GEMINI_MODELOS`, opcional `COMMUNITYLAB_GEMINI_MODEL` | discord-bot |
| `DISCORD_CONFIG_DIR` (carpeta privada con `lector.json` y `bot.json`) | discord-reader, discord-bot |
| `PUENTE_PERIODO` (`semana`/`dia`), `PUENTE_GRACIA_SEGUNDOS`, `PUENTE_INTERVALO` | discord-bridge |
| `DOCKER_PLATFORM=linux/arm64`, `HTTP_*`, `HTTPS_*`, `LETSENCRYPT_DIR` | proxy y construcción |

Ejemplos de `lector.json`/`bot.json`: `integrations/discord/config-servicios.example/`.

## Servicios de Discord

| Servicio | Función | Estado durable | Salud |
|---|---|---|---|
| `discord-reader` | Captura mensajes de canales autorizados | volumen `discord_bandeja` (SQLite) | latido + sesión verificada (`salud`) |
| `discord-bridge` | Bandeja → API, un cierre por período | volumen `discord_puente` (SQLite de entregas) | latido por ciclo |
| `discord-bot` | Responde dudas y envía alertas internas con Gemini | volumen `discord_bot` (SQLite) | latido + sesión verificada |

- Sin puertos publicados, sistema de archivos de solo lectura, sin capacidades, usuario no root.
- Lector y bot rechazan una segunda instancia sobre el mismo estado (candado de archivo).
- Un canal sin mensajes no es una falla: la salud depende del proceso y de la sesión, no del tráfico.
- Lector y bot abren dos sesiones del gateway con el mismo token (o tokens distintos si se define
  `DISCORD_LECTOR_TOKEN`). Su comportamiento real se verifica en la prueba controlada.

### Período y cierre

Cada período (semana ISO UTC o día) se envía **una sola vez** con `cierre_periodo=true` cuando vence
(fin + `PUENTE_GRACIA_SEGUNDOS`) o al pedirlo: `docker compose exec discord-bridge python -m
pipelines.communitylab.puente_discord cerrar --periodo 2026-W42`. Los mensajes que llegan después a un
período ya cerrado quedan registrados como tardíos y no se envían. No hay cierre incremental continuo:
el contenido (post, FAQ, highlights) se genera al cerrar el período; el bot sí responde en tiempo real.

## Respaldo y restauración

- `sudo cl-respaldo` (o `ops/vm/respaldo.sh`): pausa el puente, `pg_dump`, backup de SQLite con la API
  de SQLite (verificado con `integrity_check`), `.env` y configuración privada, commit, imágenes y
  conteos. Destino `/var/backups/communitylab/<fecha>` (solo root).
- `ops/vm/probar-restauracion.sh <respaldo>`: restaura en un PostgreSQL desechable sin red y compara
  conteos y esquema. Debe pasar antes de cualquier migración.

## Despliegue (resumen)

1. Construir y probar las imágenes nuevas sin detener producción (`docker compose build`; pruebas
   dentro de las imágenes arm64).
2. Etiquetar las imágenes actuales `:prev-<fecha>` y las nuevas con el SHA.
3. Respaldo + prueba de restauración.
4. `docker compose run --rm db-init` (migración aditiva) y `docker compose up -d --remove-orphans`.
5. Verificar salud, HTTPS (301 y 200, certificado), un lote real y los servicios de Discord.

`sudo cl-actualizar` automatiza 2–4 sobre `origin/main`.

## Reversión

- **Aplicación** (sin perder datos): `docker tag communitylab-<svc>:prev-<fecha> communitylab-<svc>:local`
  para api, worker, web y discord; `docker compose up -d --no-build`. Si la versión anterior no tenía
  Discord, quitar `compose.discord.yml` de `COMPOSE_FILE` y `docker compose up -d --remove-orphans`.
  La migración es aditiva: el código anterior funciona sobre el esquema nuevo (ensayado).
- **Datos** (solo ante corrupción): detener lector, puente y bot; restaurar PostgreSQL desde el
  respaldo; ejecutar `puente_discord reconciliar` (reabre entregas cuyo trabajo ya no existe para
  reenviarlas con la misma clave); reanudar. Se pierden los trabajos generados después del respaldo.
- Nunca: `docker compose down -v`, `docker volume prune`, borrar SQLite de estado.

## Comandos `cl-*`

Plantillas en `ops/vm/` con la ruta real (`/home/tareck/G10-CommunityLabE32`); se instalan en
`/usr/local/sbin` (root, 755). `cl-estado`, `cl-logs <servicio>`, `cl-reiniciar`, `cl-respaldo`,
`cl-actualizar`.
