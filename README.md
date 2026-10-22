# CommunityLab

**Motor inteligente de transformación y distribución para comunidades digitales.**
Hackathon ONE G10 (Oracle Next Education + Alura) · No Country · Equipo 32.

CommunityLab escucha lo que pasa en una comunidad (Discord o lotes JSON/CSV), lo analiza con Gemini y lo
convierte en contenido listo para revisar y publicar: posts para LinkedIn y X, FAQ y tips, resúmenes
semanales (*Community Highlights*) y alertas internas cuando alguien está bloqueado. Cada contenido
conserva sus mensajes fuente, pasa por curaduría humana y, al aprobarse, se guarda en **OCI Object Storage**.

- **Producción:** https://communitylab.alyntai.com (VM ARM Always Free en OCI, con HTTPS).
- **Repositorio:** https://github.com/No-Country-simulation/G10-CommunityLabE32

---

## Contenido

1. [Qué resuelve](#1-qué-resuelve)
2. [Cómo cumple el MVP de la hackathon](#2-cómo-cumple-el-mvp-de-la-hackathon)
3. [Funcionalidades](#3-funcionalidades)
4. [Arquitectura](#4-arquitectura)
5. [Pipeline de IA (LangGraph + Gemini)](#5-pipeline-de-ia-langgraph--gemini)
6. [Stack](#6-stack)
7. [Estructura del repositorio](#7-estructura-del-repositorio)
8. [Ejecutar en local](#8-ejecutar-en-local)
9. [Despliegue en OCI paso a paso](#9-despliegue-en-oci-paso-a-paso)
10. [API](#10-api)
11. [Seguridad](#11-seguridad)
12. [Pruebas](#12-pruebas)
13. [Datos de demostración](#13-datos-de-demostración)
14. [Documentación detallada](#14-documentación-detallada)
15. [Equipo](#15-equipo)

---

## 1. Qué resuelve

Las comunidades activas generan a diario logros, dudas repetidas y testimonios, pero ese valor se pierde
en el historial de los canales: revisar mensajes y escribir contenido a mano consume horas del equipo de
comunidad y marketing.

CommunityLab automatiza la parte repetitiva y deja la decisión en manos de una persona:

| La comunidad produce… | CommunityLab entrega… |
|---|---|
| «¡Me contrataron como desarrolladora junior!» | Un post para LinkedIn y X que celebra el logro, con su fuente |
| La misma duda de varias personas | Una FAQ o tip técnico de la semana |
| Toda la actividad del período | Un *Community Highlights* semanal |
| «Llevo tres días sin poder avanzar» | Una alerta interna para el equipo (nunca se publica) |
| Cientos de mensajes | Sentimiento, tipos de participación y temas en un panel |

## 2. Cómo cumple el MVP de la hackathon

| Requisito del documento | Cómo se cumple |
|---|---|
| Procesar interacciones de una comunidad (datos reales o simulados) | Ingesta de lotes JSON/JSONL/CSV desde el panel, captura en vivo de Discord e importación histórica de canales |
| Sentimiento, temas e historias relevantes con LLMs | Gemini analiza cada mensaje (sentimiento, tipo, tema, logro, duda, bloqueo) y puntúa su relevancia |
| Al menos dos formatos de activos | Post LinkedIn/X, FAQ/Tip técnico y Community Highlights, más banners SVG |
| Automatización con LangGraph o equivalente | Grafo LangGraph con nodos condicionales (sección 5), ejecutado por un worker en segundo plano |
| Bifurcación de condiciones | Router: bloqueo → alerta interna; duda de ≥ 2 autores → FAQ; logro relevante → post; cierre de período → highlights |
| Interfaz de visualización y aprobación | Panel Next.js con Resumen, Interacciones, Curaduría (aprobar, editar, denegar con motivo) y Analítica |
| **OCI Object Storage (obligatorio)** | Cada versión aprobada se guarda en el bucket privado `communitylab-activos-marketing` (`aprobados/<id>/v<versión>/activo.json` y `banner.svg`), con la identidad de la VM y sin llaves |
| OCI Compute (diferencial) | Toda la aplicación corre en una VM ARM Always Free con Docker Compose y HTTPS |
| README con diagrama y guía de despliegue | Este archivo (secciones 4 y 9) |

## 3. Funcionalidades

| Pantalla | Qué permite |
|---|---|
| **Resumen** | Totales de mensajes, borradores pendientes, aprobados y alertas internas; cada tarjeta abre su listado |
| **Ingesta de datos** | Conectar canales de Discord (hasta cuatro, con período y zona horaria); subir lotes JSON/JSONL/CSV; «Procesar pendientes» de Discord sin cerrar la semana; **Datos cargados**: ocultar o eliminar lotes (solo administradores) |
| **Interacciones** | Todos los mensajes con autor, tipo, tema y sentimiento; búsqueda en el servidor y filtros |
| **Curaduría** | Revisar cada borrador frente a sus fuentes, ver advertencias de fidelidad, editar versiones LinkedIn y X, regenerar con IA, generar el banner, aprobar o denegar con motivo. Cada aprobado muestra si ya se guardó en OCI |
| **Analítica** | Sentimiento, embudo de curaduría, temas detectados y tipos de participación, filtrables por lotes |
| **Usuarios** | Alta de cuentas, roles (usuario, operador, administrador) y restablecimiento de contraseñas |

Además, un **bot de Discord** responde dudas en tiempo real y avisa al equipo cuando detecta a alguien bloqueado.

## 4. Arquitectura

### Pipeline de punta a punta

```mermaid
flowchart LR
    subgraph Entradas
        D[Discord<br/>canales autorizados]
        H[Historial de Discord<br/>importación por rango]
        F[Lote JSON / JSONL / CSV<br/>desde el panel]
    end

    D --> R[discord-reader<br/>captura]
    R --> B[discord-bridge<br/>agrupa por período]
    B --> API
    H --> API
    F --> API

    API[FastAPI<br/>validar · normalizar · deduplicar] --> Q[(PostgreSQL<br/>cola de trabajos)]
    Q --> W[Worker<br/>grafo LangGraph]
    W <--> G[Gemini API]
    W --> PG[(PostgreSQL<br/>mensajes · activos · alertas)]

    PG --> UI[Panel Next.js<br/>curaduría humana]
    UI -->|aprobar| API
    API -->|versión aprobada| OCI[(OCI Object Storage<br/>communitylab-activos-marketing)]

    D -.-> BOT[discord-bot<br/>respuestas y alertas en vivo]
    BOT <--> G
```

### Despliegue en OCI

```mermaid
flowchart TB
    U[Navegador] -->|HTTPS 443| PX
    subgraph VM[VM OCI Ampere A1 · Always Free · Docker Compose]
        PX[proxy · nginx + Let's Encrypt] --> WEB[web · Next.js]
        PX -->|/api| API[api · FastAPI]
        API --> PG[(postgres 16)]
        WK[worker · LangGraph] --> PG
        HIS[discord-historico] --> PG
        RD[discord-reader] --> BR[discord-bridge] --> API
        BOT[discord-bot]
    end
    WK --> GEM[Gemini API]
    BOT --> GEM
    RD & BOT & HIS --> DIS[Discord]
    API -->|instance principal| OS[(OCI Object Storage<br/>bucket privado)]
```

| Servicio | Función |
|---|---|
| `proxy` | nginx: HTTPS, redirección HTTP → HTTPS, cabeceras de seguridad, `/api` hacia la API |
| `web` | Panel Next.js |
| `api` | FastAPI: ingesta, curaduría, métricas, cuentas y sesiones, copia en OCI |
| `worker` | Ejecuta el grafo LangGraph de cada lote con Gemini (o en modo simulado, sin red) |
| `postgres` / `db-init` | Base de datos y migraciones aditivas |
| `discord-reader` | Captura mensajes de los canales autorizados |
| `discord-bridge` | Agrupa por período y entrega los lotes a la API |
| `discord-bot` | Responde dudas y envía alertas internas en vivo |
| `discord-historico` | Importa el historial de un canal en un rango de fechas |

## 5. Pipeline de IA (LangGraph + Gemini)

Cada lote recorre este grafo (`pipelines/communitylab/grafo.py`). Cualquier error lleva directo a la
consolidación: el lote falla entero y no deja borradores a medias.

```mermaid
flowchart TD
    I[inicializar] --> IN[ingesta<br/>normaliza y deduplica]
    IN --> AN[analizar · Gemini<br/>sentimiento, tipo, tema,<br/>logro, duda, bloqueo]
    AN --> PU[puntuar · Gemini<br/>relevancia 0-1]
    PU --> RO{router}
    RO --> DE[despachar]
    DE -->|bloqueo| AL[alerta interna]
    DE -->|duda de ≥ 2 autores| FAQ[generador FAQ / Tip]
    DE -->|logro relevante| POST[generador post LinkedIn / X]
    DE -->|cierre del período| HL[generador Community Highlights]
    AL & FAQ & POST & HL --> DE
    DE -->|sin pendientes| CO[consolidación]
```

**Reglas del router** (`router_base.py`), por mensaje y con esta precedencia: **bloqueo > duda recurrente > logro**.

| Condición | Ruta | Resultado |
|---|---|---|
| El análisis marca bloqueo | `bloqueo` | Alerta interna; el mensaje queda fuera de todo contenido público |
| Relevancia < 0,6 | — | Se descarta con motivo registrado |
| Duda sobre el mismo tema de ≥ 2 autores distintos | `dudas` | FAQ / Tip técnico |
| Logro relevante sin otra ruta | `logro` | Post LinkedIn / X |
| `cierre_periodo = true` | `periodo` | Community Highlights con todos los mensajes relevantes |

**Controles sobre lo que genera la IA**
- **Fidelidad** (`generadores/fidelidad.py`): marca cifras, archivos, detalles o causas que no aparecen en
  las fuentes, y logros colectivos presentados como individuales. Curaduría pide confirmar antes de aprobar.
- **Trazabilidad:** cada activo guarda los IDs de sus mensajes fuente; el modelo nunca los elige.
- **Salida estructurada:** JSON con esquema y validación local estricta; una respuesta inválida escala al
  siguiente modelo o falla, nunca se usa a medias.
- **Presupuesto por lote:** tope de llamadas, tiempo y tokens. Ante un 429 por ritmo, espera lo que indica
  Gemini (configuración en `docs/gemini-grafo-worker.md`).

## 6. Stack

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 16, React, TypeScript, Tailwind CSS, Framer Motion |
| API | FastAPI, SQLAlchemy async, Pydantic |
| Orquestación | LangGraph, worker propio con cola en PostgreSQL (reintentos, *lease*, idempotencia) |
| IA | Google Gemini (`flash-lite` y escalamiento a un modelo mayor), cliente HTTP propio |
| Datos | PostgreSQL 16 |
| Integraciones | Discord (gateway y API REST), bot con Gemini |
| Nube | OCI Compute (Ampere A1, Always Free) y OCI Object Storage (SDK `oci`, instance principal) |
| Operación | Docker Compose, nginx, Let's Encrypt, scripts `cl-*` con respaldo y reversión |

## 7. Estructura del repositorio

```text
backend/                 API FastAPI
  app/routers/           autenticación, mensajes, curaduría, métricas
  app/api/routes/        trabajos, Discord (histórico y escucha), datos cargados, banners, puente
  app/services/          ámbito de lotes, fidelidad, banners, OCI, autenticación
  scripts/               crear_usuario, recalcular_fidelidad, reclasificar_mensajes, oci_almacenamiento…
frontend/                Panel Next.js
pipelines/communitylab/  grafo LangGraph, router, cliente Gemini, generadores, puente de Discord
worker/                  cola en PostgreSQL, esquema (schema.sql) y pruebas de integración
integrations/discord/    lector, bot y procesador de Discord
ops/vm/                  despliegue, respaldo, restauración y reversión en la VM
infrastructure/          notas de OCI, Docker y Gemini
docs/                    documentación detallada (sección 14)
docker-compose.yml       servicios base · compose.https.yml (VM) · compose.discord.yml (Discord)
```

## 8. Ejecutar en local

Requisitos: Docker con Compose 2.24.4 o posterior.

1. **Configurar el entorno.**
   ```bash
   cp .env.example .env
   ```
   En `.env`:
   - `POSTGRES_PASSWORD`: una contraseña propia.
   - `DOCKER_PLATFORM`: `linux/amd64` en PC Intel/AMD, `linux/arm64` en ARM.
   - `JWT_SECRET_KEY`: 32 bytes aleatorios o más, por ejemplo con
     `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
   - Deja `WORKER_MODE=simulado` para probar sin IA ni red. Con `WORKER_MODE=gemini`, define
     `GEMINI_API_KEY` y `GEMINI_MODELOS`.
2. **Levantar los servicios base** (proxy, web, api, worker y postgres):
   ```bash
   docker compose -f docker-compose.yml up -d --build
   ```
3. **Crear el primer administrador.** La contraseña se escribe sin eco:
   ```bash
   docker compose -f docker-compose.yml exec api python -m backend.scripts.crear_usuario --email tu@correo.com --rol administrador
   ```
4. **Entrar** en http://127.0.0.1:8080 y subir un lote desde **Ingesta de datos**. Formato mínimo:
   ```json
   {"interacciones": [{"id": "m-1", "autor": "Ana", "canal": "logros",
     "fecha": "2026-10-19T14:10:00Z", "texto": "¡Aprobé la certificación OCI!"}]}
   ```

Los servicios de Discord se agregan con `compose.discord.yml` y su configuración privada
(`integrations/discord/config-servicios.example/`).

## 9. Despliegue en OCI paso a paso

Todo usa recursos **Always Free**. Detalle completo en `docs/operacion-vm.md`.

### 9.1 Infraestructura en la consola de OCI

1. **VM:** instancia Ampere A1 (ARM) con Ubuntu, IP pública y los puertos 80 y 443 abiertos en la lista
   de seguridad. Instalar Docker y Compose.
2. **Dominio:** un registro A hacia la IP de la VM y certificados de Let's Encrypt en
   `/etc/letsencrypt/live/<dominio>/`.
3. **Bucket:** en *Storage → Buckets*, un bucket **privado** y estándar
   (`communitylab-activos-marketing`).
4. **Acceso sin llaves (instance principal):**
   - Grupo dinámico (*Identity → Domains → Default → Dynamic groups*):
     ```text
     instance.id = '<OCID de la VM>'
     ```
   - Política en el compartimento raíz (crear, sobrescribir y leer objetos; no borrar):
     ```text
     Allow dynamic-group 'Default'/'<grupo>' to read objectstorage-namespaces in tenancy
     Allow dynamic-group 'Default'/'<grupo>' to read buckets in tenancy where target.bucket.name = '<bucket>'
     Allow dynamic-group 'Default'/'<grupo>' to manage objects in tenancy where all {target.bucket.name = '<bucket>', request.permission != 'OBJECT_DELETE'}
     ```

### 9.2 Aplicación en la VM

1. **Código** clonado en `/srv/communitylab`, propiedad del usuario de servicio `communitylab` (sin
   login), y los comandos `ops/vm/cl-*` instalados en `/usr/local/sbin`. En esta VM lo hizo
   `ops/vm/migrar-a-srv.sh` al mudar la aplicación desde su ruta anterior.
2. **`.env` privado** (permisos 600, fuera de Git), a partir de `.env.example`:
   - `COMPOSE_FILE=docker-compose.yml:compose.https.yml:compose.discord.yml`
   - `WORKER_MODE=gemini`, `GEMINI_API_KEY`, `GEMINI_MODELOS`
   - `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `OPERADOR_TOKEN`, `PUENTE_TOKEN`
   - `OCI_ALMACENAMIENTO=instance_principal` (bucket en `OCI_BUCKET_NAME`)
   - Tokens y canales de Discord (`docs/operacion-vm.md`, «Variables privadas»)
3. **Desplegar un commit:**
   ```bash
   sudo cl-actualizar <sha> <ruta-al-.env-nuevo>
   ```
   Ejecuta seis puertas; si una falla, las siguientes no corren:
   1. guarda el estado actual para poder revertir;
   2. construye y prueba las imágenes en un worktree aislado;
   3. respalda la base y comprueba que el respaldo se restaura;
   4. aplica la migración (aditiva) con la versión anterior aún en servicio;
   5. hace el corte (única interrupción);
   6. verifica los servicios y HTTPS; si falla, revierte solo.
4. **Primer administrador:**
   ```bash
   sudo docker compose exec api python -m backend.scripts.crear_usuario --email <correo> --rol administrador
   ```
5. **Verificar OCI:**
   ```bash
   sudo docker compose exec api python -m backend.scripts.oci_almacenamiento --verificar
   ```
   Debe imprimir `escritura=ok lectura=ok`.
6. **Revertir** si hace falta: `sudo cl-revertir <estado>` (la carpeta la indica el despliegue).

## 10. API

Documentación interactiva en `/docs` (Swagger). Principales rutas:

| Área | Rutas |
|---|---|
| Ingesta | `POST /api/mensajes/procesamientos` (archivo), `POST /api/v1/trabajos`, `GET /api/v1/trabajos/{id}` |
| Mensajes y métricas | `GET /api/mensajes` (búsqueda `q`, lotes, sentimiento), `GET /api/dashboard/kpis`, `/alertas`, `/ambitos` |
| Curaduría | `GET/PATCH /api/curaduria/activos/{id}`, `POST .../posts/generar`, `GET/POST .../banners` |
| Datos cargados | `GET /api/v1/datos/lotes`, `PATCH .../visibilidad`, `POST .../eliminacion/vista-previa`, `POST .../eliminacion` |
| Discord | `/api/v1/discord/historico/*` (importar por rango), `/api/v1/discord/canales/{id}/escucha`, `/api/v1/procesamiento-pendientes` |
| Cuentas | `POST /api/auth/login`, `/logout`, `GET /api/auth/sesion`, `GET/POST/PATCH /api/auth/usuarios` |

Ejemplo de lote (formato del documento de la hackathon):

```json
{
  "origen_comunidad": "Discord_Grupo_ONE_G10",
  "periodo_referencia": "2026-W43",
  "cierre_periodo": true,
  "interacciones": [
    {"id": "m-01", "autor": "Mariana Souza", "canal": "#logros-y-empleos", "tipo": "testimonio",
     "fecha": "2026-10-19T14:10:00Z",
     "texto": "¡Quedé seleccionada como Desarrolladora Junior de IA gracias al proyecto de LangChain y OCI!"}
  ]
}
```

## 11. Seguridad

- **Sesiones:** cookie HttpOnly (`cl_sesion`) + token CSRF en memoria; nada de tokens en `localStorage`.
  Roles leídos de la base en cada petición; registro público cerrado; límite de intentos de login.
- **Permisos** por endpoint en `docs/politica-acceso.md`. Las acciones destructivas (eliminar lotes,
  gestionar cuentas) son solo de administradores.
- **Secretos:** solo en el `.env` privado de la VM (600). No hay credenciales predeterminadas; las
  contraseñas nunca van en argumentos ni en logs. OCI usa la identidad de la VM, sin llaves.
- **Contenedores:** usuarios no root, sistemas de archivos de solo lectura donde aplica, sin puertos
  publicados salvo el proxy.
- **IA:** los mensajes de bloqueo nunca llegan a contenido público; todo contenido pasa por aprobación humana.

## 12. Pruebas

- **Worker, API y PostgreSQL** (`worker/tests/`): ingesta, flujo híbrido, curaduría, búsqueda, tipos y
  temas, nombres de Discord, OCI con cliente falso, datos cargados y una batería de acceso y seguridad.
- **Grafo y Gemini** (`pipelines/communitylab/tests/`): router, presupuesto, fidelidad y cliente con
  transporte falso (sin red ni claves).
- **Discord** (`integrations/discord/*/tests`) y **operación de la VM** (`ops/vm/tests/`: puertas de
  despliegue, respaldo, restauración y reversión con Docker real).
- **CI en GitHub Actions** en cada PR: título con convención de commits, grafo, Discord, PostgreSQL,
  proxy HTTP/HTTPS y operación de la VM.

## 13. Datos de demostración

La demo usa 500 mensajes de soporte al cliente en español, repartidos en 5 semanas (W39 a W43), con
autores, canales y fechas ficticios. Los textos provienen del dataset público
[Bitext customer support (español)](https://huggingface.co/datasets/Faramir/Bitext-customer-support-llm-chatbot-training-dataset-spanish),
licencia **CDLA-Sharing-1.0**. No contienen datos personales reales.

## 14. Documentación detallada

| Documento | Tema |
|---|---|
| `docs/operacion-vm.md` | Operación de la VM: rutas, variables, despliegue, respaldo y reversión |
| `docs/http-local-https-vm.md` | HTTP local y HTTPS en la VM |
| `docs/gemini-grafo-worker.md` | Cliente Gemini, presupuesto por lote y política de errores |
| `docs/oci-object-storage.md` | Copia de los aprobados en OCI y acceso por instance principal |
| `docs/ingesta-lotes.md` | Formatos de lote, resultados del worker y datos cargados |
| `docs/flujo-hibrido-banners.md` | «Procesar pendientes», cierre de período y banners |
| `docs/discord-historico.md` | Importación histórica de canales de Discord |
| `docs/metricas-panel.md` | Cómo se calcula cada métrica del panel |
| `docs/politica-acceso.md` | Roles, sesiones y permisos por endpoint |

## 15. Equipo

| Integrante | Rol |
|---|---|
| Elizabeth Aguilar | Gestión del proyecto, metodologías ágiles y control de calidad |
| Vania Sherel Cruz Hernández | Desarrollo asistido por IA, experiencia de usuario y soporte de integración |
| José Ángel Olán de los Santos | Ingeniería de datos: PostgreSQL, modelado y ETL |
| Fredy Pachón | Desarrollo de backend: flujos de datos y lógica del backend |
| Ianjaner Alfonso Beltrán Guañarita | Desarrollo web: frontend Next.js, autenticación y protección de rutas |
| Santiago Horta Hurtado | Ingeniería de agentes autónomos e integración con el backend |
| Fabián Hernández Alejandro | Ingeniería de prompts para análisis y generación de contenido |
| Paulo Andrés Escobar Saldaña | Ingeniería de agentes: LangGraph, Gemini, integración con Discord y despliegue en OCI |
