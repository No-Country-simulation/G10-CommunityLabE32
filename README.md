# G10 CommunityLab E32

> Motor inteligente para transformar interacciones de comunidades digitales en información estructurada, insights y activos de contenido listos para su distribución.

Proyecto desarrollado para la Hackathon G10 Oracle One de No Country.

---

## 🎯 Descripción del proyecto

CommunityLab es una solución inteligente orientada a procesar información generada dentro de comunidades digitales.

El sistema busca transformar conversaciones, preguntas, logros, dudas, bloqueos, testimonios y otras interacciones de una comunidad en:

- Información estructurada.
- Insights.
- Contenido generado mediante IA.
- Alertas internas.
- Activos listos para revisión.
- Paquetes de resultados almacenables en OCI Object Storage.

La fuente principal de información considerada para el MVP es Discord, utilizando únicamente canales autorizados.

El proyecto está diseñado para trabajar inicialmente con datos sintéticos y posteriormente integrar información real de la comunidad bajo las reglas de consentimiento definidas para el proyecto.

---

## 🚀 Objetivo del MVP

El MVP busca construir un flujo completo capaz de:

1. Recibir un lote de mensajes en JSON o CSV.
2. Validar y normalizar los datos.
3. Eliminar duplicados.
4. Analizar los mensajes mediante inteligencia artificial.
5. Identificar sentimiento, temas, relevancia y fuentes.
6. Calcular la relevancia de los momentos detectados.
7. Clasificar cada interacción en una de las rutas definidas.
8. Generar diferentes activos de contenido.
9. Mantener las fuentes originales de cada activo.
10. Permitir revisión, edición, rechazo y aprobación.
11. Registrar las decisiones de curaduría.
12. Almacenar los paquetes generados en OCI Object Storage.
13. Exponer el procesamiento mediante una API.
14. Visualizar resultados mediante un panel web.
15. Integrar progresivamente Discord como fuente en vivo.

---

## 🧠 Las 4 rutas principales del sistema

El pipeline de CommunityLab se organiza alrededor de cuatro rutas:

MENSAJE
↓
INGESTA
↓
ANÁLISIS
↓
SCORING
↓
ROUTER
↓
LOGRO / DUDAS / PERÍODO / BLOQUEO

### 1. Logro

Detecta momentos de logro o progreso.

Salida principal:

Post LinkedIn/X

### 2. Dudas

Detecta dudas recurrentes o preguntas de utilidad para la comunidad.

Salida principal:

FAQ / Tip técnico

### 3. Período

Agrupa información relevante de un período determinado.

Salida principal:

Community Highlights / Newsletter

### 4. Bloqueo

Detecta señales de bloqueo o dificultades que requieren atención.

Salida principal:

Alerta interna

Las alertas de bloqueo son internas y no deben publicarse como contenido de distribución.

---

## 🏗️ Arquitectura general

La arquitectura propuesta para el MVP sigue el siguiente flujo:

Discord / JSON / CSV
↓
INGESTA
↓
LIMPIEZA
↓
ANÁLISIS
↓
SCORING
↓
ROUTER
↓
LANGGRAPH
↓
LOGRO / DUDAS / PERÍODO / BLOQUEO
↓
GENERADORES
↓
CONSOLIDACIÓN
↓
PostgreSQL
↓
API
↓
FRONTEND
↓
CURADURÍA
↓
APROBACIÓN
↓
OCI OBJECT STORAGE

LangGraph actúa como componente de orquestación del pipeline, coordinando los diferentes nodos de procesamiento, análisis, scoring, routing, generación y consolidación.

---

## 🧩 Arquitectura de servicios

La arquitectura de ejecución está diseñada alrededor de Docker Compose.

Los servicios principales previstos son:

Docker Compose
↓
Proxy
↓
Web
↓
API
↓
Worker
↓
PostgreSQL

El Worker será responsable de ejecutar el procesamiento asíncrono y coordinar el pipeline de inteligencia artificial.

Los componentes previstos son:

- Proxy.
- Web.
- API.
- Worker.
- PostgreSQL.

La configuración deberá contemplar:

- Healthchecks.
- Reinicio automático.
- Red privada.
- Imágenes compatibles con ARM64.
- Variables de entorno.
- Separación de secretos.

Estos componentes se implementarán progresivamente de acuerdo con el plan de ejecución.

