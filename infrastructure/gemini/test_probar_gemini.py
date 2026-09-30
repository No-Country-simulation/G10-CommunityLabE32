"""Pruebas sin red, sin credenciales reales ni consumo de Gemini."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import probar_gemini as script


class Response(io.BytesIO):
    status = 200


def success():
    return Response(json.dumps({"candidates": [{"content": {"parts": [
        {"text": "razonamiento privado", "thought": True},
        {"text": "OK_GEMINI"},
    ]}}]}).encode())


class GeminiTests(unittest.TestCase):
    def test_request_uses_official_host_header_and_synthetic_text(self):
        with patch.object(script.urllib.request, "urlopen", return_value=success()) as call:
            result = script.verify_model("fake-secret", "principal", "gemini-example")
        request = call.call_args.args[0]
        self.assertTrue(result["correcto"])
        self.assertEqual(request.full_url,
                         "https://generativelanguage.googleapis.com/v1beta/models/gemini-example:generateContent")
        self.assertNotIn("fake-secret", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "fake-secret")
        self.assertEqual(json.loads(request.data)["contents"][0]["parts"][0]["text"], script.PROMPT)
        self.assertEqual(call.call_args.kwargs["timeout"], 60)

    def test_http_errors_do_not_reveal_server_body_or_key(self):
        for code in (401, 429, 503):
            with self.subTest(code=code):
                error = urllib.error.HTTPError("https://example", code, "fake-secret", {},
                                               io.BytesIO(b"fake-secret private data"))
                with patch.object(script.urllib.request, "urlopen", side_effect=error) as call:
                    result = script.verify_model("fake-secret", "principal", "gemini-example")
                self.assertFalse(result["correcto"])
                self.assertEqual(result["http"], code)
                self.assertNotIn("fake-secret", json.dumps(result))
                self.assertEqual(call.call_count, 1)

    def test_invalid_responses_and_connection_errors_fail_safely(self):
        for payload in (b"not json", b"null", b"[]", b'{"candidates": []}',
                        b'{"candidates":[{"content":{"parts":[{"text":"fake-secret"}]}}]}'):
            with self.subTest(payload=payload):
                with patch.object(script.urllib.request, "urlopen", return_value=Response(payload)):
                    result = script.verify_model("fake-secret", "principal", "gemini-example")
                self.assertFalse(result["correcto"])
                self.assertNotIn("fake-secret", json.dumps(result))
        with patch.object(script.urllib.request, "urlopen", side_effect=OSError("fake-secret")):
            self.assertEqual(script.verify_model("fake-secret", "principal", "gemini-example")["error"],
                             "error_conexion")

    def test_environment_overrides_private_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text('# comentario\nGEMINI_API_KEY="file-secret"\nGEMINI_MODEL=from-file\n', encoding="utf-8")
            with patch.dict(os.environ, {"GEMINI_API_KEY": "env-secret"}, clear=True):
                config = script.read_config(path)
            self.assertEqual(config["GEMINI_API_KEY"], "env-secret")
            self.assertEqual(config["GEMINI_MODEL"], "from-file")

    def test_cli_roles_reports_and_exit_code(self):
        for role, expected in (("ambos", 2), ("principal", 1), ("respaldo", 1)):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                with patch.object(script, "ROOT", Path(folder)), patch.dict(os.environ, {
                    "GEMINI_API_KEY": "fake-secret", "GEMINI_MODEL": "main-model",
                    "GEMINI_FALLBACK_MODEL": "backup-model",
                }, clear=True), patch.object(script.urllib.request, "urlopen", side_effect=lambda *a, **k: success()) as call:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        status = script.main(["--rol", role, "--env-file", str(Path(folder) / ".env")])
                report = (Path(folder) / "resultados" / ("resultado-" + role + ".json")).read_text()
                self.assertEqual(status, 0)
                self.assertEqual(call.call_count, expected)
                self.assertNotIn("fake-secret", report + output.getvalue())

    def test_missing_placeholder_and_invalid_model_make_no_request(self):
        configs = ({}, {"GEMINI_API_KEY": "coloca_tu_clave_privada"},
                   {"GEMINI_API_KEY": "fake-secret", "GEMINI_MODEL": "../../bad"})
        for config in configs:
            with self.subTest(config=config), tempfile.TemporaryDirectory() as folder:
                with patch.dict(os.environ, config, clear=True), patch.object(script.urllib.request, "urlopen") as call:
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                        script.main(["--env-file", str(Path(folder) / ".env")])
                self.assertEqual(error.exception.code, 2)
                call.assert_not_called()

    def test_cli_failure_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(script, "ROOT", Path(folder)), patch.dict(os.environ, {
                "GEMINI_API_KEY": "fake-secret", "GEMINI_MODEL": "main-model",
            }, clear=True), patch.object(script.urllib.request, "urlopen", side_effect=TimeoutError()):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(script.main(["--rol", "principal", "--env-file", str(Path(folder) / ".env")]), 1)


if __name__ == "__main__":
    unittest.main()
