# Pendientes para verificar con Claude Code

Este registro reúne necesidades detectadas durante los cambios del frontend local. No confirma ausencias del backend sin revisar su implementación. Claude Code debe verificar el repositorio y crear o ajustar únicamente las conexiones que falten. En esta sesión no se modifica el backend.

## 1. Distinguir lotes de Discord y de carga manual

> **Resuelto en el backend (feat/lotes-fuente-analitica):** `trabajos_worker.fuente` guarda la vía de entrada (`discord`: puente o histórico; `manual`: archivo u operador). Los trabajos anteriores la deducen del origen (`discord`, `discord-historico` → discord; el resto → manual). `GET /api/dashboard/ambitos` devuelve `fuente_ingesta` y separa lotes de igual origen y período por vía. KPI, sentimiento, mensajes y alertas aceptan `fuente_ingesta`.

Estado: pendiente de verificar en el backend. El contrato que tenía el frontend solo declaraba origen (comunidad) y periodo.

Comportamiento esperado: el selector Todos los lotes agrupa los lotes por Discord o Carga manual · Ingesta de datos. Mantiene separados los lotes de igual comunidad y período que ingresaron por vías diferentes.

Preparación local: Ambito admite fuente_ingesta opcional con valores discord o manual. El selector usa la combinación origen, periodo y fuente_ingesta. Las consultas de KPI, mensajes y resumen de sentimientos envían fuente_ingesta si el lote la incluye.

Verificar: GET /api/dashboard/ambitos, persistencia de la procedencia en ambas vías de ingesta y aplicación real del filtro en los endpoints correspondientes. Asegurar compatibilidad con registros históricos sin procedencia; el frontend los agrupa como Origen sin identificar. Revisar CONTRATO-LOTES.md y src/services/api.ts para las rutas exactas. Los datos de referencia locales no contienen lotes individuales; no son evidencia de ausencia en producción.

## 2. Campanita: pendientes de Curaduría (especificación vigente)

Sustituye el contador de mensajes sin responder y su enlace a Interacciones. La campanita rosada abre /curaduria, cuya vista inicial es Pendientes. El número amarillo debe contar exactamente los logros elegibles pendientes de revisión del usuario/comunidad autorizados. Cero oculta el número; un error no se interpreta como cero. Actualización periódica y tras cambios de estado. Verificar el contrato y los permisos antes de implementar; no usar el total de mensajes ni registros ajenos al conjunto elegible.

## 3. Estado y control del bot Discord

Ver la especificación vigente Una sola caja Discord con cuatro conexiones al final de este documento. Sustituye el control de vista previa inicial.

## Reglas para preparar el prompt final

- Revisar el código del backend antes de afirmar que falta una conexión.
- Reutilizar los contratos existentes y coordinar cualquier nombre distinto de campo con el frontend.
- Mantener autenticación, validación y permisos; no crear accesos sin sesión.
- No tratar las muestras locales como datos productivos.
- Actualizar este registro al detectar nuevas dependencias durante la sesión.

## Ampliación a Analítica

El selector de Analítica también agrupa por fuente_ingesta y utiliza la misma combinación origen, periodo y fuente_ingesta que el Resumen. Verificar que el filtro se aplique tanto a los KPI como al resumen de sentimientos. No se modifica el backend en esta sesión.

## Selección múltiple en Analítica

> **Resuelto en el backend (feat/lotes-fuente-analitica):** `lotes` (JSON `[{origen, periodo, fuente_ingesta}]`) en `/dashboard/kpis`, `/dashboard/alertas`, `/mensajes` y `/mensajes/sentimiento/resumen`: unión sin duplicados con porcentajes recalculados. `lotes=[]` = ningún lote: todo en cero (no el global). Un `lotes` inválido responde 422.

El selector permite marcar uno o varios lotes y aplica la selección solo al pulsar Actualizar. Un lote conserva los parámetros individuales existentes. Para varios lotes, el frontend prepara el parámetro lotes como JSON de objetos origen, periodo y fuente_ingesta en los endpoints de KPI y resumen de sentimientos. Claude Code debe verificar/implementar este contrato o coordinar el contrato equivalente existente. El backend debe agregar sobre la unión de mensajes sin duplicados y recalcular porcentajes desde los conteos; no sumar porcentajes ni ignorar filtros desconocidos devolviendo el global. Si falla la consulta, el frontend conserva los últimos datos aplicados y muestra un error. No hay lotes individuales en la muestra actual para demostrar agregación real.

## Temas recurrentes de la comunidad

> **Resuelto en el backend (feat/tipo-temas-mensaje):** `GET /api/dashboard/kpis` incluye `temas_principales` (`[{tema, cantidad}]`, top 10, temas en minúsculas) sobre el mismo conjunto de mensajes que el resto de indicadores; `mensajes_por_tipo` ya refleja los tipos analizados. «Palabras frecuentes» no se implementa (pendiente de decisión).

