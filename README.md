# G10 CommunityLab E32

> Motor inteligente para transformar interacciones de comunidades digitales en información, insights y activos de contenido listos para su distribución.

Proyecto desarrollado para la **Hackathon G10 Oracle One de No Country**.

---

## 🎯 Descripción del proyecto

**CommunityLab** es una solución orientada al procesamiento inteligente de información generada dentro de comunidades digitales.

El sistema busca transformar conversaciones, preguntas, testimonios, experiencias, proyectos y otras interacciones de los miembros de una comunidad en información estructurada y contenido que pueda ser utilizado posteriormente en diferentes canales de comunicación y distribución.

Para el desarrollo inicial se contempla trabajar principalmente con información proveniente de comunidades como **Discord**.

El objetivo es reducir el trabajo manual necesario para revisar grandes cantidades de conversaciones y facilitar la identificación de información relevante para marketing, comunicación y gestión de comunidades.

---

## 🚀 Objetivo del MVP

El MVP busca implementar un flujo completo capaz de:

1. Recibir un conjunto de mensajes o interacciones de una comunidad.
2. Ingerir y preparar la información.
3. Limpiar y normalizar los datos.
4. Analizar las interacciones utilizando inteligencia artificial.
5. Identificar sentimiento, temas y relevancia.
6. Detectar preguntas frecuentes, testimonios e historias de éxito.
7. Generar diferentes formatos de contenido.
8. Permitir la revisión y aprobación de los contenidos generados.
9. Almacenar los activos e informes en **OCI Object Storage**.
10. Exponer los resultados mediante una API y/o una interfaz amigable.

---

## 🔄 Flujo general

```text
Discord / Comunidad
        ↓
Ingesta
        ↓
Limpieza y normalización
        ↓
Análisis con IA
        ↓
Sentimiento
        ↓
Temas
        ↓
Relevancia
        ↓
FAQs / Testimonios / Historias de éxito
        ↓
Generación de contenido
        ↓
LinkedIn / Resumen / FAQ / Testimonio
        ↓
Revisión y aprobación
        ↓
OCI Object Storage
        ↓
API / Interfaz
```

---

## 🏗️ Arquitectura

El proyecto está organizado como un **monorepo**, permitiendo que los diferentes integrantes del equipo trabajen sobre una misma base de código y puedan colaborar entre las diferentes áreas del proyecto.

La arquitectura se divide inicialmente en:

- Backend
- Frontend
- Pipelines de procesamiento
- Inteligencia Artificial
- Datos
- Infraestructura
- Documentación

La arquitectura es evolutiva y podrá modificarse durante el desarrollo de acuerdo con las necesidades del proyecto y las decisiones del equipo.

---

## ⚙️ Stack tecnológico

### Backend

- **Python**
- **FastAPI**
- **Pydantic**
- **SQLAlchemy**
- **PostgreSQL**

El backend será responsable de la lógica de la aplicación, exposición de APIs, gestión de datos y comunicación entre los diferentes componentes del sistema.

### Inteligencia Artificial y procesamiento

Se contempla utilizar herramientas y tecnologías orientadas al procesamiento de lenguaje natural y generación de contenido.

Entre los componentes previstos se encuentran:

- NLP
- Modelos de lenguaje (LLM)
- Análisis de sentimiento
- Clasificación de temas
- Evaluación de relevancia
- Detección de FAQs
- Detección de testimonios
- Detección de historias de éxito
- Generación de contenido
- Embeddings
- Búsqueda semántica

La selección definitiva de modelos, frameworks y herramientas será determinada por el equipo durante el desarrollo.

### Datos

- PostgreSQL
- JSON
- CSV
- Datos simulados
- Datos provenientes de comunidades digitales

### Infraestructura

- Docker
- Oracle Cloud Infrastructure (OCI)
- OCI Object Storage
- Recursos de la capa Always Free

### Control de versiones

- Git
- GitHub
- Pull Requests

### Frontend

La tecnología definitiva del frontend será definida por el equipo.

