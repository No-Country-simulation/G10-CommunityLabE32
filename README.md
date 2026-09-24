# G10 CommunityLab E32

## Community Radar — Hackathon No Country

Sistema para transformar la actividad de una comunidad de Discord en información estructurada y activos de contenido para comunicación y marketing.

El proyecto forma parte de la simulación de hackathon **No Country — G10 CommunityLab E32**.

---

# 1. Objetivo del proyecto

El objetivo de G10 CommunityLab E32 es construir un sistema capaz de:

1. Recibir datos provenientes de una comunidad.
2. Ingerir lotes de mensajes en formato JSON/CSV.
3. Validar, limpiar, normalizar y deduplicar la información.
4. Analizar los mensajes mediante inteligencia artificial.
5. Identificar sentimientos, temas, relevancia, preguntas frecuentes y testimonios.
6. Generar activos de contenido a partir de la información analizada.
7. Mantener las fuentes de los mensajes utilizados.
8. Guardar los paquetes generados en OCI Object Storage.
9. Exponer el procesamiento mediante una API.
10. Mostrar los resultados mediante una interfaz web.

Flujo general previsto:

```text
Discord
   │
   ▼
Ingesta
   │
   ▼
Limpieza y normalización
   │
   ▼
Análisis / IA
   │
   ▼
Generación de activos
   │
   ├── LinkedIn / X
   ├── FAQ / Tip
   └── Community Highlights
   │
   ▼
PostgreSQL
   │
   ▼
OCI Object Storage
   │
   ▼
FastAPI
   │
   ▼
Frontend Web
```

---

# 2. Estado actual del proyecto

El proyecto se encuentra en fase de construcción del MVP.

## Actualmente implementado

* Repositorio monorepo creado.
* Estructura inicial del proyecto creada.
* Flujo de trabajo mediante Git y GitHub.
* Backend inicializado con FastAPI.
* Endpoint de salud `GET /health`.
* Endpoint mock `POST /api/v1/procesamientos`.
* Documentación automática mediante Swagger/OpenAPI.
* Entorno virtual Python local.
* `.gitignore` configurado para archivos de Python y entornos virtuales.
* Primer commit funcional del backend publicado en GitHub.

## En desarrollo / pendientes

* Docker Compose completo ARM64.
* Frontend Next.js + React + TypeScript + Tailwind.
* Módulo de ingestión JSON/CSV.
* Limpieza, normalización y deduplicación.
* Integración de Gemini.
* Procesamiento mediante worker.
* PostgreSQL para estados y procesamiento.
* Generación de activos.
* Almacenamiento en OCI Object Storage.
* Endpoint real de procesamiento.
* Pruebas End-to-End.
* Despliegue completo en OCI.

---

# 3. Repositorio

Repositorio oficial:

```text
https://github.com/No-Country-simulation/G10-CommunityLabE32
```

La rama utilizada actualmente para el trabajo del backend es:

```text
chore/github-workflow
```

Los cambios deben realizarse mediante commits claros y posteriormente sincronizarse con GitHub.

---

# 4. Estructura del proyecto

La estructura principal del monorepo es:

```text
G10-CommunityLabE32/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── procesamientos.py
│   │   │
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   │
│   │   └── main.py
│   │
│   └── tests/
│
├── frontend/
│
├── data/
│
├── docs/
│
├── infrastructure/
│
├── pipelines/
│   ├── ingestion/
│   ├── cleaning/
│   ├── analysis/
│   └── embeddings/
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── LICENSE
└── README.md
```

La estructura se irá completando a medida que cada módulo del MVP sea implementado.

---

# 5. Backend

El backend utiliza:

* Python
* FastAPI
* Uvicorn
* Pydantic
* PostgreSQL como base de datos prevista
* Docker como mecanismo de ejecución previsto

Actualmente FastAPI está funcionando localmente.

## Estructura actual

```text
backend/
└── app/
    ├── main.py
    ├── api/
    │   └── routes/
    │       └── procesamientos.py
    └── schemas/
```

---

# 6. Endpoint de salud

Actualmente existe:

```text
GET /health
```

Su objetivo es verificar que la API está funcionando.

Respuesta actual:

```json
{
  "estado": "ok",
  "servicio": "communitylab-api"
}
```

---

# 7. Endpoint mock de procesamiento

Como parte de la inicialización del backend se implementó:

```text
POST /api/v1/procesamientos
```

Actualmente es un **endpoint mock**.

Su función es permitir que frontend y backend puedan comenzar a trabajar en paralelo antes de que esté terminado el procesamiento real.

