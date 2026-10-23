# Validación del bot de Discord

Preparado el 09/10/2026 para revisión como borrador dependiente del PR #20.

| Suite | Resultado local |
|---|---|
| Bot y compatibilidad con el repositorio | 36 aprobadas |
| Grafo del repositorio | 28 aprobadas |
| Worker y contrato de IA | 10 aprobadas, 20 omitidas por requerir PostgreSQL |
| Lector del PR #20 | 19 aprobadas |

Total: 93 aprobadas, 20 omitidas. Configuración de ejemplo válida y `pip check`
sin incompatibilidades. Las pruebas se repiten desde la estructura del PR.

Desde `integrations/discord/bot`, instalar `requirements-validacion.lock.txt` y ejecutar:

```text
python -B tools/validate_local.py
```

El script guarda resultados locales en `evidencias/`, registra el commit probado,
comprueba que los archivos versionados no cambien, no hereda claves del entorno y
bloquea sockets de red en los subprocesos Python (excepto el socketpair interno de
asyncio en Windows). CI repite la validación en Ubuntu y Windows.

Cubre filtros, permisos del canal interno (incluidos usuarios fuera de caché),
respuestas al mensaje original, bloqueo sin publicación pública, testimonios sin
publicación automática, deduplicación, reinicio, fallos y envíos inciertos. La
compatibilidad usa los esquemas y nodos reales del repositorio con IA sustituida.

No se han probado Discord real, IA real, PostgreSQL, Compose ni VM. La conversión
a Interaccion dentro de tests es un fixture, no el normalizador de Santiago. La
función final de Fabián aún debe incorporarse y su contrato debe confirmarse.

La entrega de Paulo está preparada para revisión; la tarea conjunta sigue en
progreso. Las cifras no acreditan pruebas completas de integración real.
