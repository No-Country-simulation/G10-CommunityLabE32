"""Evaluación opt-in con IA real; usa solo casos ficticios y nunca Discord."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / "bot")]
from community_processor import procesar
from community_processor.processor import ProcessingError


async def evaluate():
    results = []
    for index, case in enumerate(json.loads((ROOT / "evaluation_cases.json").read_text(encoding="utf-8"))):
        source = {"schema_version": "discord-source-v1", "message_id": str(600 + index),
                  "guild_id": "100", "channel_id": "200", "author_id": "700",
                  "created_at": "2026-10-12T12:00:00Z", "content": case["mensaje"]}
        try:
            result = await procesar(source)
            passed = all(result[key] == expected for key, expected in case["expected"].items())
            results.append({"id": case["id"], "signals_match": passed, "decision": result})
        except ProcessingError as exc:
            results.append({"id": case["id"], "signals_match": False, "error": str(exc)})
    return {"cases": len(results), "signals_match": sum(r["signals_match"] for r in results),
            "manual_review_required": "Revisar exactitud, utilidad y privacidad de cada respuesta/alerta.", "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.connect:
        parser.error("Requiere --connect; consume la cuota del proveedor configurado")
    # Abrir antes de consumir cuota y nunca sobrescribir una evaluación anterior.
    with Path(args.output).open("x", encoding="utf-8") as f:
        report = asyncio.run(evaluate())
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Clasificaciones esperadas: {report['signals_match']}/{report['cases']}; falta revisión humana de respuestas")


if __name__ == "__main__":
    main()
