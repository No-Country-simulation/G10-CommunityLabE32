"""Demo sintética: python -m pipelines.communitylab. Escribe JSON en stdout."""
import json
from pathlib import Path

from .grafo import ejecutar_lote
from .simulados import crear_componentes


def main():
    base = Path(__file__).resolve().parent / "ejemplos"
    entrada = json.loads((base / "entrada.json").read_text(encoding="utf-8"))
    senales = json.loads((base / "senales_simuladas.json").read_text(encoding="utf-8"))
    resultado = ejecutar_lote(entrada, crear_componentes(senales))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return int(bool(resultado["errores"]))


if __name__ == "__main__":
    raise SystemExit(main())
