"""Completa tipo y tema de mensajes ya procesados, con lo que guardaron sus trabajos (sin IA).

Fuentes, en orden: `clasificaciones` (trabajos nuevos) o, en trabajos anteriores, el enrutamiento:
ruta bloqueo → bloqueo; dudas → duda (con el tema de su motivo); logro → logro; y en `sin_ruta`,
«Duda sin recurrencia…» → duda y «Bloqueo ya alertado…» → bloqueo. Precedencia: bloqueo > duda > logro.
Solo trabajos terminados y no simulados. El tipo solo reemplaza a `sin_clasificar`; el tema solo se
completa si estaba vacío (mismas reglas que el worker). Lo que el enrutamiento no distingue queda igual.

Uso (contenedor de la API): python -m backend.scripts.reclasificar_mensajes [--aplicar]
Sin --aplicar solo informa. Imprime conteos, nunca textos.
"""
import argparse
import json
import os
import re
from collections import Counter

import psycopg
from psycopg.rows import dict_row

from pipelines.communitylab.grafo import MAX_TEMA
from worker.store_postgres import TIPO_POR_DEFECTO, TIPOS_ANALISIS

PRIORIDAD = {"bloqueo": 3, "duda": 2, "logro": 1, "comentario": 0}
TEMA_DUDA = re.compile(r"Duda recurrente sobre '(.+)' entre \d+ autores")


def _json(valor):
    return json.loads(valor) if isinstance(valor, str) else (valor or {})


def clasificaciones_de(resultado):
    """{id_mensaje: {"tipo", "tema"}} a partir del resultado guardado de un trabajo."""
    if resultado.get("clasificaciones"):
        return {i: c for i, c in resultado["clasificaciones"].items()
                if isinstance(c, dict) and c.get("tipo") in TIPOS_ANALISIS}
    salida = {}

    def anotar(fuente, tipo, tema=None):
        previa = salida.get(fuente)
        if previa is None or PRIORIDAD[tipo] > PRIORIDAD[previa["tipo"]]:
            salida[fuente] = {"tipo": tipo, "tema": tema or (previa or {}).get("tema")}
        elif tema and not previa.get("tema"):
            previa["tema"] = tema

    enrutamiento = resultado.get("enrutamiento") or {}
    for d in enrutamiento.get("decisiones") or []:
        tipo = {"bloqueo": "bloqueo", "dudas": "duda", "logro": "logro"}.get(d.get("ruta"))
        if tipo:
            hallado = TEMA_DUDA.search(d.get("motivo") or "") if tipo == "duda" else None
            for fuente in d.get("fuentes") or []:
                anotar(fuente, tipo, hallado.group(1)[:MAX_TEMA] if hallado else None)
    for o in enrutamiento.get("sin_ruta") or []:
        motivo = o.get("motivo") or ""
        if motivo.startswith("Duda sin recurrencia"):
            anotar(o.get("fuente"), "duda")
        elif motivo.startswith("Bloqueo ya alertado"):
            anotar(o.get("fuente"), "bloqueo")
    return salida


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true", help="guardar los cambios (por defecto, solo informar)")
    args = p.parse_args()
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    propuestas, cambios, por_tipo = {}, 0, Counter()
    with psycopg.connect(url, row_factory=dict_row) as c:
        for t in c.execute("""SELECT resultado FROM trabajos_worker WHERE estado='terminado'
                ORDER BY actualizado""").fetchall():
            resultado = _json(t["resultado"])
            if resultado.get("simulado"):
                continue
            for fuente, clase in clasificaciones_de(resultado).items():
                previa = propuestas.get(fuente)
                if previa is None or PRIORIDAD[clase["tipo"]] > PRIORIDAD[previa["tipo"]]:
                    propuestas[fuente] = clase
        for fuente, clase in sorted(propuestas.items()):
            tema = clase.get("tema") if isinstance(clase.get("tema"), str) else None
            fila = c.execute("SELECT tipo, tema_ref FROM mensajes WHERE id_mensaje=%s", (fuente,)).fetchone()
            if fila is None:
                continue
            nuevo_tipo = clase["tipo"] if fila["tipo"] == TIPO_POR_DEFECTO else fila["tipo"]
            nuevo_tema = fila["tema_ref"] or tema
            if (nuevo_tipo, nuevo_tema) == (fila["tipo"], fila["tema_ref"]):
                continue
            cambios += 1
            por_tipo[nuevo_tipo] += 1
            if args.aplicar:
                c.execute("UPDATE mensajes SET tipo=%s, tema_ref=%s WHERE id_mensaje=%s", (nuevo_tipo, nuevo_tema, fuente))
    print(f"mensajes_con_clasificacion={len(propuestas)} con_cambios={cambios} aplicado={args.aplicar}")
    print(f"tipos_resultantes={dict(por_tipo)}")


if __name__ == "__main__":
    main()