La sección inferior de Analítica sustituye la repetición de sentimientos por los tipos de participación disponibles en mensajes_por_tipo, ordenados por volumen y excluyendo Sin clasificar. Incluye espacios para preguntas repetidas y palabras frecuentes. El frontend contempla recurrencia opcional en DashboardKPIs con preguntas y palabras, cada una como lista de objetos texto y cantidad. Verificar si existe un análisis equivalente antes de implementar este contrato. El análisis debe respetar los lotes aplicados, agrupar preguntas similares semánticamente y contar mensajes/ocurrencias con una definición explícita. Para palabras, normalizar mayúsculas y acentos según criterio acordado, excluir palabras vacías, URLs y datos personales; no presentar frecuencias de una muestra como si fueran del conjunto completo. No hay resultados inventados; cuando faltan datos se muestran estados vacíos.

Actualización visual: se retiraron las subsecciones y mensajes vacíos de preguntas repetidas y palabras frecuentes por solicitud del usuario. La sección conserva un único título y descripción general. Su detección sigue pendiente de verificación; actualmente las barras muestran solo los tipos de participación disponibles.

## Ampliación de la clasificación de temas recurrentes

Solicitud adicional del usuario, posterior a Ajustes_Liz.docx: la clasificación debe ser abierta y extensible, sin limitarse a preguntas, consultas o palabras. Puede incluir comentarios, situaciones, problemas, logros y otros tipos de participación detectados. Revisar qué soporta el backend antes de crear nuevas conexiones. Identificar recurrencias por tema o significado, con etiquetas legibles, conteos y trazabilidad a los mensajes/lotes, evitando categorías rígidas que descarten tipos nuevos. Respetar los lotes seleccionados y aplicados con Actualizar. El contrato final debe permitir nuevas categorías sin cambios obligatorios en la interfaz. La descripción visual enumera ejemplos y deja explícitamente abierta la clasificación. Actualmente el frontend muestra mensajes_por_tipo; esto no demuestra que exista detección semántica de recurrencias en el backend.

Criterio editorial permanente: revisar ortografía, concordancia, signos de puntuación y comas en cada cambio de interfaz. Mantener títulos y etiquetas sin punto final, y descripciones y mensajes completos con su puntuación correspondiente.

## Fuentes del análisis de temas recurrentes

Requisito explícito del usuario: Temas recurrentes de la comunidad debe conectarse a los datos persistidos de ambas vías de ingesta: mensajes procedentes de Discord y datos cargados manualmente mediante Ingesta de datos (archivos o conjuntos de datos importados). No limitar la detección a Discord ni a la muestra local. Analizar exclusivamente la unión de los lotes aplicados al pulsar Actualizar, conservando la procedencia y evitando duplicados cuando se combinen fuentes. Todos los lotes debe incluir ambas vías conforme a los permisos de la cuenta. Claude Code debe verificar las tablas, relaciones y contratos existentes en el repositorio y crear la conexión solo si falta; no conectar el frontend directamente a la base de datos ni aceptar credenciales arbitrarias de bases de datos desde la interfaz. La carga manual actual es de archivos, no una conexión directa a una base de datos externa.

## Aviso de bloqueos en Analítica

Requisito: el triángulo amarillo y el mensaje Revisa las alertas internas antes de continuar con la publicación deben ocultarse cuando el conteo de bloqueos sea cero y mostrarse solo con un conteo mayor que cero. El frontend ya aplica esa condición al dato disponible alertas_internas. Claude Code debe verificar si alertas_internas representa bloqueos vigentes o alertas históricas; si no equivale a bloqueos pendientes, proporcionar o reutilizar el campo correcto y ajustar el contrato del frontend. La cifra y el aviso deben usar el mismo conteo y respetar los lotes aplicados. No mantener el aviso por alertas ya resueltas ni interpretar un fallo de consulta como un cero confirmado.

## Selector múltiple independiente en Resumen

Resumen utiliza el mismo componente de checklist que Analítica y aplica uno o varios lotes al pulsar Actualizar. Cada panel conserva su selección independiente; no hay botón Limpiar vista ni sincronización automática entre paneles. Verificar también el parámetro lotes en GET /api/mensajes, además de los KPI y el resumen de sentimientos. El selector no debe usar una suma de porcentajes ni devolver el global cuando se ha solicitado una selección concreta.

## Resumen con tarjetas de filtro — reemplaza el selector de lotes del Resumen

Se retiran de Resumen el checklist de lotes y los botones Actualizar, Ingresar datos y Referencia cargada. Las cuatro tarjetas filtran la lista inferior: mensajes, borradores pendientes (generados y revisados), aprobados y alertas internas. Se reutilizan GET /api/mensajes y /api/curaduria/activos por estado, con paginación. Verificar un endpoint autorizado de detalle de alertas internas: actualmente solo se conoce el contador, por lo que la pestaña de alertas indica que el detalle no está disponible. No inventar mensajes de alerta a partir de sentimientos negativos ni usar el contador como listado. Verificar actualización de métricas/listas al finalizar ingestas y consistencia de los conteos. Esta petición sustituye la sección anterior Selector múltiple independiente en Resumen; el checklist de Analítica se mantiene.

