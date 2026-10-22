"""Copia de los activos aprobados en OCI Object Storage (aprobados/<id>/v<versión>/).

PostgreSQL local aislado (127.0.0.1:15439/worker_local). OCI con un cliente falso: sin red, sin
identidad de instancia y sin llaves.
"""
import json
import os
import sys
from urllib.parse import urlparse

import pytest

OPERADOR = "operador-local-" + os.urandom(6).hex()
H_OP = {"X-Operador-Token": OPERADOR}
COPY = "Ana López completó la certificación OCI Foundations.\nCompartió sus apuntes con el canal.\n#OCI #Cloud"


@pytest.fixture
def cola():
    from worker.store_postgres import ColaPostgres
    url = os.environ.get("WORKER_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requiere PostgreSQL local de pruebas")
    parsed = urlparse(url)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/worker_local"
    q = ColaPostgres(url, lease=2, max_intentos=2)
    q.inicializar()
    with q.conectar() as c:
        c.execute("TRUNCATE trabajos_worker, activos, activos_historial, mensajes, banners")
    return q


@pytest.fixture
def cliente(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("OPERADOR_TOKEN", OPERADOR)
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    engine.sync_engine.dispose(close=False)
    with TestClient(app) as c:
        yield c


def crear_activo(cola, id_activo="act-oci-1", estado="generado", fuente="m-oci-1"):
    with cola.conectar() as c:
        c.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
            VALUES (%s, 'Ana López', '2026-10-15T14:00:00+00:00', 'logros', 'sin_clasificar',
                    'Hoy aprobé la certificación OCI Foundations, ¡gracias por los apuntes!')
            ON CONFLICT DO NOTHING""", (fuente,))
        c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
            fecha_creacion, fecha_actualizacion) VALUES (%s, 'linkedin', 'Logro', %s, %s, %s, 1, now(), now())""",
                  (id_activo, COPY, estado, json.dumps([fuente])))
    return id_activo


class ClienteFalso:
    def __init__(self, falla=False):
        self.objetos, self.falla = {}, falla

    def put_object(self, namespace, bucket, nombre, contenido, content_type=None):
        assert (namespace, bucket) == ("ns-prueba", "communitylab-activos-marketing")
        if self.falla:
            raise ConnectionError("OCI no disponible")
        self.objetos[nombre] = (contenido, content_type)

    def get_object(self, namespace, bucket, nombre):
        contenido = self.objetos[nombre][0]
        return type("R", (), {"data": type("D", (), {"content": contenido})()})()


@pytest.fixture
def oci_falso(monkeypatch):
    from backend.app.services import oci
    falso = ClienteFalso()
    monkeypatch.setenv("OCI_ALMACENAMIENTO", "instance_principal")
    monkeypatch.setattr(oci, "_cliente", falso)
    monkeypatch.setattr(oci, "_namespace", "ns-prueba")
    return falso


def aprobar(cliente, a, **extra):
    r = cliente.patch(f"/api/curaduria/activos/{a}", json={"estado": "aprobado", **extra}, headers=H_OP)
    assert r.status_code == 200, r.text
    return r.json()


def test_desactivado_por_defecto_no_llama_a_oci_y_aprueba(cliente, cola, monkeypatch):
    monkeypatch.delenv("OCI_ALMACENAMIENTO", raising=False)
    activo = aprobar(cliente, crear_activo(cola))
    assert activo["estado"] == "aprobado" and activo["almacenamiento_oci"]["estado"] == "desactivado"


def test_aprobar_sube_texto_y_banner_de_esa_version(cliente, cola, oci_falso):
    a = crear_activo(cola)
    with cola.conectar() as c:
        c.execute("""INSERT INTO banners (id, id_activo, version_texto, huella_texto, estado, proveedor, plantilla, svg)
            VALUES ('ban-1', %s, 1, 'h', 'generado', 'local', 'p', '<svg>v1</svg>')""", (a,))
    activo = aprobar(cliente, a, comentario_curador="Fiel a la fuente.")
    registro = activo["almacenamiento_oci"]
    assert registro["estado"] == "guardado" and registro["bucket"] == "communitylab-activos-marketing"
    assert registro["objetos"] == [f"aprobados/{a}/v1/activo.json", f"aprobados/{a}/v1/banner.svg"]
    contenido, tipo = oci_falso.objetos[f"aprobados/{a}/v1/activo.json"]
    datos = json.loads(contenido)
    assert tipo.startswith("application/json") and datos["copy"] == COPY and datos["version"] == 1
    assert "comentario_curador" not in datos and "actor" not in datos       # nada de quien revisó
    assert oci_falso.objetos[f"aprobados/{a}/v1/banner.svg"] == (b"<svg>v1</svg>", "image/svg+xml")
    # El detalle (lo que abre Curaduría) y el listado también devuelven el registro.
    assert cliente.get(f"/api/curaduria/activos/{a}", headers=H_OP).json()["almacenamiento_oci"] == registro
    listado = cliente.get("/api/curaduria/activos", params={"estado": "aprobado"}, headers=H_OP).json()["items"]
    assert [i["almacenamiento_oci"]["estado"] for i in listado] == ["guardado"]


