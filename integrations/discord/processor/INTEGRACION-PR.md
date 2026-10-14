# Integración de los PR de Discord

Revisión local del 13 de octubre de 2026. No constituye aprobación ni evidencia de CI remota de estos cambios.

## Revisiones comprobadas

- main: 618ac1766c6da7a21c0846e863791ab26f2bb581.
- Lector #20: 77f28ed8fc46d42c92825e74ee6a35d34e8cce8f; abierto y en borrador.
- Transporte #21: 4c0a4ddaeeb7a6cdc36a9844ab518310359c2e57; abierto y en borrador, base feature/discord-reader-paulo.
- Clasificador #25: 2977bb70f29ded4c147b410fc81b76d2e056da09; abierto, base main, incluye el historial de #20 y #21.

## Commits locales preparados para complementar #25

1. e58290b: combinación con main, sin conflictos.
2. 27ee780: contrato estricto, logros silenciosos, revisión pendiente y fallos sin publicación.
3. fcc5f62: entrada asíncrona, clasificación preliminar de Fabián y decisión final de Gemini, pruebas y ejecutores de aceptación.
4. 66b4097: CI integrada Windows/Linux y PostgreSQL.

Estos commits son descendientes del PR25, sin reescritura de su historia. No requieren modificar el código de la rama del PR21 para funcionar.

## Orden recomendado de integración

1. Revisar y aprobar #20, salir de borrador cuando proceda y fusionar con Create a merge commit.
2. Cambiar la base de #21 a main. Repetir CI y revisión por otra persona; salir de borrador y fusionar con Create a merge commit.
3. Incorporar estos commits a la rama del PR25. Actualizar su título a `fix(discord): integrar clasificador y transporte con Gemini`. El título actual falla la regla Conventional Commits; los commits de código no corrigen el título por sí solos.
4. Actualizar #25 desde el main resultante, repetir CI y completar aceptación real antes de aprobar/fusionar.

El repositorio permite merge commits. Se simuló main -> #20 -> #21 -> #25 corregido conservando los commits: sin conflictos y árbol final idéntico al probado. Esta simulación no valida futuros cambios de otros compañeros.

## Si se usa Squash and merge

También se simuló squash en #20 y #21. Al incorporar #25 corregido aparecen conflictos add/add en:

- integrations/discord/bot/bot_discord/contracts.py
- integrations/discord/bot/bot_discord/engine.py

La razón es que squash conserva el contenido, pero cambia la ascendencia: Git vuelve a considerar añadidos los archivos que #25 modifica. No fusionar #25 a ciegas. Cuando exista ese main real, combinarlo en la rama de Fabián y resolver ambos archivos conservando las correcciones del contrato y ReviewRequired, junto con cualquier cambio posterior del equipo. Ejecutar de nuevo las pruebas antes de publicar la resolución. No se incorporaron commits ficticios de la simulación a la rama entregada.

## Evidencia y límites

El código de esta entrega pasó 214 pruebas y 42 subpruebas por plataforma, Windows y Linux, con PostgreSQL desechable y cero omisiones. Los servicios Gemini/Discord se simularon en esa batería. Los hashes de los 22 archivos de implementación coinciden con los que se probaron. La CI nueva sigue pendiente de ejecución en GitHub.

La comparación real parcial completó 8 casos con Fabián integrado, todos con señales esperadas; la variante directa completó 7 y falló por HTTP en el octavo. No constituye una aceptación de los 20 casos ni de bloqueos/casos adversos. Falta completar la evaluación y verificar esta versión en Discord real: dudas, bloqueo privado, logros silenciosos, canal excluido, permisos y reinicio sin duplicación. No declarar la actividad al 100% antes de esa aceptación y revisión.