La interfaz deberá facilitar la visualización de los resultados y la revisión de los contenidos generados.

---

## 🔄 Pipeline de procesamiento

El procesamiento de los datos se organiza inicialmente en diferentes etapas:

```text
Ingestion
    ↓
Cleaning
    ↓
Analysis
    ↓
Embeddings
    ↓
Content Generation
```

### Ingestion

Recepción y preparación de los datos provenientes de las diferentes fuentes.

### Cleaning

Limpieza, normalización y preparación de los mensajes antes de iniciar el análisis.

### Analysis

Procesamiento de las interacciones utilizando inteligencia artificial para identificar:

- Sentimiento
- Temas
- Relevancia
- FAQs
- Testimonios
- Historias de éxito

### Embeddings

Generación de representaciones vectoriales que permitan realizar búsquedas semánticas y otros procesos relacionados con inteligencia artificial.

### Content Generation

Transformación de los insights encontrados en diferentes formatos de contenido.

---

## ✍️ Generación de contenido

Uno de los componentes principales de CommunityLab es la transformación de información de la comunidad en activos de distribución.

El MVP deberá generar como mínimo **dos formatos diferentes**.

Entre los formatos considerados se encuentran:

- Publicaciones para LinkedIn.
- Resúmenes semanales de la comunidad.
- FAQs.
- Tips educativos.
- Casos de éxito.
- Testimonios.

Los formatos definitivos serán seleccionados por el equipo durante el desarrollo.

---

## 📊 Datos de entrada

El sistema podrá trabajar inicialmente con datos simulados o datos reales disponibles para el proyecto.

Una interacción podrá contener información como:

```text
Fuente
Fecha
Autor
Canal
Tipo de interacción
Texto
```

### Fuentes consideradas

- Discord
- CSV
- JSON
- Formularios
- Webhooks
- Foros
- Otras fuentes que puedan integrarse posteriormente

---

## 📦 Resultados esperados

El procesamiento de las interacciones deberá permitir obtener información estructurada como:

- Total de interacciones.
- Sentimiento predominante.
- Temas principales.
- Contenido relevante.
- Preguntas frecuentes.
- Testimonios.
- Historias de éxito.
- Insights de la comunidad.
- Contenido generado.
- Estado de revisión.
- Estado de almacenamiento.

---

## ☁️ OCI Object Storage

**OCI Object Storage** forma parte de los requisitos principales del MVP.

Será utilizado para almacenar los activos generados, informes y archivos estructurados producidos durante el procesamiento.

Se utilizarán recursos de la capa **Always Free de OCI**.

Una posible organización de los archivos será:

```text
assets/
reports/
json/
```

La estructura definitiva del almacenamiento será definida durante la implementación.

---

## 🖥️ Interfaz y curaduría

La aplicación deberá contar con una interfaz que permita visualizar los resultados obtenidos durante el procesamiento.

La interfaz podrá incluir:

- Visualización de métricas.
- Resultados del análisis.
- Temas identificados.
- Sentimiento.
- FAQs.
- Testimonios.
- Historias de éxito.
- Contenidos generados.
- Revisión de contenidos.
- Aprobación o curaduría.

La tecnología utilizada para esta interfaz será definida por el equipo.

---

## 🐳 Docker

Docker será utilizado para facilitar la configuración y ejecución del proyecto en los diferentes entornos de desarrollo.

Inicialmente se contempla utilizar PostgreSQL mediante Docker para facilitar el trabajo local del equipo.

La configuración podrá ampliarse posteriormente a otros servicios del proyecto.

---

## 🗄️ Base de datos

PostgreSQL será utilizado para almacenar la información estructurada que necesite el sistema.

La estructura de la base de datos podrá evolucionar a medida que se definan los modelos y requerimientos definitivos.

---

## 📁 Estructura del proyecto

