# Guion de la demo · CommunityLab

Duración objetivo: **7 minutos** + preguntas. Se presenta en https://communitylab.nodnexa.com con una cuenta
de administrador. El documento de la hackathon pide mostrar **el procesamiento de un lote de mensajes y la
generación simultánea de los activos de distribución**: el bloque 2 es el centro de la demo.

> Completar la columna «Presenta» con el equipo. Cada bloque cabe en una persona.

| # | Bloque | Tiempo | Presenta |
|---|---|---|---|
| 1 | El problema y la solución | 0:45 | |
| 2 | Procesar un lote en vivo | 2:00 | |
| 3 | Análisis de la comunidad | 1:15 | |
| 4 | Curaduría y OCI | 1:45 | |
| 5 | Discord en tiempo real | 0:45 | |
| 6 | Arquitectura y cierre | 0:30 | |

---

## Antes de empezar (checklist, 30 minutos antes)

- [ ] Entrar a la plataforma con la cuenta de administrador y dejar el idioma en **Español**.
- [ ] En **Ingesta → Datos cargados**, que solo esté el lote base `Demo call center · 2026-W43`.
- [ ] Tener a mano el archivo del bloque 2: `Datos demo 20-10-26/subir/demo_call_center_2026-W42.json`
      (124 mensajes) o `prueba_manual_12.json` (12 mensajes, más rápido).
- [ ] Si ese lote ya se subió en un ensayo, **eliminarlo** en Datos cargados: el mismo archivo con el mismo
      nombre y período no se procesa dos veces.
- [ ] Probar que el bot responde en el canal de Discord autorizado.
- [ ] Cerrar otras pestañas y subir el zoom del navegador a 110–125 % para que se lea en la pantalla compartida.
- [ ] **Plan B** (si Gemini no responde o tarda): mostrar el bloque 2 con el lote base ya procesado y
      explicar el flujo; el resto de la demo no depende de la carga en vivo.

---

## 1. El problema y la solución (0:45) · Resumen

**Pantalla:** Resumen (la presentación «Grandes ideas. De tu comunidad.» está arriba).

- Las comunidades generan a diario logros, dudas repetidas y testimonios, pero ese valor se pierde en el
  historial de los canales.
- CommunityLab escucha la comunidad, la analiza con IA y propone contenido listo para revisar: posts para
  LinkedIn y X, preguntas frecuentes, resúmenes semanales y alertas internas.
- Señalar las cuatro tarjetas: total de mensajes, borradores pendientes, aprobados y alertas internas.

## 2. Procesar un lote en vivo (2:00) · Ingesta de datos

**Pantalla:** Ingesta de datos → Fuente de datos.

1. Escribir **Nombre:** `Demo call center` y **Período:** `2026-W42`, marcar **«Cerrar período y generar
   resumen»** y soltar el archivo.
2. Pulsar **Iniciar procesamiento**. Mientras avanza el seguimiento del trabajo, contar qué pasa por dentro:
   - el lote se valida y se deduplica (formato JSON, JSONL o CSV);
   - un **grafo de LangGraph** analiza cada mensaje con **Gemini**: sentimiento, tipo, tema y relevancia;
   - un **router** decide: un logro relevante genera un post, una duda de dos o más personas genera una FAQ,
     un bloqueo genera una alerta interna y el cierre del período genera el Community Highlights.
3. Al terminar, leer el resultado: mensajes procesados, contenidos generados y alertas.
   **Ese es el requisito central: un lote entra y salen varios activos a la vez.**

Con la cuenta gratuita de Gemini una semana tarda 1–2 minutos; si se alarga, pasar al bloque 3 y volver.

## 3. Análisis de la comunidad (1:15) · Interacciones y Analítica

**Pantalla:** Interacciones.

- Las seis tarjetas de sentimiento filtran la tabla: tocar **Negativos** y mostrar que solo quedan
  negativos; volver a **Total**.
- Usar la búsqueda (por ejemplo, «reembolso»).

**Pantalla:** Analítica.

- Distribución del sentimiento, embudo de curaduría y **temas detectados** (reembolsos, envíos, cuentas…).
- El selector de lotes permite comparar semanas.

## 4. Curaduría y OCI (1:45) · Curaduría

**Pantalla:** Curaduría → Pendientes.

1. Abrir una **FAQ** generada y pulsar **Ver fuentes**: cada contenido conserva los mensajes que lo originaron.
2. Si hay **advertencias de fidelidad**, mostrarlas: el sistema marca cifras o detalles que no están en las
   fuentes. Ningún contenido se publica sin revisión humana.
3. **Aprobar como definitivo.** En **Aprobados** aparece la etiqueta verde **«Guardado en OCI»**: la versión
   aprobada se copió al bucket de **OCI Object Storage** (requisito obligatorio), con la identidad de la VM y
   sin llaves.
4. Mostrar los botones **LinkedIn** y **X**: abren la red con el texto ya escrito; la persona revisa y publica.
5. (Opcional) **Rechazar** otro borrador: pide el motivo y queda en **Denegados**.

## 5. Discord en tiempo real (0:45)

- Escribir en el canal autorizado una duda o un bloqueo. El **bot** responde o avisa al equipo en vivo.
- En **Ingesta → Procesar mensajes pendientes de Discord**, traer esos mensajes sin cerrar la semana.

## 6. Arquitectura y cierre (0:30)

- Todo corre en una **VM Always Free de OCI** (ARM) con Docker Compose y HTTPS; los activos aprobados se
  guardan en **OCI Object Storage**.
- Next.js, FastAPI, PostgreSQL, LangGraph y Gemini; interfaz en español, inglés y portugués.
- Cierre: «CommunityLab convierte las conversaciones de una comunidad en contenido revisado y listo para
  publicar, sin perder de vista de dónde salió cada idea».

---

## Preguntas probables

| Pregunta | Respuesta corta |
|---|---|
| ¿Qué pasa si la IA inventa algo? | Los controles de fidelidad marcan cifras, archivos o detalles que no están en las fuentes, y todo pasa por aprobación humana. |
| ¿Se publica solo? | No. Los botones abren LinkedIn o X con el texto; la persona confirma la publicación. |
| ¿Cómo cumplen OCI Object Storage? | Cada versión aprobada se sube a un bucket privado Always Free con la identidad de la VM (instance principal), sin llaves guardadas. |
| ¿Qué pasa con los datos personales? | El acceso es por cuentas con roles; los bloqueos nunca llegan a contenido público; los datos de la demo son ficticios. |
| ¿Por qué Gemini y LangGraph? | Gemini analiza y redacta; LangGraph orquesta las ramas condicionales del flujo con presupuesto por lote. |