Respuesta actual:

```json
{
  "procesamiento_id": "mock-001",
  "estado": "recibido",
  "mensaje": "Procesamiento recibido correctamente"
}
```

Este contrato es provisional para la etapa mock.

El contrato completo del procesamiento real deberá respetar los campos acordados para el MVP.

Entre los campos previstos para la respuesta real están:

```text
procesamiento_id
resumen
activos
alertas
almacenamiento_oci
```

No se debe asumir que el contrato definitivo está cerrado hasta que sea documentado y acordado por el equipo.

---

# 8. Ejecutar el backend localmente

## Requisitos

Se necesita:

* Python
* Git
* Visual Studio Code recomendado

---

## Crear entorno virtual

Desde la raíz del proyecto:

```bash
python3 -m venv .venv
```

Activar el entorno:

```bash
source .venv/bin/activate
```

Cuando esté activo deberá aparecer algo similar a:

```text
(.venv) TARECK ~/G10-CommunityLabE32 %
```

---

# 9. Instalar dependencias iniciales

Con el entorno virtual activo:

```bash
python -m pip install fastapi uvicorn
```

Las dependencias adicionales se irán incorporando conforme avance el proyecto.

---

# 10. Ejecutar FastAPI

Desde la raíz:

```bash
python -m uvicorn backend.app.main:app --reload
```

La API quedará disponible localmente en:

```text
http://127.0.0.1:8000
```

---

# 11. Swagger / documentación de la API

FastAPI genera automáticamente la documentación interactiva.

Abrir:

```text
http://127.0.0.1:8000/docs
```

En Swagger actualmente debe aparecer:

```text
GET  /health
POST /api/v1/procesamientos
```

El endpoint `POST /api/v1/procesamientos` puede ejecutarse desde Swagger utilizando:

```text
Try it out
```

y posteriormente:

```text
Execute
```

---

# 12. Arquitectura prevista

La arquitectura general del MVP está organizada por componentes:

```text
                  ┌─────────────────┐
                  │    Frontend     │
                  │ Next.js / React │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │    FastAPI      │
                  │      API        │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │     Worker      │
                  │ procesamiento   │
                  └────────┬────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        PostgreSQL      Pipelines        IA
                         │              Gemini
                         │
                         ▼
                  Generación de
                     activos
                           │
                           ▼
                  OCI Object Storage
```

---

# 13. Pipeline de datos

El pipeline previsto para el MVP es:

```text
Lote JSON / CSV
      │
      ▼
Validación
      │
      ▼
Normalización
      │
      ▼
Deduplicación
      │
      ▼
Análisis
      │
      ├── Sentimiento
      ├── Temas
      ├── Relevancia
      └── Fuentes
      │
      ▼
Generación de contenido
      │
      ├── LinkedIn / X
      ├── FAQ / Tip
      └── Community Highlights
      │
      ▼
Paquete de resultados
      │
      ▼
OCI Object Storage
```

---

# 14. LangGraph

LangGraph está previsto para organizar el flujo de procesamiento y los diferentes pasos del pipeline.

La arquitectura definitiva del grafo será documentada en:

```text
docs/
```

El grafo deberá permitir organizar etapas como:

```text
Ingesta
   ↓
Limpieza
   ↓
Análisis
   ↓
Generación
   ↓
Validación
   ↓
Almacenamiento
```

Los nodos de error y reintentos para problemas de IA también forman parte del desarrollo posterior.

---

# 15. Inteligencia Artificial

El proyecto contempla el uso de **Gemini** para el análisis de los mensajes.

El análisis deberá contemplar información como:

* Sentimiento.
* Temas.
* Relevancia.
* Fuentes.
* Preguntas frecuentes.
* Testimonios.
* Información útil para generación de contenido.

La salida del análisis deberá mantenerse estructurada para poder ser procesada por los siguientes componentes del pipeline.

---

# 16. Generación de activos

Uno de los objetivos principales del proyecto es convertir la información de la comunidad en activos reutilizables.

Los activos contemplados para el MVP incluyen:

### LinkedIn / X

Generación de contenido para redes sociales a partir de los hallazgos de la comunidad.

### FAQ / Tip

Conversión de preguntas o conocimientos frecuentes en contenido útil.

### Community Highlights

Identificación de momentos, opiniones o aportes relevantes de la comunidad.

Los activos deben conservar las fuentes utilizadas para generarlos.

---

# 17. PostgreSQL

PostgreSQL está contemplado como la base de datos del sistema.

Será utilizada para manejar información relacionada con:

* Procesamientos.
* Estados.
* Mensajes o datos normalizados según el diseño definitivo.
* Resultados del procesamiento.
* Información necesaria para coordinar el worker.

La implementación completa de PostgreSQL forma parte de las siguientes etapas del proyecto.

---

# 18. Worker

El proyecto contempla un worker para ejecutar el procesamiento de los lotes de forma asíncrona.

El worker tendrá responsabilidad sobre el procesamiento del lote y la ejecución de los componentes correspondientes del pipeline.

La implementación se realizará dentro de Docker Compose.

---

# 19. Docker Compose

El objetivo es disponer de una arquitectura compuesta por servicios independientes.

La configuración prevista contempla:

```text
proxy
web
api
worker
postgres
```

Además se contemplan:

* Healthchecks.
* Reinicio automático.
* Red privada entre servicios.
* Imágenes compatibles con ARM64.
* Secretos fuera del repositorio.

La configuración de Docker Compose se encuentra actualmente en desarrollo.

---

# 20. OCI

OCI será utilizado como infraestructura de despliegue y almacenamiento del proyecto.

La arquitectura contempla:

```text
OCI
│
├── VM Always Free
│
└── Object Storage
```

La VM prevista utiliza:

```text
Ampere A1
ARM64
Ubuntu
```

La configuración contempla:

* VCN.
* Subred.
* IP pública.
* Claves SSH.
* Reglas de entrada.
* Docker.
* Servicios del proyecto.

---

# 21. Estado de OCI

Actualmente la creación de la VM Always Free está bloqueada por disponibilidad de capacidad en la región utilizada.

Por esta razón, el equipo continúa desarrollando localmente mientras se intenta nuevamente el aprovisionamiento.

Esto **no bloquea el desarrollo del código**.

La estrategia actual es:

```text
Desarrollo local
       │
       ▼
Git / GitHub
       │
       ▼
Pruebas
       │
       ▼
OCI cuando la infraestructura esté disponible
```

---

# 22. OCI Object Storage

El proyecto contempla almacenar los paquetes generados en Object Storage.

La estructura prevista es:

```text
demo/
└── {periodo}/
    └── lotes/
        └── {id}/
            └── paquete.json
```

También se contempla una ruta:

```text
aprobados/
```

El almacenamiento del paquete deberá confirmarse solamente después de que el archivo haya sido escrito correctamente.

Esta parte todavía está pendiente de implementación.

---

# 23. Variables de entorno y secretos

Los secretos **no deben subirse al repositorio**.

Utilizar:

```text
.env
```

para valores locales y secretos.

El repositorio solamente debe contener:

```text
.env.example
```

como referencia de las variables necesarias.

Nunca subir:

```text
.env
```

ni claves API, credenciales, claves SSH u otros secretos.

---

# 24. Git y flujo de trabajo

El proyecto utiliza Git y GitHub para trabajar en equipo.

Cada integrante debe:

1. Actualizar su repositorio.
2. Trabajar en su rama correspondiente.
3. Realizar cambios pequeños y relacionados.
4. Probar los cambios localmente.
5. Crear commits descriptivos.
6. Hacer push de la rama.
7. Crear Pull Request cuando corresponda.
8. Revisar conflictos antes de integrar cambios.

---

# 25. Convención de commits

Se recomienda utilizar commits siguiendo una convención tipo Conventional Commits.

Ejemplos:

```text
feat: agregar endpoint de procesamiento
fix: corregir validación del lote
docs: actualizar README
refactor: reorganizar servicio de ingesta
test: agregar pruebas de procesamiento
chore: actualizar configuración docker
```

El primer commit funcional del backend realizado en esta etapa fue:

```text
feat: inicializar backend FastAPI y endpoint mock
```

---

# 26. Estado del backend actual

Actualmente el backend tiene:

```text
backend/app/
│
├── __init__.py
│
├── main.py
│
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── procesamientos.py
│
└── schemas/
    └── __init__.py
```

El backend puede ejecutarse localmente mediante:

```bash
python -m uvicorn backend.app.main:app --reload
```

---

# 27. Estado del frontend

El frontend forma parte de la arquitectura prevista y será construido utilizando:

```text
Next.js
React
TypeScript
Tailwind CSS
```

La interfaz deberá permitir posteriormente:

* Subir lotes JSON/CSV.
* Previsualizar mensajes.
* Enviar el lote al backend.
* Mostrar el procesamiento.
* Mostrar los activos generados.
* Mostrar las fuentes asociadas.

Durante el desarrollo inicial podrán utilizarse mocks mientras el endpoint real del backend no esté terminado.

