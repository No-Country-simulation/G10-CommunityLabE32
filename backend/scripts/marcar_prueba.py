"""Marca (o desmarca) lotes como «de prueba»: se ocultan por defecto en el panel; no se borra nada.

Uso (en el contenedor de la API):
  python -m backend.scripts.marcar_prueba --listar
  python -m backend.scripts.marcar_prueba --origen CommunityLab-prueba --periodo 2026-W42-prueba-PR32 [--fuente manual]
  python -m backend.scripts.marcar_prueba --origen ... --periodo ... --quitar
Imprime solo lotes y conteos.
"""
import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

from backend.app.services.ambito import fuente_de


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listar", action="store_true")
    p.add_argument("--origen")
    p.add_argument("--periodo")
    p.add_argument("--fuente", choices=("discord", "manual"))
    p.add_argument("--quitar", action="store_true", help="desmarcar (vuelve a mostrarse)")
    args = p.parse_args()
    if not args.listar and not (args.origen and args.periodo):
        p.error("indica --listar, o --origen y --periodo")
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    with psycopg.connect(url, row_factory=dict_row) as c:
        filas = c.execute("SELECT id, entrada, fuente, es_prueba FROM trabajos_worker").fetchall()
        lotes = {}
        for f in filas:
            entrada = f["entrada"] if isinstance(f["entrada"], dict) else json.loads(f["entrada"])
            clave = (entrada.get("origen_comunidad"), entrada.get("periodo_referencia"), fuente_de(f["fuente"], entrada))
            lote = lotes.setdefault(clave, {"ids": [], "prueba": 0})
            lote["ids"].append(f["id"])
            lote["prueba"] += bool(f["es_prueba"])
        if args.listar:
            for (origen, periodo, fuente), lote in sorted(lotes.items(), key=lambda x: tuple(map(str, x[0]))):
                print(f"{origen} | {periodo} | {fuente} | trabajos={len(lote['ids'])} de_prueba={lote['prueba']}")
            return
        ids = [i for (o, per, fu), lote in lotes.items() for i in lote["ids"]
               if o == args.origen and per == args.periodo and (args.fuente is None or fu == args.fuente)]
        if not ids:
            raise SystemExit("No hay trabajos con ese origen/período (usa --listar).")
        n = c.execute("UPDATE trabajos_worker SET es_prueba=%s WHERE id = ANY(%s)", (not args.quitar, ids)).rowcount
        print(f"{'desmarcados' if args.quitar else 'marcados como prueba'}: {n} trabajos de {args.origen} | {args.periodo}")


if __name__ == "__main__":
    main()