---

## 🐳 Docker Compose

El proyecto utiliza Docker Compose como mecanismo previsto para levantar el entorno de desarrollo y posteriormente el entorno de ejecución en OCI.

Archivo principal:

docker-compose.yml

La estructura actual del repositorio mantiene además:

infrastructure/
└── docker/

La carpeta infrastructure/docker/ queda destinada a configuraciones y recursos específicos de Docker que puedan incorporarse durante la implementación.

El plan de ejecución contempla los siguientes servicios:

proxy
web
api
worker
postgres

Actualmente, la configuración de Docker Compose se encuentra en etapa inicial y será ampliada progresivamente conforme se implementen los servicios.

---

## ⚙️ Stack tecnológico

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL

El backend será responsable de:

- Exponer la API.
- Recibir lotes de procesamiento.
- Validar los contratos.
- Gestionar los estados.
- Comunicarse con PostgreSQL.
- Coordinar el procesamiento.
- Entregar resultados al frontend.

### Frontend

La arquitectura definida contempla:

- Next.js
- React
- TypeScript
- Tailwind CSS

La estructura inicial del frontend está preparada para desarrollar la interfaz del panel de CommunityLab.

Entre las funcionalidades previstas se encuentran:

- Pantalla de ingesta.
- Carga de JSON/CSV.
- Previsualización de mensajes.
- Visualización de activos.
- Visualización de fuentes.
- Curaduría.
- Edición de borradores.
- Estados de contenido.
- KPIs.
- Alertas.

### Inteligencia Artificial

La arquitectura del plan contempla el uso de:

- Gemini API.
- LangGraph.
- Modelos de lenguaje.
- Prompts especializados.
- Salidas JSON estructuradas.

La API de Gemini será utilizada para analizar los mensajes y generar resultados estructurados.

El sistema deberá contemplar:

- Claves mediante variables de entorno.
- Control de cuotas.
- Manejo de errores.
- Timeouts.
- JSON inválido.
- Modelo de respaldo cuando corresponda.

Las credenciales nunca deben almacenarse directamente en el repositorio.

---

## 🧠 LangGraph

LangGraph será utilizado para construir el módulo central de orquestación del pipeline.

El grafo contempla nodos para:

Ingesta
↓
Análisis
↓
Scoring
↓
Router
↓
Generadores
↓
Consolidación

El estado compartido permitirá transportar la información procesada entre los diferentes nodos.

---

## 📊 Análisis de mensajes

Cada mensaje será procesado para obtener información estructurada.

El análisis contempla como mínimo:

- Sentimiento.
- Temas.
- Relevancia.
- Fuentes.
- Ruta esperada.
- Información necesaria para la generación del activo.

La salida debe respetar el contrato JSON acordado.

Ejemplo conceptual:

{
  "mensaje_id": "m-01",
  "sentimiento": "positivo",
  "temas": [
    "proyecto",
    "aprendizaje"
  ],
  "relevancia": 0.92,
  "fuentes": [
    "discord"
  ],
  "ruta": "logro"
}

El esquema definitivo será documentado y validado antes de integrarse al pipeline definitivo.

---

## 📈 Scoring de relevancia

El sistema contará con un puntuador para identificar los momentos más relevantes de la comunidad.

Los criterios contemplados son:

- Hito logrado.
- Emoción.
- Utilidad.
- Recurrencia.

Los umbrales deberán ser configurables.

El scoring permitirá seleccionar los mensajes o grupos de mensajes con mayor potencial para generar contenido útil.

---

## 📦 Contrato de entrada

El sistema recibirá lotes de información mediante JSON o CSV.

El esquema común deberá permitir representar información como:

{
  "mensaje_id": "m-01",
  "autor": "usuario_demo",
  "canal": "testimonios",
  "fecha": "2026-09-22T10:00:00",
  "texto": "Finalmente terminé mi proyecto."
}

Los datos deberán ser:

- Validados.
- Normalizados.
- Deduplicados.

El lote común será utilizado tanto por los datos sintéticos como por la futura integración con Discord.

---

## 🧪 Dataset del MVP

Para la evaluación inicial se utilizará un dataset controlado con autores ficticios.

El plan contempla:

- Casos m-01 a m-06.
- Entre 30 y 50 mensajes etiquetados de referencia.
- Datos estructurados en JSON/CSV.
- Uso del lote para evaluar el comportamiento de las cuatro rutas.