```text
G10-CommunityLabE32/
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
├── frontend/
│
├── pipelines/
│   ├── ingestion/
│   ├── cleaning/
│   ├── analysis/
│   └── embeddings/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── examples/
│
├── docs/
│
├── infrastructure/
│   ├── docker/
│   └── oci/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## 👥 Equipo

### Integrantes y roles actuales

| Integrante | Rol |
|---|---|
| Janjaner Alfonso Beltrán Guañarita | Full Stack Developer |
| Tareck Fredy Pachon | Backend Developer |
| Zeus Adonis Javier Diaz Herrera | AI Engineer |
| Paulo Andres Escobar Solorzano | Autonomous Agent Engineer |
| Santiago Horta Hurtado | Autonomous Agent Engineer |
| Fabian Hernández Alejandro | Prompt Engineer |
| Jose Angel Olan de los Santos | Data Engineer |
| Vania Sherel Cruz Hernandez | Vibe Coder |

### 🤝 Forma de trabajo

Los roles representan la **organización inicial del equipo**.

No se consideran límites exclusivos de trabajo. El proyecto será colaborativo y cualquier integrante podrá participar en diferentes componentes, proponer cambios, realizar correcciones y aportar mejoras.

A medida que avance la Hackathon se podrán definir nuevas responsabilidades, ramas, revisiones y reglas de colaboración.

---

## 🌿 Git y GitHub

El proyecto utiliza Git y GitHub como herramientas principales para el control de versiones y trabajo colaborativo.

La metodología de trabajo podrá incluir:

- Ramas de desarrollo.
- Pull Requests.
- Revisión de código.
- Commits organizados.
- Integración de cambios.
- Documentación de decisiones técnicas.

Durante la etapa inicial se mantendrá una estructura flexible para permitir que el equipo pueda proponer y realizar cambios.

Las reglas definitivas de colaboración serán acordadas posteriormente por el equipo.

---

## 🧪 Demostración del MVP

La demostración deberá mostrar un flujo completo desde la información original hasta los activos generados.

```text
Mensajes de la comunidad
        ↓
Ingesta
        ↓
Limpieza
        ↓
Análisis con IA
        ↓
Identificación de insights
        ↓
Generación de contenido
        ↓
Revisión / aprobación
        ↓
Almacenamiento en OCI
```

El objetivo de la demostración será mostrar cómo un conjunto de interacciones puede convertirse en información estructurada y posteriormente en diferentes activos de contenido.

---

## 📚 Documentación

La documentación técnica del proyecto estará disponible en:

```text
docs/
```

Se incluirán progresivamente documentos relacionados con:

- Arquitectura.
- Requerimientos.
- Flujo de datos.
- Decisiones técnicas.
- Instalación.
- Configuración.
- Desarrollo.
- Despliegue.
- Uso del sistema.

---

## 🚧 Estado del proyecto

Actualmente **CommunityLab se encuentra en fase inicial de planificación y estructuración**.

En esta etapa se está trabajando en:

- Definición de arquitectura.
- Estructura del repositorio.
- Organización del equipo.
- Selección de tecnologías.
- Definición del flujo de datos.
- Preparación del entorno de desarrollo.

La arquitectura, tecnologías y responsabilidades podrán evolucionar durante la Hackathon de acuerdo con las necesidades del proyecto y las decisiones del equipo.

---

## 🎯 Meta del proyecto

Construir un MVP funcional capaz de transformar la actividad de una comunidad digital en información útil y activos de contenido.

```text
DATOS
  ↓
INFORMACIÓN
  ↓
INSIGHTS
  ↓
CONTENIDO
  ↓
ACTIVOS LISTOS PARA DISTRIBUIR
```

Utilizando inteligencia artificial, procesamiento de datos, automatización, una arquitectura organizada y **OCI Object Storage** como parte de la infraestructura del proyecto.

---

## 📌 Nota

Este repositorio representa la base inicial del proyecto **G10 CommunityLab E32**.

La estructura y las decisiones técnicas podrán cambiar durante el desarrollo a medida que el equipo valide la solución y avance en la implementación del MVP.