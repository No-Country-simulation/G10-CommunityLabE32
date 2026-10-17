# Operación de CommunityLab en la VM

VM OCI ARM64. Ruta canónica de la aplicación: **`/srv/communitylab`**, propiedad del usuario de
servicio `communitylab` (sin login). Proyecto Compose `g10-communitylabe32`. Comandos como root (o
`sudo`) desde esa carpeta. Mientras no se ejecute la migración (ver «Ubicación y usuario de
servicio»), la aplicación sigue en la ruta histórica `/home/tareck/G10-CommunityLabE32`; los
scripts de `ops/vm` deducen la ruta de su propio checkout y funcionan en ambas.

## Ubicación y usuario de servicio

Estructura según el Filesystem Hierarchy Standard (FHS 3.0):

| Ruta | Contenido | Dueño |
|---|---|---|
| `/srv/communitylab` | Código, archivos Compose y `.env` (600) | `communitylab` (cuenta de sistema, `nologin`, sin carpeta personal) |
| `/etc/communitylab/discord` | Configuración privada de Discord | root |
| `/var/lib/communitylab/despliegues` | Estado de cada despliegue (reversión) | root (700) |
| `/var/backups/communitylab` | Respaldos | root (700) |
| `/usr/local/sbin/cl-*`, `communitylab-certbot-*` | Comandos de operación y hooks HTTPS | root |
| Volúmenes `g10-communitylabe32_*` | Datos (PostgreSQL, SQLite de Discord) | Docker |

- Las personas conservan sus cuentas (`ubuntu`, `tareck`, …) y operan con `sudo cl-*`. Quien deba
  leer código y logs puede entrar al grupo `communitylab` (`usermod -aG communitylab <usuario>`);
  el `.env` sigue siendo 600 y no lo lee el grupo.
- Todo `git` sobre el checkout se ejecuta con el usuario dueño de la carpeta (`git_app` en
  `comun.sh`, vía `runuser`): los despliegues ya no dejan archivos de root en el repositorio.
- El token de operador no cambia: vive en el `.env` y se mueve con él.

### Migración desde la ruta histórica (una sola vez; requiere autorización)

Script: `ops/vm/migrar-a-srv.sh` (root). No mueve datos: el `.env` fija `COMPOSE_PROJECT_NAME`, así
que el proyecto conserva sus volúmenes (el script se niega a continuar si falta esa línea).

1. Elegir una ventana fuera de cierres semanales (p. ej. después del cierre del lunes 01:00 UTC).
2. `sudo /home/tareck/G10-CommunityLabE32/ops/vm/migrar-a-srv.sh comprobar` — solo comprueba.
3. `sudo /home/tareck/G10-CommunityLabE32/ops/vm/migrar-a-srv.sh ejecutar`:
   respaldo comprobado → usuario `communitylab` → `docker compose down` (sin `-v`) →
   `mv` a `/srv/communitylab` → dueño `communitylab` (carpeta 750, `.env` 600) → instala `cl-*` y
   hooks desde la ruta nueva → `up -d` → salud y verificación HTTPS. Corte estimado: 1–2 min.
   Cualquier fallo durante el corte deshace la mudanza automáticamente.
4. Reversión posterior: `sudo /srv/communitylab/ops/vm/migrar-a-srv.sh deshacer` (devuelve la
   carpeta, el dueño anterior y los `cl-*`/hooks guardados en `/var/lib/communitylab/migracion-srv`).
5. Después de migrar, los `.env` preparados para despliegues deben vivir fuera del repo (p. ej.
   `/root` o `/etc/communitylab`), con permisos 600.

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

El `.env` de la carpeta es la **única** fuente de configuración: no mantener copias paralelas
(`.env.nuevo`, `~/.env.communitylab.nuevo`) como configuración en uso. Un `.env` sin `COMPOSE_FILE`
hace que `docker compose up` sin parámetros levante solo `docker-compose.yml`: modo y proxy locales,
sin HTTPS ni Discord.

### Hooks de certbot

Versionados en `ops/vm/certbot-pre` y `ops/vm/certbot-post`; se instalan como
`/usr/local/sbin/communitylab-certbot-pre|post` (root, 750) y se referencian como `pre_hook` y
`post_hook` en `/etc/letsencrypt/renewal/<dominio>.conf`.

- `certbot-pre` comprueba que el `.env` declare `COMPOSE_FILE` con HTTPS y que la configuración
  resuelta tenga el proxy con 443 **antes** de detenerlo. Si no, sale con error sin tocar el proxy:
  la renovación falla y el sitio sigue sirviendo.
