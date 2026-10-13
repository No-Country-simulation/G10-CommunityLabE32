# Prueba de escala del worker — CommunityLab

## Objetivo

Medir el tiempo de procesamiento de lotes sintéticos
en modo simulado, usando la base aislada `worker_local`
en la VM OCI.

## Entorno

- Rama: `integracion-v1.0`
- Modo: simulado
- Base de datos: `worker_local` (entorno de pruebas)
- Tamaño máximo probado: 500 interacciones por lote
- Los resultados no representan procesamiento con IA externa.

## Resultados

| Interacciones | Tiempo medido | Rendimiento aproximado | Estado |
|---:|---:|---:|---|
| 4 | 0,757 s | 5,3 mensajes/s | terminado |
| 100 | 0,814 s | 122,8 mensajes/s | terminado |
| 300 | 0,991 s | 302,6 mensajes/s | terminado |
| 500 | 0,995 s | 502,8 mensajes/s | terminado |
| 500 (repetición 1) | 1,034 s | 483,8 mensajes/s | terminado |
| 500 (repetición 2) | 1,004 s | 497,9 mensajes/s | terminado |
| 500 (repetición 3) | 1,013 s | 493,5 mensajes/s | terminado |

## Recursos observados

Antes de la prueba de 500 mensajes:

- Memoria disponible: aproximadamente 10 GiB.
- Disco disponible: aproximadamente 39 GiB.
- Worker de producción: `running`.

Después de la prueba de 500 mensajes:

- Memoria disponible: aproximadamente 10 GiB.
- RAM observada del contenedor worker: aproximadamente 40 MiB.
- El worker de producción continuó en estado `running`.

Las cifras de CPU y memoria son observaciones puntuales,
no mediciones máximas ni promedios durante toda la ejecución.

## Conclusiones

- Los lotes de hasta 500 interacciones finalizaron con
  estado `terminado` y sin código de error.
- Tres repeticiones consecutivas de 500 interacciones
  también finalizaron correctamente.
- Los tiempos corresponden al pipeline simulado y a las
  operaciones incluidas en la medición; no deben extrapolarse
  al uso de modelos de IA externos.
- Esta prueba no valida concurrencia, carga sostenida,
  rendimiento de IA real ni el recorrido completo por la API.

## Próximos pasos

1. Medir concurrencia de varios trabajos.
2. Evaluar carga sostenida con límites controlados.
3. Medir por separado el rendimiento con IA real cuando
   la integración esté disponible.