## PRIORIDAD — Lógica funcional de las tarjetas del Resumen

> **Resuelto en el backend (feat/resumen-tarjetas-alertas):** `GET /api/dashboard/alertas?skip&limit[&origen&periodo]` lista las alertas internas (una por mensaje, mismo total que el KPI `alertas_internas`) con texto, autor, motivo, lote, trabajo y `veces`. `GET /api/mensajes` devuelve en cada mensaje `alerta_interna` (bool) y `estado_borrador` (aprobado | pendiente | rechazado | null). `GET /api/curaduria/activos?estados=generado,revisado` da los pendientes en un solo listado paginado (mismo total que `borradores_pendientes`). Las alertas son históricas: todavía no existe el estado «atendida».

El usuario confirma que el comportamiento actual todavía no funciona correctamente y pide documentarlo para verificación e implementación por Claude Code. La interfaz es una preparación local; no se debe considerar validada la integración completa.

Comportamiento esperado:

1. Los datos que ingresan desde Discord o mediante carga manual deben persistirse y alimentar tanto el Resumen como Analítica, según los permisos de la cuenta. Los resultados procesados deben estar disponibles tras completar la ingesta y el análisis.
2. Total de mensajes: al pulsar la tarjeta, mostrar todos los mensajes del conjunto correspondiente, con paginación real; no solo nueve mensajes recientes ni una muestra fija. El contador debe representar el total de ese mismo conjunto.
3. Borradores pendientes: al pulsar la tarjeta, mostrar únicamente los borradores que siguen pendientes de aprobación. Verificar que esto incluye generado y revisado, y excluye aprobado y rechazado. El listado y el contador deben usar exactamente la misma definición. Preferir un listado único ordenado y paginado en el servidor, no mezclar páginas independientes de estados como solución definitiva.
4. Aprobados: al pulsar la tarjeta, mostrar únicamente los contenidos aprobados, completos y paginados. El contador debe coincidir con el total del listado. Aprobado no significa publicado.
5. Alertas internas: al pulsar la tarjeta, mostrar el detalle de todas las alertas del mismo conjunto, con estado y referencias a mensajes, lotes o trabajos cuando existan. Verificar si el contador representa alertas vigentes o históricas y alinear listado y métrica. No deducir alertas de sentimientos negativos ni fabricar registros a partir del contador.
6. Cambiar de tarjeta reemplaza la lista inferior sin navegar a otro módulo. Se marca una sola tarjeta activa y se reinicia su paginación. Si no hay resultados, mostrar un estado vacío; distinguirlo de errores o falta de conexión.
7. Verificar invalidación/refresco de métricas y listas tras ingestas, análisis, revisión, aprobación o resolución de alertas para evitar cifras obsoletas. Revisar el backend antes de decidir si hace falta consulta periódica, eventos o invalidación existente.
8. Definir explícitamente el alcance de los datos. El Resumen ya no tiene selector de lotes. Verificar con el contrato existente si trabaja con todo el conjunto de la comunidad o el alcance aplicado del análisis; mantener ese alcance consistente entre las cuatro cifras y sus listas. No añadir silenciosamente sincronización de selectores: el usuario deshizo previamente esa solución visual.

Verificación requerida: comparar conteos y listados con datos persistidos reales de ambas vías de ingesta, comprobar paginación, estados y permisos. La captura local muestra 472 mensajes, 29 pendientes, 2 aprobados y 5 alertas, pero contiene solo 9 mensajes y 4 borradores de referencia; esa diferencia es propia de una muestra parcial y no permite validar la integración. El detalle de alertas no está conectado. No cambiar esos datos para simular que el backend funciona.

Esta solicitud solo actualiza la documentación. No implementar el backend durante esta sesión de cambios locales del frontend.

## Simplificación de Ingesta

Se retira de la interfaz el panel Historial de Discord por ser redundante con Conectar a Discord. Se conserva Conectar a Discord como punto de entrada para importar un canal por rango de fechas y Procesar mensajes pendientes como flujo separado. Esta decisión no autoriza eliminar endpoints ni capacidades históricas del backend: verificar y reutilizar las conexiones que utiliza Conectar a Discord.

## Zona horaria de la importación de Discord

Estado: envío verificado en el frontend; interpretación y conexión del backend pendientes de revisión por Claude Code. ConectarDiscord envía zona (identificador IANA, por ejemplo America/Guatemala o Europe/Madrid) junto con canal_id, desde y hasta a previsualizarDiscordHistorico. Al confirmar, crearImportacionDiscord reutiliza desde, hasta y zona del alcance_congelado devuelto por el backend. Cambiar la zona invalida la previsualización anterior. No se ha confirmado en esta sesión cómo lo procesa el servidor.

