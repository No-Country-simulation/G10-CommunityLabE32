"""Recalcula las advertencias de fidelidad guardadas de todos los activos (sin IA).

Uso (en el contenedor de la API):  python -m backend.scripts.recalcular_fidelidad [--aplicar]
Sin --aplicar solo informa cuántos cambiarían. Imprime conteos, nunca textos.
"""
import argparse
import os
from collections import Counter

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.app.services.fidelidad import advertencias_de


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="guardar los cambios (por defecto, solo informar)")
    args = p.parse_args()
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    cambios, antes, despues = 0, Counter(), Counter()
    with psycopg.connect(url, row_factory=dict_row) as c:
        activos = c.execute("SELECT id_activo, formato, copy, fuentes, advertencias_fidelidad FROM activos").fetchall()
        for a in activos:
            ids = a["fuentes"] or []
            mensajes = c.execute("""SELECT id_mensaje AS id, autor, canal, fecha, texto FROM mensajes
                WHERE id_mensaje = ANY(%s)""", (ids,)).fetchall() if ids else []
            ambito = c.execute("""SELECT entrada->>'origen_comunidad' origen, entrada->>'periodo_referencia' periodo
                FROM trabajos_worker WHERE entrada->'interacciones' @> jsonb_build_array(jsonb_build_object('id', %s::text))
                ORDER BY creado DESC LIMIT 1""", (ids[0],)).fetchone() if ids else None
            nuevas = advertencias_de(a["copy"], a["formato"], mensajes, *(ambito or {}).values()) if mensajes else (a["advertencias_fidelidad"] or [])
            antes.update(w["tipo"] for w in a["advertencias_fidelidad"] or [])
            despues.update(w["tipo"] for w in nuevas)
            if nuevas != (a["advertencias_fidelidad"] or []):
                cambios += 1
                if args.aplicar:
                    c.execute("UPDATE activos SET advertencias_fidelidad=%s WHERE id_activo=%s", (Jsonb(nuevas), a["id_activo"]))
    print(f"activos={len(activos)} con_cambios={cambios} aplicado={args.aplicar}")
    print(f"antes={dict(antes)}")
    print(f"despues={dict(despues)}")


if __name__ == "__main__":
    main()