- `certbot-post` levanta solo el proxy (`up -d --no-deps`), valida `nginx -t` y recarga.

No ejecutar `certbot renew --dry-run` en producción sin ventana de mantenimiento: también corre los
hooks y detiene el proxy durante la prueba.

### Proxy y archivo de configuración montado

El proxy monta `proxy/nginx.https.conf` solo cuando se crea con `compose.https.yml`. Un proxy creado
con otra combinación de archivos debe **recrearse** con la invocación canónica
(`docker compose up -d --no-deps proxy` desde la carpeta, con el `.env` canónico); reiniciarlo no
cambia su definición. Comprobación sin reiniciar:
`docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' <proxy>`
debe incluir `compose.https.yml`, y el `sha256sum` de `/etc/nginx/conf.d/default.conf` dentro del
contenedor debe coincidir con `proxy/nginx.https.conf`.

## Variables privadas (solo nombres)

| Variable | Servicio |
|---|---|
| `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` | postgres, api, worker |
| `WORKER_MODE=gemini`, `WORKER_TIMEOUT`, `GEMINI_API_KEY`, `GEMINI_MODELOS`, `GEMINI_*` | worker |
| `DISCORD_BOT_TOKEN` (y opcional `DISCORD_LECTOR_TOKEN`) | discord-reader, discord-bot |
| `GEMINI_API_KEY`, `GEMINI_MODELOS`, opcional `COMMUNITYLAB_GEMINI_MODEL` | discord-bot |
| `DISCORD_CONFIG_DIR` (carpeta privada con `lector.json` y `bot.json`) | discord-reader, discord-bot |
| `PUENTE_PERIODO` (`semana`/`dia`), `PUENTE_GRACIA_SEGUNDOS`, `PUENTE_INTERVALO`, `PUENTE_MAX_PREVIOS` | discord-bridge |
| `PUENTE_TOKEN` (mismo valor en api y discord-bridge; vacío = sin «Procesar pendientes») | api, discord-bridge |
| `OPERADOR_TOKEN` (acciones protegidas; vacío = deshabilitadas con 503) | api |
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
Además, «Procesar pendientes» (Ingesta) adelanta borradores con lotes parciales sin cerrar el
período; el cierre se aplaza mientras haya parciales en curso. Ver `docs/flujo-hibrido-banners.md`.

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

Plantillas en `ops/vm/` (ruta canónica `/srv/communitylab`), instaladas en
`/usr/local/sbin` (root, 755): `cl-estado`, `cl-logs <servicio>`, `cl-reiniciar`, `cl-respaldo`,
`cl-actualizar <sha> <env-nuevo>`, `cl-revertir <carpeta-estado>`.

Instalación (reemplaza versiones antiguas que apunten a `/opt/communitylab`):
`install -m 755 -o root -g root ops/vm/cl-* /usr/local/sbin/`.

## Procedencia de imágenes

`desplegar.sh` exporta `GIT_REVISION=<sha>` al construir; cada imagen propia lleva la etiqueta OCI
`org.opencontainers.image.revision` y la etapa 2 la registra en `<estado>/imagenes.nuevas`.
Comprobación: `docker image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}'
communitylab-api:local`. Una etiqueta de nombre (`:<sha>`) por sí sola no prueba la procedencia.

## Registro de restauraciones

`probar-restauracion.sh` deja `restauracion-<fecha>.json` (resultado OK/FALLA, código de salida,
fecha) dentro de la carpeta del respaldo y lo informa a `logger -t cl-operador`. Un respaldo con
listado legible (`pg_restore -l`) no equivale a una restauración comprobada: solo cuenta el registro
con resultado OK.

## Pruebas de la operación

- `ops/vm/tests/test_puertas_despliegue.py` (bash + git, sin Docker): orden de etapas, conservación
  de imágenes en ejecución antes del build y bloqueo ante fallos de build, pruebas, respaldo,
  restauración o migración; reversión automática ante fallos del corte o la verificación; rechazo de
  un `.env` con Discord sin `DISCORD_CONFIG_DIR`; hooks de certbot que no tocan el proxy si el `.env`
  no es el canónico.
- `ops/vm/tests/test_operacion_docker.py` (`CL_OPS_DOCKER=1`, Docker real): respaldo con los tres
  SQLite en WAL y escrituras concurrentes, restauración desechable, respaldos alterados, esquema
  previo a la migración, imagen con archivos ilegibles, despliegue fallido con reversión automática y
  despliegue exitoso con reversión manual. `CL_OPS_REPRODUCIR=1` reproduce los defectos de `0831c75`.
