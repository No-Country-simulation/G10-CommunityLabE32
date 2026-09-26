# Inicializar el backend FastAPI y publicar el contrato POST /api/v1/procesamientos con respuesta simulada (mock)

## Aporte de integración y validación
La implementación del backend ya existe en backend/main.py. Este cambio no crea otro backend ni modifica su lógica: conecta el panel al endpoint mediante /api y el reenvío de Next.js, usa seis interacciones sintéticas compatibles con las fuentes fijas del mock y muestra que el almacenamiento OCI es simulado. Los botones sin implementación quedan deshabilitados.

## Ejecutar sin Docker
Desde la raíz, con un entorno Python activo y las dependencias de backend/requirements.txt instaladas:

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

En otra terminal, desde frontend, usar Node.js 22 y ejecutar npm ci y npm run dev. Abrir http://localhost:3000 y pulsar Disparar Ingesta Mock. El reenvío usa por defecto http://127.0.0.1:8000; API_PROXY_TARGET permite otro destino antes de iniciar desarrollo o compilar.

## Contrato comprobado
Entrada: origen_comunidad, periodo_referencia e interacciones. Cada interacción requiere id, autor, canal, fecha y texto. Respuesta: procesamiento_id, resumen_comunidad, activos_distribucion_generados, alertas_internas y almacenamiento_oci. El mock entrega tres formatos: linkedin, faq y newsletter, y una alerta interna. Entrada incompleta o JSON inválido: 422. GET no sustituye POST: 405.

## Alcance y dependencias
Es una respuesta simulada con contenido fijo. No valida todas las reglas de negocio ni ejecuta IA, worker o persistencia del backend en PostgreSQL/OCI. La diferencia id frente a id_mensaje sigue pendiente de acuerdo con el equipo de datos. El flujo Docker reproducible y su actualización a Node.js 22 se entregan en la rama dependiente chore/docker-compose-arm64; no usar el Dockerfile de main como evidencia de esta validación.

El backend modular backend/app/main.py devuelve un contrato distinto; esta prueba toma explícitamente backend/main.py. No se elimina ni sustituye la implementación modular. Antes de integrar el despliegue común, el equipo debe acordar la implementación y el punto de entrada.
