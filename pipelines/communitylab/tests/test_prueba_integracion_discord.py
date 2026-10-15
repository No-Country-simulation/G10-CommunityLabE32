from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from pipelines.communitylab import prueba_integracion_discord as script

SCRIPT = Path(script.__file__)


class BackendFalso:
    """Servidor HTTP local que imita POST/GET de /api/v1/trabajos."""

    def __init__(self, codigo_post=202, estados=("terminado",)):
        self.recibidos = []
        backend = self
        estados = list(estados)

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _responder(self, codigo, cuerpo):
                datos = json.dumps(cuerpo).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def do_POST(self):
                largo = int(self.headers["Content-Length"])
                backend.recibidos.append(json.loads(self.rfile.read(largo)))
                if codigo_post != 202:
                    return self._responder(codigo_post, {"detail": "rechazado"})
                self._responder(202, {"procesamiento_id": f"t{len(backend.recibidos)}", "estado": "recibido"})

            def do_GET(self):
                estado = estados.pop(0) if len(estados) > 1 else estados[0]
                self._responder(200, {"estado": estado})

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.servidor.server_port}/api/v1/trabajos"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


def ejecutar(*argv):
    lineas = []
    codigo = script.ejecutar(list(argv), salida=lineas.append)
    return codigo, "\n".join(lineas)


class PruebasScriptIntegracion(unittest.TestCase):
    def setUp(self):
        self.backends = []

    def tearDown(self):
        for backend in self.backends:
            backend.cerrar()

    def backend(self, **kwargs):
        b = BackendFalso(**kwargs)
        self.backends.append(b)
        return b

    def test_simulado_termina_con_codigo_cero_y_lote_valido(self):
        b = self.backend(estados=("procesando", "terminado"))
        with mock.patch.object(script.time, "sleep"):
            codigo, salida = ejecutar("--simulado", "--url", b.url)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("SIMULADOS", salida)
        lote = b.recibidos[0]
        self.assertEqual(set(lote), {"origen_comunidad", "periodo_referencia", "cierre_periodo", "interacciones"})
        self.assertEqual(len(lote["interacciones"]), 2)

    def test_trabajo_con_error_devuelve_codigo_distinto_de_cero(self):
        b = self.backend(estados=("error",))
        codigo, salida = ejecutar("--simulado", "--url", b.url)
        self.assertEqual(codigo, script.SALIDA_ERROR_BACKEND)
        self.assertIn("estado=error", salida)

    def test_error_http_del_backend(self):
        b = self.backend(codigo_post=422)
        codigo, salida = ejecutar("--simulado", "--url", b.url)
        self.assertEqual(codigo, script.SALIDA_ERROR_BACKEND)
        self.assertIn("HTTP 422", salida)

    def test_sin_conexion(self):
        codigo, salida = ejecutar("--simulado", "--url", "http://127.0.0.1:9/api/v1/trabajos")
        self.assertEqual(codigo, script.SALIDA_SIN_CONEXION)
        self.assertIn("Sin conexión", salida)

    def test_tiempo_agotado_esperando_estado_final(self):
        b = self.backend(estados=("procesando",))
        with mock.patch.object(script.time, "sleep"):
            codigo, _ = ejecutar("--simulado", "--url", b.url, "--espera", "0")
        self.assertEqual(codigo, script.SALIDA_SIN_CONEXION)

    def test_archivo_real_se_lee_sin_modificarlo_ni_borrarlo(self):
        b = self.backend()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "discord_export.jsonl"
            contenido = json.dumps({
                "schema_version": "discord-source-v1", "message_id": "77", "guild_id": "1",
                "channel_id": "2", "author_id": "3", "created_at": "2026-10-14T18:00:00+00:00",
                "content": "Mensaje REAL"}) + "\n"
            ruta.write_text(contenido, encoding="utf-8")
            codigo, salida = ejecutar("--archivo", str(ruta), "--url", b.url)
            self.assertEqual(ruta.read_text(encoding="utf-8"), contenido)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("REAL", salida)
        self.assertEqual(b.recibidos[0]["interacciones"][0]["texto"], "Mensaje REAL")

    def test_simulado_no_toca_un_export_existente_en_la_carpeta_actual(self):
        b = self.backend()
        actual = os.getcwd()
        with tempfile.TemporaryDirectory() as carpeta:
            existente = Path(carpeta) / "discord_export.jsonl"
            existente.write_text("datos reales\n", encoding="utf-8")
            os.chdir(carpeta)
            try:
                codigo, _ = ejecutar("--simulado", "--url", b.url)
            finally:
                os.chdir(actual)
            self.assertEqual(existente.read_text(encoding="utf-8"), "datos reales\n")
            self.assertEqual(os.listdir(carpeta), ["discord_export.jsonl"])
        self.assertEqual(codigo, 0)

    def test_archivo_inexistente(self):
        codigo, _ = ejecutar("--archivo", "no_existe.jsonl", "--url", "http://127.0.0.1:9")
        self.assertEqual(codigo, script.SALIDA_ENTRADA_INVALIDA)

    def test_salida_sin_emojis_en_terminal_cp1252_y_utf8(self):
        fuente = SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(all(ord(c) < 0x2000 for c in fuente), "el script no debe usar emojis")
        for codificacion in ("cp1252", "utf-8"):
            entorno = {**os.environ, "PYTHONIOENCODING": codificacion, "PYTHONUTF8": "0"}
            proceso = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--simulado", "--url", "http://127.0.0.1:9/x"],
                cwd=SCRIPT.parent, env=entorno, capture_output=True, timeout=60)
            self.assertNotIn(b"UnicodeEncodeError", proceso.stderr, codificacion)
            self.assertEqual(proceso.returncode, script.SALIDA_SIN_CONEXION, proceso.stderr)


if __name__ == "__main__":
    unittest.main()