---

# 28. Datos de prueba

Para el MVP se contempla trabajar inicialmente con datos sintéticos que representen mensajes de una comunidad de Discord.

Esto permite desarrollar y probar el pipeline sin depender inicialmente de una comunidad real.

La demostración prevista contempla una corrida con mensajes sintéticos y generación de activos.

---

# 29. MVP

El objetivo de la primera demostración funcional es conseguir un flujo completo:

```text
Mensajes sintéticos
        │
        ▼
      Ingesta
        │
        ▼
     Limpieza
        │
        ▼
     Análisis IA
        │
        ▼
Generación de activos
        │
        ├── Post
        ├── FAQ
        └── Highlights
        │
        ▼
     OCI Storage
```

La demostración debe permitir comprobar que el procesamiento completo funciona de extremo a extremo.

---

# 30. Próximas tareas

El desarrollo continuará siguiendo el cronograma del proyecto.

Orden general de trabajo:

```text
1. Repositorio y workflow Git
        ↓
2. Infraestructura OCI
        ↓
3. Object Storage
        ↓
4. Docker Compose ARM64
        ↓
5. Herramientas / stack
        ↓
6. Backend FastAPI + endpoint mock
        ↓
7. Frontend Next.js
        ↓
8. Ingesta JSON / CSV
        ↓
9. Integración Gemini
        ↓
10. Worker + PostgreSQL
        ↓
11. Almacenamiento OCI
        ↓
12. Endpoint real
        ↓
13. UI conectada al backend
        ↓
14. Demo End-to-End
```

Las tareas de infraestructura que dependan de disponibilidad de OCI podrán continuar en local hasta que la VM esté disponible.

---

# 31. Documentación

La documentación técnica del proyecto se encuentra en:

```text
docs/
```

Se documentarán progresivamente:

* Arquitectura.
* Pipeline.
* LangGraph.
* Contratos de API.
* Configuración de infraestructura.
* Flujo de despliegue.
* Pruebas.
* Decisiones técnicas.

---

# 32. Cómo empezar a trabajar en el proyecto

Clonar el repositorio:

```bash
git clone git@github.com:No-Country-simulation/G10-CommunityLabE32.git
```

Entrar al proyecto:

```bash
cd G10-CommunityLabE32
```

Crear entorno virtual:

```bash
python3 -m venv .venv
```

Activarlo:

```bash
source .venv/bin/activate
```

Instalar dependencias iniciales:

```bash
python -m pip install fastapi uvicorn
```

Ejecutar backend:

```bash
python -m uvicorn backend.app.main:app --reload
```

Abrir Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 33. Importante para el equipo

Actualmente el proyecto está en desarrollo.

No asumir que todos los módulos descritos en esta documentación están terminados.

### Implementado actualmente

```text
Git / GitHub
        ↓
Backend FastAPI
        ↓
GET /health
        ↓
POST /api/v1/procesamientos
        ↓
Swagger /docs
```

### En construcción

```text
Frontend
Ingesta
Limpieza
Gemini
LangGraph
Worker
PostgreSQL
OCI Object Storage
Docker Compose completo
Endpoint real
Pruebas E2E
```

Antes de modificar una parte del proyecto, revisar la estructura existente y coordinar los cambios con el equipo para evitar conflictos entre ramas.

---

# 34. Equipo

Proyecto:

**G10 CommunityLab E32**

Organización:

**No Country — Simulation**

Repositorio:

```text
No-Country-simulation/G10-CommunityLabE32
```

El trabajo se desarrolla de manera colaborativa mediante GitHub, ramas, commits y Pull Requests.

---

# 35. Visión del producto

Community Radar busca convertir las conversaciones de una comunidad en información accionable.

La idea central es:

```text
Conversaciones
      ↓
Datos estructurados
      ↓
Información útil
      ↓
Inteligencia artificial
      ↓
Contenido
      ↓
Activos de comunicación
```

El sistema permitirá que la información generada por la comunidad pueda convertirse en contenido reutilizable, manteniendo trazabilidad hacia las fuentes originales.

---

# 36. Estado de esta documentación

Este README corresponde al estado actual del proyecto durante la construcción del MVP.

Se actualizará conforme se incorporen:

* Nuevos servicios.
* Nuevos endpoints.
* Procesamiento real.
* Integración con IA.
* Base de datos.
* Docker.
* OCI.
* Frontend.
* Pruebas End-to-End.
* Nuevas decisiones de arquitectura.

---

**G10 CommunityLab E32 — Community Radar**

Construyendo el MVP paso a paso. 🚀