El dataset etiquetado permitirá comparar:

Resultado esperado
↓
Resultado producido por IA
↓
Ajuste de prompts y umbrales

---

## 🔄 Pipeline de procesamiento

El pipeline general es:

1. INGESTA
↓
2. VALIDACIÓN
↓
3. NORMALIZACIÓN
↓
4. DEDUPLICACIÓN
↓
5. ANÁLISIS IA
↓
6. SCORING
↓
7. ROUTER
↓
8. GENERACIÓN
↓
9. CONSOLIDACIÓN
↓
10. CURADURÍA
↓
11. APROBACIÓN
↓
12. ALMACENAMIENTO OCI

---

## 🧵 Worker

El procesamiento será ejecutado de forma asíncrona mediante un Worker.

El Worker será integrado dentro de Docker Compose.

Responsabilidades previstas:

- Recibir trabajos.
- Procesar lotes.
- Ejecutar el pipeline.
- Coordinar LangGraph.
- Gestionar llamadas de IA.
- Actualizar estados.
- Manejar errores.
- Registrar resultados.

El Worker también servirá como punto de integración para componentes de Discord e inteligencia artificial.

---

## 🗄️ PostgreSQL

PostgreSQL será la base de datos principal del proyecto.

El modelo contempla entidades relacionadas con:

- Interacciones.
- Activos.
- Estados.
- Decisiones.
- Consentimiento.
- Procesamientos.

Los estados de curaduría deberán diferenciar claramente:

Generado
↓
Revisado
↓
Aprobado

Generación, aprobación y consentimiento son conceptos diferentes y deberán mantenerse separados.

---

## 📝 Curaduría

El panel permitirá gestionar los activos generados por el sistema.

Las operaciones contempladas son:

Listar
↓
Editar
↓
Rechazar
↓
Aprobar

Cada decisión deberá registrarse en PostgreSQL.

La versión aprobada deberá poder almacenarse posteriormente en OCI Object Storage.

---

## 🔐 Consentimiento

Para versiones identificables se contempla un mecanismo de consentimiento verificable.

Durante la demostración se utilizarán:

- Autores ficticios.
- Datos sintéticos.
- Etiqueta visible de aprobación de demostración.

El objetivo es separar claramente el contenido generado de cualquier publicación real sin consentimiento.

---

## ☁️ Oracle Cloud Infrastructure

El proyecto contempla desplegar la solución utilizando Oracle Cloud Infrastructure (OCI).

La infraestructura prevista incluye:

OCI
↓
VM Always Free
↓
Red
↓
Docker Compose
↓
Object Storage

La VM prevista en el plan es:

Ampere A1 ARM64
Ubuntu

La infraestructura deberá utilizar recursos compatibles con la capa Always Free cuando sea posible.

---

## 📦 OCI Object Storage

Object Storage será utilizado para almacenar los paquetes generados y las versiones aprobadas.

La estructura prevista incluye:

demo/
└── {periodo}/
    └── lotes/
        └── {id}/
            └── paquete.json

aprobados/

El paquete generado deberá almacenarse y confirmarse únicamente después de haber sido escrito correctamente.

---

## 🌐 API

La API será desarrollada con FastAPI.

El contrato inicial contempla:

POST /api/v1/procesamientos

Durante la primera etapa podrá utilizarse una respuesta simulada para desbloquear el desarrollo paralelo de frontend y backend.

Posteriormente se implementará el procesamiento real.

La respuesta final deberá contemplar información como:

procesamiento_id
resumen
activos
alertas
almacenamiento_oci

---

## 📡 Integración con Discord

Durante las siguientes etapas se integrará Discord como fuente de información en vivo.

El sistema deberá:

1. Leer únicamente canales autorizados.
2. Obtener los mensajes.
3. Normalizarlos al mismo esquema utilizado por el lote JSON/CSV.
4. Enviarlos al pipeline.
5. Analizarlos.
6. Generar las rutas correspondientes.

También se contempla un bot de Discord capaz de:

- Responder dudas técnicas.
- Detectar testimonios.
- Detectar bloqueos.
- Disparar alertas internas.

---

## 📊 Dashboard y KPIs

El panel deberá mostrar información real proveniente del backend.

KPIs previstos:

