import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

from pipelines.communitylab import prueba_integracion_discord as script

SCRIPT = Path(script.__file__)


class BackendFalso:
    """Imita POST/GET de /api/v1/trabajos sin abrir sockets (el validador bloquea la red)."""

    url = "http://backend.falso/api/v1/trabajos"

    def __init__(self, codigo_post=202, estados=("terminado",), sin_conexion=False):
        self.recibidos = []
        self.codigo_post = codigo_post
        self.estados = list(estados)
        self.sin_conexion = sin_conexion

    def urlopen(self, peticion, timeout=None):
        if self.sin_conexion:
            raise urllib.error.URLError("conexión rechazada")
        if peticion.get_method() == "POST":
            self.recibidos.append(json.loads(peticion.data))
            if self.codigo_post != 202:
                raise urllib.error.HTTPError(peticion.full_url, self.codigo_post, "rechazado", {},
                                             io.BytesIO(b'{"detail": "rechazado"}'))
            cuerpo = {"procesamiento_id": f"t{len(self.recibidos)}", "estado": "recibido"}
        else:
            estado = self.estados.pop(0) if len(self.estados) > 1 else self.estados[0]
            cuerpo = {"estado": estado}
        return _Respuesta(json.dumps(cuerpo).encode("utf-8"))


class _Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def ejecutar(*argv):
    lineas = []
    codigo = script.ejecutar(list(argv), salida=lineas.append)
    return codigo, "\n".join(lineas)


class PruebasScriptIntegracion(unittest.TestCase):
    def test_reinicio_no_reenvia_entrega_terminada(self):
        b = self.backend()
        with tempfile.TemporaryDirectory() as carpeta:
            args = ['--simulado', '--url', b.url, '--estado', str(Path(carpeta)/'entregas.db')]
            self.assertEqual(ejecutar(*args)[0], 0)
            codigo, salida = ejecutar(*args)
        self.assertEqual(codigo, 0)
        self.assertEqual(len(b.recibidos), 1)
        self.assertIn('ya terminado', salida)

    def test_sin_esperar_reanuda_consulta_sin_reenviar(self):
        b = self.backend()
        with tempfile.TemporaryDirectory() as carpeta:
            args = ['--simulado', '--url', b.url, '--estado', str(Path(carpeta)/'entregas.db')]
            codigo, salida = ejecutar(*args, '--sin-esperar')
            self.assertEqual(codigo, 0)
            self.assertNotIn('Todos los lotes terminaron', salida)
            self.assertIn('estado final no verificado', salida)
            self.assertEqual(ejecutar(*args)[0], 0)
        self.assertEqual(len(b.recibidos), 1)

    def test_caida_despues_post_repite_misma_clave_y_payload(self):
        b = self.backend()
        claves = []
        original = b.urlopen
        def registrar(peticion, timeout=None):
            if peticion.get_method() == 'POST':
                claves.append(peticion.get_header('Idempotency-key'))
            return original(peticion, timeout)
        with tempfile.TemporaryDirectory() as carpeta, mock.patch.object(script.urllib.request, 'urlopen', registrar):
            args = ['--simulado', '--url', b.url, '--estado', str(Path(carpeta)/'entregas.db')]
            with mock.patch.object(script.Entregas, 'confirmar', side_effect=OSError('caída antes del checkpoint')):
                self.assertEqual(ejecutar(*args)[0], script.SALIDA_ENTRADA_INVALIDA)
            self.assertEqual(ejecutar(*args)[0], 0)
        self.assertEqual(len(claves), 2)
        self.assertEqual(claves[0], claves[1])
        self.assertTrue(claves[0])
        self.assertEqual(b.recibidos[0], b.recibidos[1])

    def test_archivo_creciente_solo_envia_mensajes_nuevos(self):
        b = self.backend()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta)/'eventos.jsonl'
            primero, segundo = script.mensajes_simulados()[:2]
            ruta.write_text(json.dumps(primero)+'\n', encoding='utf-8')
            args = ['--archivo', str(ruta), '--url', b.url]
            self.assertEqual(ejecutar(*args)[0], 0)
            ruta.write_text(json.dumps(primero)+'\n'+json.dumps(segundo)+'\n', encoding='utf-8')
            self.assertEqual(ejecutar(*args)[0], 0)
        self.assertEqual([len(l['interacciones']) for l in b.recibidos], [1, 1])
        self.assertNotEqual(b.recibidos[0]['interacciones'][0]['id'], b.recibidos[1]['interacciones'][0]['id'])

    def test_lote_invalido_no_se_envia_parcialmente(self):
        b = self.backend()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta)/'eventos.jsonl'
            ruta.write_text(json.dumps(script.mensajes_simulados()[0])+'\n{mal\n', encoding='utf-8')
            self.assertEqual(ejecutar('--archivo', str(ruta), '--url', b.url)[0], script.SALIDA_ENTRADA_INVALIDA)
        self.assertFalse(b.recibidos)

    def backend(self, **kwargs):
        b = BackendFalso(**kwargs)
        parche = mock.patch.object(script.urllib.request, "urlopen", b.urlopen)
        parche.start()
        self.addCleanup(parche.stop)
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
        b = self.backend(sin_conexion=True)
        codigo, salida = ejecutar("--simulado", "--url", b.url)
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
        codigo, _ = ejecutar("--archivo", "no_existe.jsonl", "--url", BackendFalso.url)
        self.assertEqual(codigo, script.SALIDA_ENTRADA_INVALIDA)

    def test_salida_sin_emojis_en_terminal_cp1252_y_utf8(self):
        fuente = SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(all(ord(c) < 0x2000 for c in fuente), "el script no debe usar emojis")
        with tempfile.TemporaryDirectory() as carpeta:
            invalido = Path(carpeta) / "invalido.jsonl"
            invalido.write_text('{"schema_version": "roto"}\n', encoding="utf-8")
            for codificacion in ("cp1252", "utf-8"):
                entorno = {**os.environ, "PYTHONIOENCODING": codificacion, "PYTHONUTF8": "0"}
                proceso = subprocess.run(
                    [sys.executable, "-B", str(SCRIPT), "--archivo", str(invalido), "--url", BackendFalso.url],
                    cwd=SCRIPT.parent, env=entorno, capture_output=True, timeout=60)
                self.assertNotIn(b"UnicodeEncodeError", proceso.stderr, codificacion)
                self.assertEqual(proceso.returncode, script.SALIDA_ENTRADA_INVALIDA, proceso.stderr)
                self.assertIn("Normalizaci".encode(), proceso.stdout)

if __name__ == "__main__":
    unittest.main()