Verificar en el repositorio:
- Que ambos endpoints reciban y validen zona como identificador IANA, sin ignorarla ni sustituirla silenciosamente por la zona del servidor.
- Que desde y hasta se interpreten como fechas locales en la zona seleccionada, incluyendo ambos días. Convertir a instantes UTC con un inicio inclusivo y un fin exclusivo correspondiente a la medianoche local del día siguiente a hasta.
- Que se respeten cambios de horario de verano e intervalos de 23 o 25 horas, especialmente Europe/Madrid; no usar un desfase UTC fijo para todas las fechas.
- Que la previsualización, el alcance congelado, la confirmación, los trabajos y las consultas a Discord usen el mismo rango, sin sumar dos veces el desfase ni volver a interpretar fechas UTC como locales.
- Que se conserve la zona seleccionada y los límites efectivos del lote para trazabilidad, reintentos e idempotencia.
- Que los rangos inválidos y las zonas desconocidas devuelvan errores legibles; comprobar los límites en cambios de día, mes, año y horario de verano.

Si falta esa conexión o validación, Claude Code debe implementarla tras revisar las capacidades existentes. No modificar el backend en esta sesión. Las etiquetas UTC de la interfaz son orientativas; los cálculos deben basarse en IANA y en las fechas seleccionadas.


## ESPECIFICACIÓN VIGENTE — Una sola caja Discord con cuatro conexiones

> **Resuelto en el backend (feat/discord-escucha-canal):** `GET/PATCH /api/v1/discord/canales/{canal_id}/escucha` con el contrato propuesto `{canal_id, conectado, escuchando}` (más `deteniendo` e `importacion`). Escuchando = el canal tiene una importación histórica en curso; termina sola al completarse aunque se cierre el navegador. `PATCH {escuchando:false}` cancela la importación activa (pendiente: al instante; en ejecución: entre páginas, `deteniendo=true`); `true` solo confirma una activa (409 `sin_importacion` si no la hay). No toca el bot ni el lector en vivo. `conectado` = canal en la lista autorizada del servidor.

Esta sección sustituye la propuesta descartada de cinco paneles independientes. La interfaz debe tener una sola caja titulada Conectar a Discord, con un único interruptor superior derecho y hasta CUATRO conexiones dentro. Se inicia con una conexión y aparece la siguiente cuando el servidor acepta la importación de la anterior, hasta cuatro en total. No mostrar cinco cajas ni un botón para añadir paneles manualmente.

Cada conexión tiene un ID de canal, un período (días, meses o años) y una zona IANA. El usuario completa los campos. Cuando son válidos, el frontend espera brevemente y solicita la previsualización y la importación de forma automática. No inferir fechas ni zona a partir del ID. Para rangos que el backend exige confirmar, se mantiene la confirmación explícita antes de importar. Los errores no provocan reintentos infinitos; puede reintentarse expresamente. Verificar validación de IDs, duplicados entre conexiones, acceso a canales, límite de cuatro e idempotencia por solicitud.

El frontend consulta el progreso de la importación usando el endpoint existente consultarImportacionDiscord. Al llegar a un estado terminal (completada, completada_con_limite, cancelada o error), solicita escuchando=false para ese canal. El interruptor superior representa el conjunto de canales con estado confirmado: Escuchando si al menos uno sigue escuchando y Apagado cuando ninguno escucha. Una solicitud aceptada no equivale a datos ya importados; no apagar basándose solo en la creación del trabajo. Si no se conoce el estado, mostrar Sin confirmar; si falla el apagado, no afirmar que se apagó.

IMPORTANTE: el backend debe garantizar el apagado al finalizar la gestión/importación, incluso si el usuario cierra el navegador o se corta la conexión. La llamada del frontend es un refuerzo de interfaz, no la garantía principal. Revisar que el interruptor represente escucha por canal y no implique apagar el proceso global del bot para otros usuarios. Si hay trabajos simultáneos, mantener el estado correcto hasta que terminen todos los que correspondan. Finalizar una carga no debe borrar datos ni cancelar otras conexiones.

Contrato de escucha PROPUESTO, sujeto a verificación en el repositorio: GET /api/v1/discord/canales/{canal_id}/escucha y PATCH a la misma ruta con {escuchando: boolean}; respuesta {canal_id: string, conectado: boolean, escuchando: boolean}. Reutilizar endpoints equivalentes si ya existen y adaptar el contrato del frontend en lugar de duplicarlos. Validar autenticación, permisos por canal y estado real del consumidor/puente. La conexión de escucha no ha sido implementada ni verificada en el backend en esta sesión.

Acordar e implementar el ciclo del consumidor durante la gestión de importación: no confundir importar historial con mantener escucha permanente. El requisito confirmado es que, al terminar de traer los datos, la escucha quede apagada. Verificar la arquitectura para activar temporalmente solo lo que la importación necesita, manteniendo la separación entre importador histórico y consumidor de mensajes en vivo.

Persistencia: verificar recuperación de conexiones y estados al reabrir, permisos de cuenta/comunidad y límite autoritativo de cuatro. El borrador de formulario local no se persiste actualmente. Las fechas deben respetar la zona elegida y el alcance congelado de la previsualización. Probar ambas fuentes de ingesta y el efecto posterior en Resumen y Analítica.

