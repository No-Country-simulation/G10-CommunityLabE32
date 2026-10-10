# Validación del lector

Preparado para revisión el 09/10/2026 sobre main `61ddc4bd4a6dfa0590b44e9d833e2fd42769f563`.
La suite contiene 19 pruebas: 10 del núcleo y 9 del cliente discord.py con
transporte sustituido. Cubre filtros, permisos, reconexión, persistencia,
deduplicación, capacidad y exportación. No usa tokens ni Discord real.

Desde `integrations/discord/reader`, con las dependencias instaladas:

```text
python -B -m unittest discover -s tests -v
python -B -m discord_reader --config config.example.json check-config
python -m pip check
```

Pendiente: acordar contrato con Santiago, integrar su normalizador y validar con
bot/canales reales. Estas pruebas no acreditan el cierre de la tarea compartida.