- Mensajes.
- Activos.
- Alertas.
- Paquete OCI.
- Sentimiento.
- Temas en tendencia.

También se contempla mostrar las fuentes asociadas a cada activo.

---

## 📁 Estructura actual del repositorio

La estructura actual del repositorio es:

G10-CommunityLabE32/
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   │
│   └── tests/
│
├── data/
│   ├── examples/
│   ├── processed/
│   │   └── .gitkeep
│   └── raw/
│       └── .gitkeep
│
├── docs/
│   └── .gitkeep
│
├── frontend/
│   └── .gitkeep
│
├── infrastructure/
│   ├── docker/
│   │   └── .gitkeep
│   └── oci/
│       └── .gitkeep
│
├── pipelines/
│
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── docker-compose.yml
├── LICENSE
└── README.md

Esta estructura corresponde al estado actual del repositorio y está preparada para que cada componente se implemente progresivamente.

---

## 📂 Organización del Backend

El backend está preparado con una separación por responsabilidades:

backend/
└── app/
    ├── api/
    │   └── routes/
    │
    ├── database/
    │
    ├── models/
    │
    ├── schemas/
    │
    └── services/

### api/routes

Contendrá los endpoints de FastAPI.

### database

Configuración y conexión con PostgreSQL.

### models

Modelos de datos mediante SQLAlchemy.

### schemas

Contratos de entrada y salida mediante Pydantic.

### services

Lógica de negocio y comunicación con otros componentes.

### tests

Pruebas automatizadas del backend.

---

## 📂 Datos

La estructura de datos está dividida en:

data/
├── examples/
├── processed/
└── raw/

### raw

Datos originales sin procesar.

### processed

Datos limpiados y preparados.

### examples

Ejemplos y datos utilizados para pruebas o documentación.

---

## 📂 Infraestructura

infrastructure/
├── docker/
└── oci/

### Docker

Configuraciones relacionadas con contenedores y despliegue.

### OCI

Configuraciones y recursos relacionados con Oracle Cloud Infrastructure.

El archivo principal de orquestación se encuentra actualmente en la raíz:

docker-compose.yml

---

## 📂 Pipelines

La carpeta:

pipelines/

está destinada a contener los diferentes procesos de transformación de datos e inteligencia artificial.

La arquitectura contempla componentes relacionados con:

Ingesta
↓
Limpieza
↓
Análisis
↓
Embeddings
↓
Scoring
↓
Router
↓
Generadores
↓
Consolidación

---

## 🔐 Variables de entorno

Las credenciales y configuraciones sensibles deben mantenerse fuera del repositorio.

Archivo de referencia:

.env.example

Nunca deben subirse al repositorio:

.env
API Keys
Secret Keys
Tokens
Credenciales de OCI
Credenciales de PostgreSQL
Credenciales de Discord

Las claves deben gestionarse mediante variables de entorno.

---

## 🌿 Git y GitHub

El proyecto utiliza Git y GitHub para el control de versiones y colaboración.

El repositorio cuenta con:

.github/
└── PULL_REQUEST_TEMPLATE.md

También cuenta con:

CONTRIBUTING.md

Estos archivos establecen las reglas de colaboración iniciales del equipo.

### Rama principal

La rama principal actual es:

master

Esta rama representa la versión principal y estable del proyecto.

No se deben realizar cambios directamente sobre master.

### Convención de ramas

Las ramas se crean según el tipo de trabajo:

feature/<nombre-tarea>
fix/<nombre-error>
chore/<nombre-tarea>
docs/<nombre-tarea>

Ejemplos:

feature/backend-api
feature/database-model
feature/data-ingestion
fix/postgres-connection
chore/docker-config
docs/architecture

Las ramas representan tareas concretas. No es necesario crear ramas permanentes o vacías para cada categoría.

La estrategia definitiva de organización de ramas queda sujeta al acuerdo del equipo.

### Convención de commits

Los commits utilizan la estructura:

tipo: descripción breve

Tipos:

- feat → nueva funcionalidad.
- fix → corrección.
- docs → documentación.
- test → pruebas.
- refactor → reorganización.
- chore → configuración o mantenimiento.

Ejemplo:

feat: agregar endpoint de procesamientos

### Pull Request

Los cambios destinados a master deben realizarse mediante Pull Request.

El Pull Request debe indicar:

