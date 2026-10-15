"""Prueba REAL y opcional con Gemini: consume cuota del proyecto. No se ejecuta en CI.

Requisitos (solo por entorno, nunca en Git): COMMUNITYLAB_GEMINI_REAL=1, GEMINI_API_KEY y
GEMINI_MODELOS. Usa datos ficticios del repositorio. No envía nada a Discord.

Pasos:
  1. Lista los modelos del proyecto (no genera contenido) y verifica que cada modelo de
     GEMINI_MODELOS exista y admita generateContent.
  2. Ejecuta los tres generadores con pipelines/communitylab/ejemplos/peticiones_generadores.json.
  3. Ejecuta un lote completo del grafo (ejemplos/entrada.json) con los cinco componentes reales.

La salida solo muestra métricas y validaciones; con --salida ARCHIVO guarda los textos
generados (de datos ficticios) para revisión humana fuera del repositorio.
Códigos: 0 todo válido, 1 algún paso falló, 2 no habilitada o mal configurada.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import sys
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import httpx  # noqa: E402

from pipelines.communitylab import ejecutar_lote  # noqa: E402
from pipelines.communitylab.componentes_gemini import crear_componentes_gemini  # noqa: E402
from pipelines.communitylab.gemini import ClienteGemini, ConfiguracionGemini, ErrorIA, URL_BASE  # noqa: E402
from pipelines.communitylab.generadores import generar_faq, generar_highlights, generar_post  # noqa: E402
from pipelines.communitylab.generadores.contrato import validar_contrato_salida  # noqa: E402

EJEMPLOS = RAIZ / "pipelines" / "communitylab" / "ejemplos"
GENERADORES = {"post_linkedin_x": generar_post, "faq_tip_tecnico": generar_faq,
               "community_highlights": generar_highlights}


def modelos_disponibles(cfg):
    disponibles, token = {}, None
    with httpx.Client(trust_env=False, timeout=20) as http:
        while True:
            r = http.get(URL_BASE.rstrip("/"), headers={"x-goog-api-key": cfg.clave},
                         params={"pageSize": 1000, **({"pageToken": token} if token else {})})
            if r.status_code != 200:
                raise SystemExit(f"[ERROR] Listado de modelos: HTTP {r.status_code}")
            datos = r.json()
            for m in datos.get("models", []):
                disponibles[m.get("name", "").removeprefix("models/")] = m.get("supportedGenerationMethods", [])
            token = datos.get("nextPageToken")
            if not token:
                return disponibles


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, help="archivo local para guardar los textos generados")
    args = parser.parse_args()
    if os.environ.get("COMMUNITYLAB_GEMINI_REAL") != "1":
        print("[NO EJECUTADA] Defina COMMUNITYLAB_GEMINI_REAL=1 para consumir cuota real.")
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        cfg = ConfiguracionGemini.desde_entorno()
    except ErrorIA as exc:
        print(f"[ERROR] Configuración: {exc}")
        return 2

    fallos, textos = 0, {}
    disponibles = modelos_disponibles(cfg)
    for modelo in cfg.modelos:
        ok = "generateContent" in disponibles.get(modelo, [])
        fallos += not ok
        print(f"[1] modelo {modelo}: {'disponible' if ok else 'NO disponible para generateContent'}")
    if fallos:
        return 1

    peticiones = json.loads((EJEMPLOS / "peticiones_generadores.json").read_text(encoding="utf-8"))
    for peticion in peticiones:
        formato = peticion["formato"]
        cliente = ClienteGemini(cfg)
        inicio = time.monotonic()
        try:
            salida = validar_contrato_salida(GENERADORES[formato](peticion, cliente), peticion)
            textos[formato] = salida["copy"]
            print(f"[2] {formato}: OK copy={len(salida['copy'])} caracteres fuentes={len(salida['fuentes'])} "
                  f"llamadas={cliente.presupuesto.llamadas} {time.monotonic() - inicio:.1f}s")
        except Exception as exc:
            fallos += 1
            print(f"[2] {formato}: FALLA {getattr(exc, 'codigo', type(exc).__name__)}")

    entrada = json.loads((EJEMPLOS / "entrada.json").read_text(encoding="utf-8"))
    inicio = time.monotonic()
    resultado = ejecutar_lote(entrada, crear_componentes_gemini(cfg))
    activos = resultado["activos_distribucion_generados"]
    valido = (resultado["estado"] == "completado_local" and resultado["simulado"] is False
              and all(a["estado"] == "borrador" for a in activos))
    fallos += not valido
    print(f"[3] grafo: estado={resultado['estado']} activos={sorted(a['formato'] for a in activos)} "
          f"alertas={len(resultado['alertas_internas'])} errores={[e['tipo'] for e in resultado['errores']]} "
          f"{time.monotonic() - inicio:.1f}s")
    for a in activos:
        textos[f"grafo:{a['formato']}"] = a["copy"]
    if args.salida:
        args.salida.write_text(json.dumps(textos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Textos guardados en {args.salida} (datos ficticios; no subir a Git).")
    print("[OK] Prueba real completa." if not fallos else f"[ERROR] {fallos} paso(s) fallaron.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
