"""Evaluación del sentimiento contra el conjunto etiquetado a mano (datos ficticios).

Uso:
  python tools/evaluar_sentimiento.py --simulado            # sin red: valida el conjunto y el cálculo
  python tools/evaluar_sentimiento.py --real --max-llamadas 2 --confirmo-consumo

--real usa la MISMA llamada de análisis del grafo (1 llamada por bloque de 40; 20 mensajes = 1
llamada, 2 si escala por contrato inválido). Requiere GEMINI_API_KEY y GEMINI_MODELOS en el
entorno y autorización explícita: consume cuota. No imprime claves ni textos, solo métricas.
"""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelines.communitylab.analisis_gemini import SENTIMIENTOS, analizar  # noqa: E402

CONJUNTO = Path(__file__).resolve().parents[1] / "pipelines/communitylab/ejemplos/evaluacion_sentimiento.json"


def metricas(esperados, obtenidos):
    """Exactitud sobre los analizados; los sin resultado se informan aparte (nunca como neutral)."""
    analizados = [i for i in esperados if obtenidos.get(i) in SENTIMIENTOS]
    aciertos = sum(1 for i in analizados if obtenidos[i] == esperados[i])
    confusion = Counter((esperados[i], obtenidos[i]) for i in analizados)
    return {"total": len(esperados), "analizados": len(analizados), "sin_resultado": len(esperados) - len(analizados),
            "exactitud_sobre_analizados": round(aciertos / len(analizados), 3) if analizados else None,
            "confusion": {f"{e}->{o}": n for (e, o), n in sorted(confusion.items())}}


def evaluar_real(lote, cfg, max_llamadas, transporte=None):
    """Analiza el lote con la llamada real del grafo. Devuelve (sentimientos, llamadas).

    El tope duro de llamadas lo aplica el presupuesto del cliente en cada intento HTTP.
    Las llamadas se informan aunque el análisis falle, para auditar el consumo.
    """
    from pipelines.communitylab.gemini import ClienteGemini
    cliente = ClienteGemini(replace(cfg, max_llamadas=max(1, min(max_llamadas, cfg.max_llamadas))),
                            transporte=transporte)
    try:
        return {i: a.get("sentimiento") for i, a in analizar(lote, cliente).items()}, cliente.presupuesto.llamadas
    except Exception:
        print(json.dumps({"llamadas": cliente.presupuesto.llamadas, "resultado": "fallo"}))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--simulado", action="store_true")
    modo.add_argument("--real", action="store_true")
    parser.add_argument("--max-llamadas", type=int, default=2)
    parser.add_argument("--confirmo-consumo", action="store_true")
    args = parser.parse_args(argv)
    datos = json.loads(CONJUNTO.read_text(encoding="utf-8"))
    esperados = {m["id"]: m["esperado"] for m in datos["interacciones"]}
    lote = {"interacciones": [{k: m[k] for k in ("id", "canal", "texto")} for m in datos["interacciones"]]}
    if args.simulado:
        obtenidos = dict(esperados)  # control del cálculo: debe dar exactitud 1.0
    else:
        if not args.confirmo_consumo:
            parser.error("--real consume cuota de Gemini: requiere --confirmo-consumo y autorización explícita")
        from pipelines.communitylab.gemini import ConfiguracionGemini
        obtenidos, llamadas = evaluar_real(lote, ConfiguracionGemini.desde_entorno(), args.max_llamadas)
        print(json.dumps({"llamadas": llamadas}))
    print(json.dumps(metricas(esperados, obtenidos), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
