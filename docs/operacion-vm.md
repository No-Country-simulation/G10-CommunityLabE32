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

## Procedimiento único de despliegue

`sudo cl-actualizar <sha> <env-nuevo>` ejecuta `ops/vm/desplegar.sh`. El `.env` nuevo (privado, 600,
fuera del repositorio) se prepara antes y debe definir `COMPOSE_FILE` con `compose.https.yml`; el
script lo instala recién en el corte. Cada etapa es una puerta: si falla, las siguientes no se ejecutan.

| # | Etapa | Qué hace | Si falla |
|---|---|---|---|
| 1 | Conservar | Guarda en `/var/lib/communitylab/despliegues/<id>/` (root, 700) el `.env`, el commit y los ids de imagen **de los contenedores en ejecución**; los etiqueta `:prev-<id>` antes de cualquier build | Nada cambió |
| 2 | Construir y probar | Build en un worktree aislado con etiquetas `:<sha>` (las `:local` no se tocan); `probar-imagenes.sh`: importación desde `/app` y suites de worker, grafo, Discord y API **con el usuario de cada imagen** | Nada cambió en producción |
| 3 | Respaldo y restauración | `respaldo.sh` + `probar-restauracion.sh` (ver abajo) | Nada cambió; el puente se reanuda |
| 4 | Migración | `db-init` de la versión nueva (aditiva) con la app anterior aún en servicio | Se detiene; la app anterior sigue funcionando sobre el esquema |
| 5 | Corte | Instala el `.env` nuevo, `checkout` del sha, `:<sha>` → `:local`, `up -d --remove-orphans` | Reversión automática |
| 6 | Verificación | Todos los servicios sanos + API + `VERIFICAR_URLS` (HTTPS 200 y HTTP→HTTPS 301) | Reversión automática |

Interrupción: solo la etapa 5 (recreación de contenedores). Si la reversión automática también falla,
el script lo informa y se sigue el procedimiento manual de Reversión con la carpeta de estado.

## Respaldo y restauración

- `ops/vm/respaldo.sh` (o `sudo cl-respaldo`, que además comprueba la restauración):
  - PostgreSQL: una transacción `REPEATABLE READ` exporta un snapshot; conteos por tabla y columnas
    del manifiesto se leen en ella y `pg_dump --snapshot` usa el mismo estado, aunque API y worker
    sigan escribiendo.
  - SQLite (bandeja, puente y bot): se pausa el puente; cada base se copia con la API de backup de
    SQLite (incluye el WAL) en un contenedor con la identidad dueña del volumen; la copia sale por
    stdout y el host la guarda. El contenedor nunca escribe en el destino.
  - Destino `/var/backups/communitylab/<fecha>` (root 700, archivos 600): `postgres.dump`, `sqlite/`,
    `configuracion-privada.tgz` y `manifiesto.json` (commit, conteos, columnas, integridad y conteos SQLite).
- `ops/vm/probar-restauracion.sh <respaldo>`: restaura en contenedores desechables sin red (nombres
  únicos, solo borra los suyos) y exige que conteos y columnas de PostgreSQL y la integridad y
  conteos de cada SQLite coincidan con el manifiesto. El esquema esperado es el de la versión
  respaldada: un respaldo anterior a la migración no necesita `clave_idempotencia`.

## Reversión

- **Aplicación**, automática en las etapas 5–6 o manual: `sudo cl-revertir /var/lib/communitylab/despliegues/<id>`
  (`ops/vm/revertir.sh`):
  1. detiene los consumidores nuevos (bot, lector, puente y worker);
  2. restaura el `.env` y el commit anteriores; mantiene el override HTTPS si la versión anterior lo
     tiene disponible (`REVERTIR_CONSERVAR_HTTPS=1`), para no perder TLS al recrear el proxy;
  3. devuelve a `:local` las imágenes `:prev-<id>` (las que estaban en ejecución);
  4. `up -d --remove-orphans`: retira contenedores de servicios que la versión anterior no tenía
     (sus volúmenes se conservan);
  5. verifica salud y URLs.

  La migración es aditiva: la versión anterior funciona sobre el esquema nuevo (probado).
- **Datos** (solo ante corrupción, decisión manual): detener lector, puente, bot y worker;
  restaurar PostgreSQL desde un respaldo comprobado; `puente_discord reconciliar` (reabre entregas
  cuyo trabajo ya no existe, para reenviarlas con la misma clave); reanudar. Se pierden los trabajos
  generados después del respaldo.
- Nunca: `docker compose down -v`, `docker volume prune`, borrar SQLite de estado.

## Comandos `cl-*`

Plantillas en `ops/vm/` (ruta real `/home/tareck/G10-CommunityLabE32`), instaladas en
`/usr/local/sbin` (root, 755): `cl-estado`, `cl-logs <servicio>`, `cl-reiniciar`, `cl-respaldo`,
`cl-actualizar <sha> <env-nuevo>`, `cl-revertir <carpeta-estado>`.

## Pruebas de la operación

- `ops/vm/tests/test_puertas_despliegue.py` (bash + git, sin Docker): orden de etapas, conservación
  de imágenes en ejecución antes del build y bloqueo ante fallos de build, pruebas, respaldo,
  restauración o migración; reversión automática ante fallos del corte o la verificación.
- `ops/vm/tests/test_operacion_docker.py` (`CL_OPS_DOCKER=1`, Docker real): respaldo con los tres
  SQLite en WAL y escrituras concurrentes, restauración desechable, respaldos alterados, esquema
  previo a la migración, imagen con archivos ilegibles, despliegue fallido con reversión automática y
  despliegue exitoso con reversión manual. `CL_OPS_REPRODUCIR=1` reproduce los defectos de `0831c75`.