def test_editar_y_reaprobar_sube_la_version_nueva_sin_banner_viejo(cliente, cola, oci_falso):
    a = crear_activo(cola)
    with cola.conectar() as c:
        c.execute("""INSERT INTO banners (id, id_activo, version_texto, huella_texto, estado, proveedor, plantilla, svg)
            VALUES ('ban-2', %s, 1, 'h', 'generado', 'local', 'p', '<svg>v1</svg>')""", (a,))
    aprobar(cliente, a)
    nuevo = COPY.replace("apuntes", "notas")
    activo = aprobar(cliente, a, copy=nuevo)
    assert activo["version"] == 2
    assert activo["almacenamiento_oci"]["objetos"] == [f"aprobados/{a}/v2/activo.json"]
    assert json.loads(oci_falso.objetos[f"aprobados/{a}/v2/activo.json"][0])["copy"] == nuevo
    # Cambiar solo la nota de un aprobado no vuelve a subir.
    antes = dict(oci_falso.objetos)
    r = cliente.patch(f"/api/curaduria/activos/{a}", json={"comentario_curador": "ok"}, headers=H_OP)
    assert r.status_code == 200 and oci_falso.objetos == antes


def test_fallo_de_oci_no_impide_aprobar(cliente, cola, oci_falso):
    oci_falso.falla = True
    activo = aprobar(cliente, crear_activo(cola))
    assert activo["estado"] == "aprobado"
    assert activo["almacenamiento_oci"]["estado"] == "error" and activo["almacenamiento_oci"]["error"] == "ConnectionError"


def test_script_verifica_y_sube_los_aprobados_pendientes(cola, oci_falso, monkeypatch, capsys):
    from backend.scripts import oci_almacenamiento as s
    monkeypatch.setenv("DATABASE_URL", cola.url)
    crear_activo(cola, "act-viejo", estado="aprobado", fuente="m-1")
    crear_activo(cola, "act-pend", estado="generado", fuente="m-2")
    monkeypatch.setattr(sys, "argv", ["oci_almacenamiento", "--verificar"])
    with pytest.raises(SystemExit) as fin:
        s.main()
    assert fin.value.code == 0 and "escritura=ok lectura=ok" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["oci_almacenamiento", "--subir-aprobados"])
    s.main()
    assert "aprobados_sin_copia=1 aplicado=False" in capsys.readouterr().out
    assert "aprobados/act-viejo/v1/activo.json" not in oci_falso.objetos
    monkeypatch.setattr(sys, "argv", ["oci_almacenamiento", "--subir-aprobados", "--aplicar"])
    s.main()
    assert "subidos=1 errores=0" in capsys.readouterr().out
    assert "aprobados/act-viejo/v1/activo.json" in oci_falso.objetos
    with cola.conectar() as c:
        registro = c.execute("SELECT almacenamiento_oci FROM activos WHERE id_activo='act-viejo'").fetchone()["almacenamiento_oci"]
    assert registro["estado"] == "guardado"
    s.main()   # ya tiene copia: no se repite
    assert "subidos=0 errores=0" in capsys.readouterr().out


def test_script_sin_instance_principal_no_hace_nada(monkeypatch):
    from backend.scripts import oci_almacenamiento as s
    monkeypatch.setenv("OCI_ALMACENAMIENTO", "desactivado")
    monkeypatch.setattr(sys, "argv", ["oci_almacenamiento", "--verificar"])
    with pytest.raises(SystemExit) as fin:
        s.main()
    assert "instance_principal" in str(fin.value.code)