- Qué cambio se realizó.
- Qué tarea del cronograma corresponde.
- Qué archivos fueron modificados.
- Qué pruebas se realizaron.
- Si fue necesario actualizar la documentación.

La plantilla se encuentra en:

.github/PULL_REQUEST_TEMPLATE.md

### Revisión

Antes del merge, el Pull Request debe ser revisado por otro integrante del equipo.

La revisión debe comprobar:

- Correspondencia con la tarea.
- Ausencia de errores evidentes.
- Respeto por la estructura del proyecto.
- Ausencia de credenciales o información sensible.
- Cumplimiento de las convenciones establecidas.

La persona responsable de la aprobación final y del merge será definida por el equipo.

---

## 👥 Equipo

### Catálogo de integrantes

| ID | Integrante | Rol principal |
|---|---|---|
| EQ-01 | Jose Angel Olan de los Santos | Data Engineer |
| EQ-02 | Ianjaner Alfonso Beltran Guañarita | Full Stack Developer |
| EQ-03 | Fredy Pachon | Backend Developer |
| EQ-04 | Zeus Adonis Javier Diaz Herrera | AI Engineer |
| EQ-05 | Paulo Andres Escobar Solorzano | Autonomous Agent Engineer |
| EQ-06 | Santiago Horta Hurtado | Autonomous Agent Engineer |
| EQ-07 | Fabian Hernández Alejandro | Prompt Engineer |
| EQ-08 | Vania Sherel Cruz Hernandez | Vibe Coder |
| EQ-09 | Elizabeth Aguilar | Project Manager |

Los roles corresponden a la organización definida en el plan de ejecución.

---

## 📅 Plan de ejecución

El proyecto se desarrolla mediante un plan de ejecución de:

5 semanas de ejecución
+
Demo Day

El plan contempla las siguientes etapas principales:

SEMANA 0
Organización y kickoff
↓
SEMANA 1
Infraestructura y bases del MVP
↓
SEMANA 2
Pipeline, IA y generación
↓
SEMANA 3
Discord, curaduría y diferenciales
↓
SEMANA 4
Pruebas cloud y estabilización
↓
SEMANA 5
Correcciones, evidencia y entrega
↓
DEMO DAY
Presentación final

El plan establece además reuniones de:

- Sprint Planning.
- Reunión diaria.
- Sprint Demo.
- Pre Demo.
- Demo Day.

---

## 🗓️ Semana 1

Los objetivos principales incluyen:

- Finalizar el repositorio GitHub.
- Definir ramas y convenciones.
- Configurar .gitignore.
- Configurar OCI.
- Crear VM Always Free.
- Crear Object Storage.
- Preparar Docker Compose.
- Inicializar FastAPI.
- Publicar el contrato inicial de la API.
- Inicializar frontend.
- Diseñar modelo PostgreSQL.
- Definir esquema JSON/CSV.
- Preparar dataset etiquetado.
- Configurar Gemini.
- Diseñar el pipeline de cuatro rutas.
- Definir prompts iniciales.
- Definir identidad visual.

---

## 🗓️ Semana 2

Los objetivos principales incluyen:

- Implementar ingesta JSON/CSV.
- Validar y normalizar datos.
- Deduplicar mensajes.
- Integrar Gemini.
- Analizar sentimiento, temas, relevancia y fuentes.
- Implementar scoring.
- Construir grafo LangGraph.
- Implementar router.
- Crear generadores.
- Manejar errores de Gemini.
- Implementar worker.
- Gestionar estados en PostgreSQL.
- Guardar paquetes en OCI.
- Implementar endpoint real.
- Probar el sistema con Postman.

---

## 🗓️ Semana 3

Los objetivos principales incluyen:

- Integrar Discord.
- Leer canales autorizados.
- Normalizar mensajes.
- Implementar bot.
- Detectar testimonios.
- Detectar bloqueos.
- Implementar endpoints de curaduría.
- Implementar aprobación y rechazo.
- Registrar decisiones.
- Implementar editor de borradores.
- Gestionar consentimiento.
- Mostrar KPIs.
- Generar las tres transformaciones principales.
- Validar las cuatro rutas.

---

## 🗓️ Semana 4

La prioridad será estabilizar el sistema.

Se contemplan:

