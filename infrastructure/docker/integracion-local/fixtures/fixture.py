"""Sondas desechables de P03. No implementan Next.js, FastAPI ni LangGraph."""
import json
import os
import signal
from pathlib import Path
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["FIXTURE_ROLE"]
HEARTBEAT = Path("/tmp/p03-heartbeat")


def database_ready():
    try:
        result = subprocess.run(
            ["psql", "-X", "-tAc", "SELECT 1"],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0 and result.stdout.strip() == b"1"
    except subprocess.TimeoutExpired:
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if ROLE == "web" and self.path == "/":
            payload = {"fixture": True, "service": ROLE,
                       "message": "Prueba de infraestructura P03. No es el panel del producto."}
            status = 200
        elif self.path == ("/healthz" if ROLE == "web" else "/api/health/ready"):
            ready = ROLE == "web" or database_ready()
            payload = {"fixture": True, "service": ROLE, "ready": ready}
            status = 200 if ready else 503
        else:
            payload, status = {"fixture": True, "error": "not implemented"}, 404
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    # PID 1 ignora señales sin manejador dentro de su namespace. Esta señal de
    # prueba termina el proceso con error y deja actuar a Docker, sin docker stop.
    signal.signal(signal.SIGUSR1, lambda *_: os._exit(17))
    if ROLE == "worker":
        while True:
            if database_ready():
                HEARTBEAT.write_text(str(time.time()))
            else:
                HEARTBEAT.unlink(missing_ok=True)
            time.sleep(2)
    else:
        ThreadingHTTPServer(("0.0.0.0", 3000 if ROLE == "web" else 8000), Handler).serve_forever()