Solo se modifica el frontend y este documento local. Claude Code de Anthropic deberá revisar el repositorio y completar las conexiones del backend que falten. No se modifica el backend ni GitHub durante esta sesión.

## Nombre y período de la carga manual — requisito vigente

Nombre sustituye a Comunidad en Fuente de datos. Nombre y Período empiezan vacíos; no precargar CommunityLab ni la semana actual. Al elegir un archivo JSON, JSONL o CSV válido, completar desde metadatos disponibles. El frontend toma nombre/nombre_dataset/origen_comunidad/comunidad/origen de metadatos o un valor uniforme en los registros; en ausencia de nombre interno usa el nombre del archivo sin extensión. Período toma periodo/período explícito o uniforme; si no existe y todos los registros tienen fechas ISO con zona, propone el intervalo de días UTC de esas fechas. Si existen períodos contradictorios o fechas insuficientes, dejar el período vacío para revisión; no inventar la semana actual. Los campos siguen editables.

Claude Code debe verificar y formalizar la detección en el servidor para ambos formatos de JSON, JSONL y CSV con encabezados, normalización de BOM/UTF-8 y campos entrecomillados. La inferencia local es una ayuda, no validación autoritativa. Validar conflictos entre metadatos, registros y valores corregidos en el formulario; no recortar silenciosamente ni asignar un período incorrecto. Definir la zona para períodos derivados de fechas y comunicarla. Si la semana o período seleccionado viene en los metadatos, conservarlo; si el conjunto contiene varios períodos, decidir si se rechaza, requiere selección o se divide en lotes.

Compatibilidad: el frontend sigue enviando el nombre mediante origen_comunidad en subirLote por el contrato actual. El cambio visual a Nombre no implica renombrar la columna/campo del backend sin revisar sus usos. La clasificación y los selectores deben mostrar ese nombre y el período real importado. Verificar endpoint de prevalidación/detección si ya existe y reutilizarlo si corresponde. No se ha modificado el backend.

## Desmarcar Cerrar período y generar resumen — cancelación de carga

Solicitud del usuario: al desmarcar Cerrar período y generar resumen, cancelar automáticamente la carga de datos asociada. Actualmente el frontend solo envía cierre=false; NO existe en esta sesión una cancelación real implementada ni se verificó una API de cancelación de la carga manual.

Claude Code debe revisar el significado existente de cierre y el ciclo de trabajos antes de cambiar este comportamiento, ya que importar sin cerrar período y cancelar una importación son operaciones diferentes. Determinar si la carga está solo seleccionada, pendiente, procesándose o ya completada. Para una carga pendiente o en curso, verificar cancelación autorizada e idempotente, detener procesamiento y generación de resumen, y devolver un estado confirmado a la interfaz. Si solo existe selección local, retirar esa selección y sus metadatos conforme al flujo acordado. No presentar un simple cierre=false como una cancelación exitosa.

La solicitud no debe traducirse en borrar automáticamente una base de datos ni datos ya persistidos o compartidos. Para cargas completadas, definir expresamente con el equipo si corresponde cancelar solo el cierre/resumen o una reversión transaccional del lote; no ejecutar borrados implícitos. Conservar trazabilidad y aislamiento por cuenta/lote. Verificar conflictos con el requisito de conservar datos importados sin cierre semanal y acordar la semántica antes de implementar el backend. Esta sección es una especificación para revisar con Claude Code, no evidencia de soporte existente.

## Indicador verde de ingesta completada

Requisito: en Fuente de datos, Esperando archivo debe convertirse en un check circular verde y el texto Ingesta completada cuando el backend confirme que el trabajo de ingesta terminó correctamente. El frontend ya condiciona ese estado a trabajo.estado === terminado, obtenido por consultarTrabajo. Un archivo seleccionado se muestra como Listo para iniciar; una subida aceptada o procesamiento en curso muestra Procesando datos. Un error no muestra el check verde.

Claude Code debe verificar que terminado se emita únicamente después de persistir la data y completar las operaciones requeridas por el contrato; distinguir recepción HTTP, validación, guardado y procesamiento. Si falla, hay cancelación o no se confirma el resultado, no emitir éxito. Conservar trazabilidad del lote y reflejar reintentos y trabajos reutilizados mediante una consulta de estado real. El indicador debe poder recuperarse al consultar el trabajo y las métricas/listados correspondientes deben reflejar la ingesta confirmada. No fabricar éxito en el frontend ni mostrarlo solo por haber elegido o enviado un archivo. No se modifica el backend en esta sesión.

## Interacciones: tarjetas de filtro y búsqueda por palabra clave

> **Resuelto en el backend (fix/busqueda-fidelidad-fechas-pruebas):** `GET /api/mensajes?q=` busca en texto, autor y canal sin distinguir mayúsculas ni tildes (`%` y `_` son literales), combinado con `sentimiento` y los lotes, antes de contar y paginar.