- Pruebas end-to-end.
- Pruebas de reinicio.
- Persistencia de PostgreSQL.
- Persistencia de OCI.
- Pruebas de fallos.
- JSON inválido.
- Errores de Gemini.
- Falta de cuota.
- OCI inaccesible.
- Pruebas de escala.
- Endurecimiento del despliegue.
- HTTPS.
- Gestión de secretos.
- Respaldo de PostgreSQL.
- Pulido visual.

Desde el 12/10 se contempla el congelamiento de funcionalidades:

Solo pruebas
+
Correcciones
+
Mejoras visuales

---

## 🗓️ Semana 5

La última etapa estará enfocada en:

- Correcciones finales.
- Evidencia.
- Documentación.
- README final.
- Guía de despliegue.
- Prueba desde una VM limpia.
- Evidencia de OCI.
- Preparación del pitch.
- Grabación del video demo.
- Edición del video.
- Verificación de enlaces.
- Checklist final.
- Preparación del Demo Day.

---

## 🎬 Demo del MVP

La demostración final deberá mostrar un flujo completo:

6 mensajes sintéticos
↓
Ingesta
↓
Análisis
↓
Scoring
↓
Router
↓
4 rutas
↓
Generación
↓
Curaduría
↓
Aprobación
↓
OCI
↓
Panel

El plan contempla como demostración principal:

Logro
↓
LinkedIn/X

Duda
↓
FAQ/Tip

Período
↓
Newsletter / Highlights

Bloqueo
↓
Alerta interna

---

## 🧪 Pruebas

El sistema deberá contar progresivamente con pruebas para:

- Validación de JSON.
- Validación de CSV.
- Duplicados.
- Mensajes incompletos.
- IA.
- JSON inválido.
- Timeouts.
- Cuotas.
- Router.
- Generadores.
- API.
- PostgreSQL.
- Worker.
- OCI.
- Discord.
- Curaduría.
- Persistencia.
- Reinicio de servicios.

---

## 📦 Estado del proyecto

El repositorio se encuentra actualmente en la etapa inicial de ejecución.

La base estructural del monorepo ya está creada y organizada para comenzar la implementación progresiva de los componentes definidos en el plan.

Actualmente se dispone de:

✓ Repositorio GitHub
✓ Estructura de monorepo
✓ Backend estructurado
✓ Estructura inicial del frontend preparada
✓ Data organizada
✓ Docs preparada
✓ Infrastructure preparada
✓ Docker Compose en raíz
✓ .env.example
✓ .gitignore
✓ CONTRIBUTING.md
✓ Pull Request Template

Los componentes funcionales serán implementados progresivamente de acuerdo con el plan de ejecución.

---

## 🎯 Objetivo final

El objetivo de CommunityLab es convertir:

CONVERSACIONES
↓
DATOS
↓
ANÁLISIS
↓
INSIGHTS
↓
DECISIONES
↓
CONTENIDO
↓
CURADURÍA
↓
ACTIVOS APROBADOS
↓
DISTRIBUCIÓN

utilizando:

IA
+
LangGraph
+
FastAPI
+
Next.js
+
PostgreSQL
+
Docker Compose
+
Discord
+
OCI

---

## 🏁 Resultado esperado

Al finalizar el proyecto, CommunityLab deberá demostrar un flujo funcional capaz de:

Recibir información
↓
Procesarla
↓
Comprenderla
↓
Clasificarla
↓
Seleccionar los momentos relevantes
↓
Generar contenido
↓
Mostrar las fuentes
↓
Permitir curaduría
↓
Registrar aprobación
↓
Almacenar el resultado
↓
Demostrarlo mediante una interfaz web

---

## 📌 Nota

Este README refleja la arquitectura y el plan de ejecución definidos para G10 CommunityLab E32.

La implementación se realizará progresivamente y el repositorio evolucionará conforme cada componente sea desarrollado, probado e integrado.

Las funcionalidades descritas como futuras o planificadas no deben interpretarse como funcionalidades ya implementadas.

El objetivo es mantener el README alineado con el estado real del repositorio y actualizarlo conforme avance la ejecución del proyecto.

---

## 📄 Documentación relacionada

### Guía de contribución

CONTRIBUTING.md

### Plantilla de Pull Request

.github/PULL_REQUEST_TEMPLATE.md

### Variables de entorno

.env.example

### Docker Compose

docker-compose.yml

### Licencia

LICENSE