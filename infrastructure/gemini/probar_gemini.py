"""Verifica la conexion a Gemini con texto sintetico, sin dependencias externas."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
NAMES = ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL")
PROMPT = "Responde unicamente OK_GEMINI. Es una prueba de conexion."


def read_config(env_file):
    config = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                if name.strip() in NAMES:
                    config[name.strip()] = value.strip().strip('"').strip("'")
    for name in NAMES:
        if os.environ.get(name):
            config[name] = os.environ[name]
    return config


def verify_model(key, role, model):
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 256},
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model + ":generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    result = {"rol": role, "modelo": model, "correcto": False}
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
            result["http"] = response.status
        answer = "".join(
            part.get("text", "")
            for candidate in data.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
            if not part.get("thought")
        )
        result["correcto"] = answer.strip() == "OK_GEMINI"
        if not result["correcto"]:
            result["error"] = "respuesta_no_esperada"
    except urllib.error.HTTPError as error:
        # No guardamos el cuerpo ni el texto del error: pueden contener secretos.
        result.update(http=error.code, error="error_http")
        error.close()
    except (OSError, TimeoutError):
        result["error"] = "error_conexion"
    except (ValueError, TypeError, AttributeError):
        result["error"] = "respuesta_no_valida"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rol", choices=["ambos", "principal", "respaldo"], default="ambos")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)
    try:
        config = read_config(args.env_file)
    except (OSError, UnicodeError):
        parser.error("No se pudo leer el archivo de configuracion privada.")
    key = config.get("GEMINI_API_KEY", "")
    if not key or key == "coloca_tu_clave_privada":
        parser.error("Configura GEMINI_API_KEY en el entorno o en el archivo privado.")
    models = [("principal", config.get("GEMINI_MODEL", "")),
              ("respaldo", config.get("GEMINI_FALLBACK_MODEL", ""))]
    selected = [(role, model) for role, model in models if args.rol in ("ambos", role)]
    for _, model in selected:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", model):
            parser.error("Configura un nombre de modelo valido para cada rol seleccionado.")
        if key in model:
            parser.error("Un nombre de modelo no puede contener la credencial.")
    report = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "alcance": "Conexion con texto sintetico; sin datos del equipo ni pipeline.",
        "pruebas": [],
        "nota": "Sin reintentos ni conmutacion automatica. No mide cuotas ni facturacion.",
    }
    for role, model in selected:
        result = verify_model(key, role, model)
        report["pruebas"].append(result)
        print(role, model, "HTTP", result.get("http"),
              "OK" if result["correcto"] else "NO SUPERADA", flush=True)
    report["correcto"] = all(result["correcto"] for result in report["pruebas"])
    output = ROOT / "resultados" / ("resultado-" + args.rol + ".json")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        print("No se pudo guardar el informe local.")
        return 1
    return 0 if report["correcto"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