Se elimina el botón Filtros. Total de mensajes, Positivos, Negativos y Sin analizar filtran el listado usando sentimiento (sin filtro, positivo, negativo o sin_analizar), con paginación reiniciada. La lupa izquierda despliega hacia la derecha el buscador sin texto de ayuda visible. El frontend prepara q como parámetro opcional en GET /api/mensajes y combina la búsqueda con el filtro antes de paginar. Claude Code debe verificar soporte real para q o adaptar al contrato equivalente existente; buscar en el conjunto completo autorizado y devolver un total coherente, no filtrar solo diez mensajes de una página. La muestra local filtra antes de paginar. Verificar normalización, permisos y consulta parametrizada. No crear un endpoint si ya existe uno equivalente.

### Confirmación del usuario — funcionamiento completo de Interacciones

Dejar esta funcionalidad explícita en el prompt final para Claude Code. Al pulsar Total de mensajes, devolver todos los mensajes autorizados; Positivos y Negativos deben devolver únicamente mensajes con el sentimiento correspondiente, y Sin analizar los que no tienen análisis. Cambiar de tarjeta reinicia a la primera página y actualiza el título de la tabla. La búsqueda por palabra clave debe combinarse con la tarjeta activa en una misma consulta al backend, aplicada antes de calcular total y paginación. Actualmente se prepara el parámetro q; verificar si existe otro nombre o endpoint equivalente y adaptar sin duplicar contratos. La lupa que se expande hacia la derecha es comportamiento del frontend, no requiere un endpoint separado.

Verificar con datos reales de Discord y carga manual que las cifras de las tarjetas coincidan con sus listados sin búsqueda y que el total paginado corresponda al filtro y palabra clave activos. No filtrar solo la página cargada ni ignorar silenciosamente q. Distinguir ausencia de resultados, falta de análisis y errores de conexión. Mantener permisos, aislamiento de datos y consultas parametrizadas. La integración real aún requiere revisión del backend; no considerarla validada por funcionar con la muestra local.

### Estado inicial de la lupa de Interacciones

El buscador se inicia cerrado al entrar a la pantalla y al restaurarla desde el historial del navegador; solo se amplía al pulsar la lupa. Este estado visual no se persiste ni requiere cambios del backend. La API conserva únicamente la responsabilidad de filtrar por palabra clave cuando exista una consulta.

## Sentimientos detectados y actualización de Interacciones

Después de que la IA detecte y persista el sentimiento, GET /api/mensajes debe devolver sentimiento_ref actualizado y coherente con la clasificación real; no asignar un sentimiento a Ana Valenzuela u otro registro desde el frontend solo para colorearlo. Sin análisis confirmado, conservar Sin analizar y aspecto neutro. Las etiquetas de Interacciones usan positivo=verde, negativo=azul de la paleta (igual que su tarjeta), neutral=amarillo e indeterminado=rosado; el texto siempre identifica el estado para no depender solo del color.

El frontend vuelve a consultar la página activa y el resumen cada 15 segundos mientras la pestaña esté visible, conserva filtro/búsqueda/paginación y evita consultas de listado superpuestas. Claude Code debe verificar persistencia y exposición del resultado, actualización de conteos, ausencia de caché obsoleta y filtros por sentimiento aplicados después de la clasificación. Si ya hay eventos en tiempo real, considerar reutilizarlos; la actualización actual es periódica, no instantánea. La captura local es estática y sus registros sin analizar no se convierten artificialmente en analizados. Mantener datos de prueba identificados.

Se retira el contorno de selección de las cuatro tarjetas de Interacciones; siguen filtrando al pulsarlas y mantienen semántica accesible. No requiere cambios del backend.

## Columna Tipo en Interacciones

> **Resuelto en el backend (feat/tipo-temas-mensaje):** el worker guarda en `mensajes.tipo` el tipo que deduce el análisis (`bloqueo` > `duda` > `logro` > `comentario`) y en `tema_ref` el tema de la IA, para Discord y carga manual. Un tipo que trae el archivo se conserva; el tema solo se completa si estaba vacío. `backend.scripts.reclasificar_mensajes` completa lo ya procesado desde el enrutamiento guardado (sin IA).

Se reemplaza la columna visible Canal por Tipo. Mostrar una etiqueta corta por mensaje basada en su campo tipo, independiente de su sentimiento. Mapeo de presentación actual: PREGUNTA_TECNICA/PREGUNTA/DUDA → Duda; CONSULTA_NEGOCIO/CONSULTA → Consulta; LOGRO/EXITO/CASO_DE_EXITO → Éxito; BLOQUEO → Bloqueo; PROBLEMA → Problema; COMENTARIO → Comentario; SUGERENCIA → Sugerencia. Sin tipo confirmado, mostrar Pendiente; los valores no reconocidos muestran Otro y conservan el original como información de ayuda. No clasificar automáticamente en el navegador a partir de palabras sueltas ni deducirlo del canal.

