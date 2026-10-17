"""Reproceso controlado del sentimiento de mensajes históricos (sentimiento_ref NULL).

Uso:
  python -m backend.scripts.reprocesar_sentimiento previsualizar [--canal C] [--limite N]
  python -m backend.scripts.reprocesar_sentimiento ejecutar --limite N --max-llamadas M --confirmo-consumo

- previsualizar: no llama a Gemini. Informa cuántos mensajes faltan, bloques, llamadas
  esperadas y máximas, y una estimación de tokens de entrada (caracteres / 4).
- ejecutar: reutiliza la MISMA llamada de análisis del grafo (analisis_gemini.analizar, mismo
  prompt, esquema y versión) por bloques de GEMINI_TAMANO_BLOQUE; descarta las señales y guarda
  solo el sentimiento. Se detiene al llegar a --limite mensajes o --max-llamadas, o en el primer
  fallo del proveedor.
- Reanudable e idempotente: cada bloque se guarda al terminar y solo actualiza filas que siguen
  en NULL; volver a ejecutar continúa con lo que falte y nunca pisa un valor existente.
- No imprime textos de mensajes, claves ni la URL de la base.

La ejecución real consume cuota de Gemini y requiere autorización explícita aparte.
"""
import argparse
import json
import math
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from pipelines.communitylab.analisis_gemini import SENTIMIENTOS, VERSION_SENTIMIENTO

ORIGEN = "gemini-reproceso"


def conectar(url):
    return psycopg.connect(url.replace("postgresql+asyncpg://", "postgresql://", 1),
                           row_factory=dict_row, connect_timeout=5)


def candidatos(c, canal=None, limite=None):
    consulta = "SELECT id_mensaje, canal, tipo, texto FROM mensajes WHERE sentimiento_ref IS NULL"
    parametros = []
    if canal:
        consulta += " AND canal=%s"
        parametros.append(canal)
    consulta += " ORDER BY id_mensaje"
    if limite:
        consulta += " LIMIT %s"
        parametros.append(limite)
    return c.execute(consulta, parametros).fetchall()


def previsualizar(c, tamano_bloque, canal=None, limite=None):
    filas = candidatos(c, canal, limite)
    bloques = math.ceil(len(filas) / tamano_bloque) if filas else 0
    caracteres = sum(len(f["texto"]) + len(f["canal"]) + 40 for f in filas)
    total = c.execute("SELECT count(*) AS n FROM mensajes").fetchone()["n"]
    return {"mensajes_total": total, "sin_analizar_en_alcance": len(filas), "bloques": bloques,
            "llamadas_esperadas": bloques, "llamadas_maximas": 2 * bloques,  # escalado ante contrato inválido
            "tokens_entrada_estimados": caracteres // 4, "tamano_bloque": tamano_bloque,
            "version": VERSION_SENTIMIENTO}


def guardar(c, resultados, ids, corrida):
    guardados = 0
    for id_mensaje, analisis in sorted(resultados.items()):
        valor = analisis.get("sentimiento") if isinstance(analisis, dict) else None
        if id_mensaje not in ids or valor not in SENTIMIENTOS:
            continue  # IDs ajenos o valores fuera del contrato se ignoran; quedan sin analizar.
        guardados += c.execute("""UPDATE mensajes SET sentimiento_ref=%s, sentimiento_origen=%s,
            sentimiento_version=%s, sentimiento_trabajo=%s, sentimiento_fecha=clock_timestamp()
            WHERE id_mensaje=%s AND sentimiento_ref IS NULL""",
            (valor, ORIGEN, VERSION_SENTIMIENTO, corrida, id_mensaje)).rowcount
    return guardados


def ejecutar(url, analizar, tamano_bloque, limite, max_llamadas, canal=None):
    """analizar(lote, maximo) -> ({id: {..., "sentimiento"}}, llamadas_usadas).

    `maximo` es el tope duro de llamadas para ese bloque (el resto del presupuesto global)."""
    corrida = "reproceso-" + uuid4().hex[:12]
    resumen = {"corrida": corrida, "procesados": 0, "guardados": 0, "bloques": 0, "llamadas": 0,
               "detenido_por": "completo"}
    while resumen["procesados"] < limite:
        if resumen["llamadas"] >= max_llamadas:
            resumen["detenido_por"] = "max_llamadas"
            break
        with conectar(url) as c:
            filas = candidatos(c, canal, min(tamano_bloque, limite - resumen["procesados"]))
        if not filas:
            break
        lote = {"interacciones": [{"id": f["id_mensaje"], "canal": f["canal"], "texto": f["texto"],
                                   **({"tipo": f["tipo"]} if f["tipo"] else {})} for f in filas]}
        try:
            resultados, llamadas = analizar(lote, max_llamadas - resumen["llamadas"])
            resumen["llamadas"] += llamadas
        except Exception as exc:
            resumen["detenido_por"] = f"fallo_proveedor:{type(exc).__name__}"
            break
        with conectar(url) as c:
            guardados = guardar(c, resultados, {f["id_mensaje"] for f in filas}, corrida)
        resumen["bloques"] += 1
        resumen["procesados"] += len(filas)
        resumen["guardados"] += guardados
        if guardados == 0:
            # El proveedor no devolvió sentimientos válidos para el bloque: no repetir en bucle.
            resumen["detenido_por"] = "bloque_sin_sentimientos"
            break
    if resumen["procesados"] >= limite and resumen["detenido_por"] == "completo":
        resumen["detenido_por"] = "limite"
    return resumen


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproceso controlado de sentimiento histórico")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("previsualizar")
    p.add_argument("--canal")
    p.add_argument("--limite", type=int)
    e = sub.add_parser("ejecutar")
    e.add_argument("--canal")
    e.add_argument("--limite", type=int, required=True)
    e.add_argument("--max-llamadas", type=int, required=True)
    e.add_argument("--confirmo-consumo", action="store_true",
                   help="Obligatorio: confirma que la ejecución consume cuota real de Gemini")
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("Falta DATABASE_URL")
    tamano = int(os.environ.get("GEMINI_TAMANO_BLOQUE", "40"))
    if args.comando == "previsualizar":
        with conectar(url) as c:
            print(json.dumps(previsualizar(c, tamano, args.canal, args.limite), ensure_ascii=False))
        return 0
    if not args.confirmo_consumo:
        parser.error("La ejecución real requiere --confirmo-consumo (y autorización explícita)")
    if not 1 <= args.limite <= 5000 or not 1 <= args.max_llamadas <= 200:
        parser.error("--limite debe estar entre 1 y 5000 y --max-llamadas entre 1 y 200")
    from dataclasses import replace
    from pipelines.communitylab import analisis_gemini
    from pipelines.communitylab.gemini import ClienteGemini, ConfiguracionGemini
    cfg = ConfiguracionGemini.desde_entorno()

    def analizar(lote, maximo):
        # Cliente nuevo por bloque con tope duro = presupuesto restante.
        cliente = ClienteGemini(replace(cfg, max_llamadas=max(1, min(cfg.max_llamadas, maximo))))
        return analisis_gemini.analizar(lote, cliente), cliente.llamadas
    print(json.dumps(ejecutar(url, analizar, cfg.tamano_bloque, args.limite, args.max_llamadas, args.canal),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
