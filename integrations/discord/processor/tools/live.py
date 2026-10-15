"""Pruebas opt-in de la integración final. Las claves solo vienen del entorno."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / "bot")]
from community_processor.integrated import procesar
from community_processor.processor import ProcessingError
from bot_discord.__main__ import main as bot_main
from bot_discord.contracts import Config


async def evaluate(cases):
    results = []
    for i, case in enumerate(cases):
        source = dict(schema_version="discord-source-v1", message_id=str(600+i),
                      guild_id="100", channel_id="200", author_id="700",
                      created_at=datetime.now(timezone.utc).isoformat(), content=case["mensaje"])
        try:
            result = await procesar(source)
            matched = all(result[k] == v for k,v in case["expected"].items())
            results.append({"id":case["id"], "senales_correctas":matched,
                            "mensaje_ficticio":case["mensaje"], "decision":result})
        except ProcessingError as exc:
            results.append({"id":case["id"], "senales_correctas":False, "error":str(exc)})
            # No insistir ni cambiar modelos ante errores de cuota/autenticación.
            break
    return {"casos_previstos":len(cases), "casos_ejecutados":len(results),
            "senales_correctas":sum(r["senales_correctas"] for r in results),
            "revision_humana_pendiente":"Revisar exactitud y utilidad de cada respuesta; no es aprobación automática.",
            "resultados":results, "mensajes_discord_enviados":0}


def snapshot(config):
    if not config.database.exists():
        return {"estados":{}, "registros":[]}
    with sqlite3.connect(config.database.as_uri()+"?mode=ro",uri=True) as connection:
        states=dict(connection.execute("SELECT status,COUNT(*) FROM jobs GROUP BY status"))
        records=[]
        for source, status, decision, receipt, error in connection.execute(
                "SELECT source,status,decision,receipt,error FROM jobs ORDER BY created_at,key"):
            s=json.loads(source)
            d=json.loads(decision) if decision else {}
            records.append({"message_id":s["message_id"], "channel_id":s["channel_id"],
                            "estado":status, "es_duda":d.get("es_duda"), "es_logro":d.get("es_logro"),
                            "es_bloqueo":d.get("es_bloqueo"), "envio_confirmado":bool(receipt), "error":error})
    return {"estados":states,"registros":records}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["check-ia","evaluate","listen","status"])
    parser.add_argument("--connect",action="store_true")
    parser.add_argument("--config",type=Path)
    parser.add_argument("--evidence-dir",type=Path,required=True)
    args=parser.parse_args()
    if args.command != "status" and not args.connect:
        parser.error("Requiere --connect: consume cuota; listen también publica en Discord.")
    if args.command in ("listen","status") and args.config is None:
        parser.error("Requiere --config")
    logging.disable(logging.CRITICAL)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    os.environ["COMMUNITYLAB_GEMINI_ENABLE"]="1"
    report={"fecha_utc":datetime.now(timezone.utc).isoformat(), "comando":args.command,
            "modelo":os.environ.get("COMMUNITYLAB_GEMINI_MODEL","gemini-3.5-flash-lite")}
    code=0
    if args.command in ("check-ia","evaluate"):
        cases=json.loads((ROOT/"evaluation_cases.json").read_text(encoding="utf-8"))
        if args.command == "check-ia":
            cases=[{"id":"duda_python", "mensaje":"¿Cómo puedo capturar una excepción en Python?",
                    "expected":{"es_duda":True,"es_logro":False,"es_bloqueo":False}}]
        report.update(asyncio.run(evaluate(cases)))
        code=int(report["senales_correctas"] != report["casos_previstos"])
    else:
        config=Config.load(args.config)
        if args.command == "listen":
            print("Espera estado=listo. Envía mensajes NUEVOS en los canales de pruebas. Ctrl+C para finalizar.",flush=True)
            code=bot_main(["--config",str(args.config),"listen","--connect",
                           "--processor","community_processor.integrated:procesar"])
        report.update(snapshot(config))
    report["exit_code"]=code
    name=args.command+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"
    (args.evidence_dir/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("estado=detenido")
        sys.exit(130)
    except Exception:
        print("error=prueba_local_fallida_sin_exponer_credenciales")
        sys.exit(1)