Claude Code debe verificar que el análisis clasifique y persista tipo por mensaje tanto para Discord como para carga manual, y que GET /api/mensajes lo devuelva actualizado. Alinear este campo con mensajes_por_tipo y los temas recurrentes, manteniendo etiquetas breves y categorías extensibles. El canal original debe conservarse en almacenamiento aunque ya no se muestre como columna. La muestra local tiene tipo vacío y mostrará Pendiente hasta que exista clasificación real; no inventar etiquetas para la demostración.

## PRIORIDAD — Curaduría de logros académicos y publicaciones de felicitación

Nombre visible vigente: Curaduría, con ortografía española (sustituye Borradores en el menú y el módulo; las métricas Borradores pendientes conservan su significado).

Regla de admisión: solo mensajes que la IA confirme como positivos Y que comuniquen que una persona ya completó un curso, diplomado o certificación. No incluir positividad genérica, consultas, cursos en progreso, intención de cursar, logros colectivos sin atribución confirmada ni felicitaciones sin evidencia de finalización. Verificar y persistir clasificación, estado de finalización, tipo de logro y fuentes. Mantener controles de fidelidad y consentimiento.

El frontend prepara elegibilidad_curaduria en Activo con sentimiento, logro_completado y tipo_logro (curso, diplomado, certificacion), y solicita /api/curaduria/activos con tipo_revision=logro_academico, sentimiento=positivo y logro_completado=true. Es un contrato propuesto: revisar si existe otro equivalente y adaptar. El servidor debe filtrar antes de paginar y devolver total/total_pages coherentes. El frontend además excluye activos sin evidencia de elegibilidad. La muestra local no tiene esa confirmación y muestra un estado vacío, no ejemplos inventados.

En Cuerpo del contenido se añade Generar posts con IA y dos versiones editables: LinkedIn y X. Contrato propuesto POST /api/curaduria/activos/{id}/posts/generar con redes=[linkedin,x], respuesta con linkedin y x (strings). Reutilizar generadores/contratos existentes antes de crear otro endpoint. Generar desde las fuentes del logro validado; no inventar títulos, cursos, instituciones, notas, fechas o identidad. Adaptar estilo y longitud por red, sin publicar. Evitar duplicación de solicitudes y consumos por reintentos; definir idempotencia/rate limits autorizados. Confirmar elegibilidad también en el servidor.

Persistencia propuesta al guardar: posts_redes={linkedin,x}, manteniendo copy compatible con la versión LinkedIn. Verificar versionado, revisión, actualización y guardado real de ambas versiones. La aprobación debe referirse a la versión revisada; cambios posteriores deben invalidar aprobaciones/banners según el contrato existente. La generación no aprueba ni publica automáticamente. No generar con IA desde el navegador usando secretos del proveedor.

Banner: el flujo produce una felicitación por el logro académico. Revisar generador existente y reutilizarlo. Acordar si se crea como borrador automáticamente al validar el logro o después de aprobar el texto; conservar la revisión antes de publicación, no inventar una transición automática de aprobación. El componente actual requiere texto aprobado para generar banner y sigue disponible. Aprobar un banner no lo publica. Garantizar coherencia entre logro, versiones de posts y banner.

Integrar mensajes elegibles de Discord y de archivos de carga manual, actualizar conteos de Resumen y trazabilidad a las fuentes. Verificar permisos por cuenta, anonimización sin consentimiento y manejo de errores del proveedor. La integración de generación y el contrato de elegibilidad no están confirmados en el backend; este documento es para que Claude Code de Anthropic los verifique e implemente si faltan. Esta sesión solo cambia frontend y documentación local.

## Historial de Curaduría: pendientes, denegados y aprobados

> **Resuelto en el backend (fix/curaduria-posts-historial):** `GET /api/curaduria/activos/{id}` devuelve `historial` (`evento`, `estado`, `version`, `fecha`, `actor`, `comentario`) en orden estable. Se registran desde ahora la creación por el worker, las ediciones, las generaciones con IA y los cambios de estado; los activos anteriores no tienen eventos reconstruidos. Aprobar desde `generado` está permitido (revisar y aprobar en una acción). Pendiente: `estados=` múltiple en el listado.

Solo existen tres filtros visibles: Pendientes, Denegados y Aprobados. Se retiran Todos, Generados y Revisados como opciones independientes, así como la acción Marcar como revisado. Para compatibilidad, generado y revisado se agrupan en Pendientes; un registro revisado NO se convierte automáticamente en aprobado. Denegados corresponde a rechazado y Aprobados a aprobado. Claude Code debe revisar el modelo y acordar una migración explícita si corresponde, conservando la auditoría. El frontend propone estados=generado,revisado para pendientes en GET /api/curaduria/activos; verificar o adaptar el contrato existente. Filtrar elegibilidad y estados ANTES de paginar, devolver total real del mismo conjunto que usa la campanita. Mantener la regla de logros académicos positivos confirmados y conservar los denegados y aprobados.

