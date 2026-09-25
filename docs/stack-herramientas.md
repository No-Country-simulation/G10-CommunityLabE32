# Stack de Herramientas — G10 CommunityLab E32

## Herramientas principales

| Herramienta | Uso dentro del proyecto |
|---|---|
| OCI | Infraestructura y despliegue del proyecto en la nube. |
| FastAPI | Backend y exposición de los endpoints de la aplicación. |
| Next.js | Desarrollo del frontend y panel de la aplicación. |
| LangGraph | Orquestación del flujo de procesamiento y análisis. |
| Gemini | Análisis de los mensajes y generación de resultados estructurados. |

## Estado del stack

- **OCI:** infraestructura objetivo del proyecto.
- **FastAPI:** backend inicializado y endpoint mock disponible.
- **Next.js:** frontend previsto para el panel de la aplicación.
- **LangGraph:** utilizado como base para orquestar el flujo de procesamiento.
- **Gemini:** previsto para el análisis de los mensajes y la obtención de resultados estructurados.

## Integraciones previstas

El proyecto contempla posteriormente:

- Integración de Gemini para analizar cada mensaje.
- Análisis de sentimiento, temas, relevancia y fuentes.
- Salida estructurada en JSON.
- Integración con PostgreSQL.
- Integración del worker mediante Docker Compose.
- Despliegue y pruebas en OCI.

## Nota de infraestructura

La VM de OCI continúa pendiente debido a la disponibilidad de capacidad de infraestructura. El desarrollo local puede continuar mientras se resuelve esta dependencia.

