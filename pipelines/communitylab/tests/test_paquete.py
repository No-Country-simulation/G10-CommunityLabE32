"""Verificación del uso como paquete desde la raíz del repositorio."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[3]


class PruebasPaquete(unittest.TestCase):
    def proceso(self, argumentos, extra=None):
        return subprocess.run([sys.executable, *argumentos], cwd=RAIZ,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8", **(extra or {})},
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_demo_desde_raiz(self):
        p = self.proceso(["-m", "pipelines.communitylab"])
        self.assertEqual(p.returncode, 0, p.stderr)
        salida = json.loads(p.stdout)
        self.assertEqual(salida["estado"], "completado_local")
        self.assertTrue(salida["simulado"])
        self.assertEqual(len(salida["activos_distribucion_generados"]), 3)
        self.assertEqual(len(salida["alertas_internas"]), 1)

    def test_importar_no_cambia_configuracion_del_host(self):
        p = self.proceso(["-c", "import os; import pipelines.communitylab; "
                          "assert os.environ['LANGSMITH_TRACING'] == 'true'; "
                          "assert os.environ['LANGCHAIN_TRACING_V2'] == 'true'"],
                         {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"})
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_ejecucion_local_no_activa_trazas_del_host(self):
        p = self.proceso(["-c", "from unittest.mock import patch; import socket, runpy; "
                          "p = patch.object(socket.socket, 'connect', side_effect=AssertionError('sin red')); "
                          "m = p.start(); runpy.run_module('pipelines.communitylab', run_name='demo'); "
                          "from pipelines.communitylab.__main__ import main; "
                          "assert main() == 0; m.assert_not_called(); p.stop()"],
                         {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"})
        self.assertEqual(p.returncode, 0, p.stderr)