El listado muestra estado actual y fecha de actualización. El editor contempla historial opcional por activo con eventos {estado, fecha, comentario?}. Claude Code debe verificar la auditoría existente y reutilizar su esquema/endpoint; devolver el historial real en el detalle o adaptar el frontend al recurso existente. Registrar generación, revisión, denegación y aprobación con versión, fecha y actor autorizado; incluir regeneraciones y ediciones con trazabilidad cuando corresponda. No reconstruir falsamente transiciones pasadas a partir del estado actual ni guardar la auditoría solo en el navegador. Definir orden estable para los eventos y permisos de lectura.

Actualizar listas y conteos después de una transición, con filtros coherentes: un contenido que deja de cumplir el filtro activo debe salir del listado filtrado sin perder su historial. El frontend vuelve a consultar el listado tras cambiar estado. La generación de posts, las versiones LinkedIn/X y el banner deben vincularse al mismo contenido y conservar su revisión. Si la auditoría no está disponible, mostrar el estado actual como tal, sin inventar eventos.

## Curaduría — Generar post y enlaces a LinkedIn/X: especificación vigente

> **Resuelto en el backend (fix/curaduria-posts-historial):** `POST /api/curaduria/activos/{id}/posts/generar` devuelve `{linkedin, x, generaciones_restantes}` con una sola llamada a Gemini y las mismas reglas editoriales del generador de logros; no guarda ni aprueba. Tope `CURADURIA_MAX_GENERACIONES` (3) por borrador; un fallo de la IA no consume el intento. `PATCH` acepta `posts_redes` (`x` hasta 280 caracteres) y lo devuelve; `copy` queda igual a la versión LinkedIn y cualquier cambio en LinkedIn o X crea una versión nueva e invalida la aprobación. Pendiente: elegibilidad de logro académico.

El nombre exacto del botón es Generar post, sin con IA y en singular. La generación sí requiere la conexión del backend especificada en la sección de generación de textos.

LinkedIn y X quedan DESHABILITADOS por ahora. Cuando se habiliten, su único propósito será abrir https://www.linkedin.com/ y https://x.com/, respectivamente. No necesitan endpoint de preparación de publicación, OAuth, cuentas asociadas, tokens ni publicación automática desde CommunityLab para este alcance. Se retiró del frontend la propuesta prepararPublicacionLogro y su endpoint. Esta decisión sustituye la propuesta anterior de publicación mediante cuentas asociadas.

Si existe una sesión en esa red en el dispositivo/navegador, la propia red la utilizará; si no existe, la red decidirá si pide iniciar sesión. CommunityLab no puede comprobar directamente sesiones externas ni debe prometer que abrir una página equivale a publicar. El usuario redactará/confirmará la publicación en la red. No adjuntar, copiar ni publicar automáticamente texto o banner por el simple enlace.

EXCEPCIÓN EXPLÍCITA PARA EL TRABAJO FUTURO EN BACKEND: verificar y actualizar el SVG/plantilla de los banners de felicitación, que el usuario indica desactualizado y con otra colorimetría. Adaptar a la paleta vigente: rosado #ff90e8, amarillo #f1f333, azul #90a8ed, verde #b9e9c5, negro y grises de interfaz; tipografía ABC Favorit cuando corresponda y sea compatible con el renderizador. Mantener geometría, legibilidad, dimensiones y fuentes de datos del banner. No reutilizar los dos logos descartados por el usuario. El nuevo símbolo entregado el 20 de octubre está adaptado en public/brand/communitylab-logo-current.svg; usar esta versión de referencia visual y no los logos descartados. Revisar la ubicación real de la plantilla y probar el SVG y su conversión a imagen con textos largos y acentos. Esta excepción documenta autorización para la tarea futura de Claude Code; no se modifica el backend durante esta sesión.

## Idioma predeterminado y revisión editorial

Español es el idioma base en todo el dashboard, inicio de sesión y registro. Se eliminan los selectores español/inglés y se ignora la antigua preferencia de idioma almacenada. El frontend declara html lang="es" y translate="yes". El navegador (por ejemplo, Chrome/Google Translate) decide si ofrece traducción a inglés según las preferencias del usuario; la aplicación no puede forzar ese aviso ni necesita un endpoint de idioma. Conservar sin traducir los mensajes originales, nombres propios y datos de usuarios. Verificar que el backend no fuerce inglés ni inyecte etiquetas notranslate globales; no modificar datos persistidos para traducir la interfaz.

## Banner SVG de Curaduría: revisión profesional para Claude Code

Revisar el generador y la plantilla SVG existentes, mantener el flujo SVG actual y renovar su diseño conforme al producto vigente. Usar la paleta documentada, tipografía ABC Favorit con alternativa compatible y jerarquía clara; cuidar márgenes, contraste, alineación y legibilidad. Probar felicitaciones, nombres largos, acentos, distintas dimensiones y conversión a imagen. Evitar recortes y texto desbordado. No incorporar los logos rechazados; el nuevo símbolo adaptado está en public/brand/communitylab-logo-current.svg. Verificar licencias y disponibilidad de fuentes en el renderizador. Este trabajo está pendiente para Claude Code en backend; aquí solo se documenta, sin modificar el backend ni el repositorio remoto.
