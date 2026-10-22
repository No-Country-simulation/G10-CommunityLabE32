"""«Datos cargados»: listar, ocultar y eliminar lotes (solo administradores).

PostgreSQL local aislado (127.0.0.1:15439/worker_local). Cuentas, contraseñas y tokens ficticios
generados en cada ejecución; sin red.
"""
import json
import os
import secrets
from urllib.parse import urlparse

import pytest

OPERADOR = "operador-" + secrets.token_hex(8)
CONTRASENA = "contrasena-ficticia-" + secrets.token_hex(4)
URL = "/api/v1/datos/lotes"
LOTE_A = {"origen": "Comunidad-A", "periodo": "2026-W42", "fuente_ingesta": "manual"}
LOTE_B = {"origen": "discord", "periodo": "2026-W43", "fuente_ingesta": "discord"}


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
        c.execute("TRUNCATE usuarios, sesiones RESTART IDENTITY CASCADE")
    return q


@pytest.fixture
def c(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("OPERADOR_TOKEN", OPERADOR)
    monkeypatch.setenv("JWT_SECRET_KEY", secrets.token_urlsafe(48))
    monkeypatch.setenv("SESION_COOKIE_SEGURA", "false")
    from fastapi.testclient import TestClient
    from backend.app.core.database import engine
    from backend.app.main import app
    from backend.app.services.limite_login import LIMITE
    engine.sync_engine.dispose(close=False)
    LIMITE.reiniciar()
    with TestClient(app) as cliente:
        yield cliente


def entrar(cola, c, rol="administrador"):
    from backend.app.services.auth import hash_contrasena
    email = f"{rol}@example.com"
    with cola.conectar() as con:
        con.execute("INSERT INTO usuarios (email, hashed_password, full_name, rol, is_active, created_at) "
                    "VALUES (%s, %s, 'Cuenta ficticia', %s, true, now()) ON CONFLICT DO NOTHING",
                    (email, hash_contrasena(CONTRASENA), rol))
    c.cookies.clear()
    r = c.post("/api/auth/login", data={"username": email, "password": CONTRASENA})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}


def sembrar(cola, id_trabajo, lote, mensajes, activos=(), estado="terminado"):
    """Trabajo del lote con sus mensajes y activos (IDs como los genera el worker)."""
    from backend.app.services.ambito import id_activo_curaduria
    entrada = {"origen_comunidad": lote["origen"], "periodo_referencia": lote["periodo"], "cierre_periodo": False,
               "interacciones": [{"id": m, "autor": "a", "canal": "general", "fecha": "2026-10-19T10:00:00Z",
                                  "texto": "Mensaje ficticio"} for m in mensajes]}
    resultado = {"activos_distribucion_generados": [{"id_activo": g} for g, _ in activos]}
    ids = []
    with cola.conectar() as con:
        con.execute("INSERT INTO trabajos_worker (id, entrada, estado, resultado, fuente) VALUES (%s, %s, %s, %s, %s)",
                    (id_trabajo, json.dumps(entrada), estado, json.dumps(resultado), lote["fuente_ingesta"]))
        for m in mensajes:
            con.execute("""INSERT INTO mensajes (id_mensaje, autor, fecha, canal, tipo, texto)
                VALUES (%s, 'a', '2026-10-19T10:00:00Z', 'general', 'logro', 'Mensaje ficticio') ON CONFLICT DO NOTHING""", (m,))
        for g, estado_activo in activos:
            a = id_activo_curaduria(id_trabajo, g)
            ids.append(a)
            con.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
                fecha_creacion, fecha_actualizacion) VALUES (%s, 'linkedin', 'Logro', 'Texto ficticio', %s, %s, 1, now(), now())""",
                        (a, estado_activo, json.dumps(list(mensajes))))
            con.execute("""INSERT INTO banners (id, id_activo, version_texto, huella_texto, estado, proveedor, plantilla, svg)
                VALUES (%s, %s, 1, 'h', 'generado', 'local', 'p', '<svg/>')""", ("ban-" + a[-8:], a))
            con.execute("INSERT INTO activos_historial (id_activo, evento, estado, version) VALUES (%s, 'estado', %s, 1)",
                        (a, estado_activo))
    return ids


def contar(cola, tabla):
    with cola.conectar() as con:
        return con.execute(f"SELECT count(*) n FROM {tabla}").fetchone()["n"]


def test_solo_administradores(cola, c):
    sembrar(cola, "t-a", LOTE_A, ["m-1"])
    c.cookies.clear()
    assert c.get(URL).status_code == 401
    assert c.get(URL, headers={"X-Operador-Token": OPERADOR}).status_code == 401      # el token no basta
    entrar(cola, c, "operador")
    assert c.get(URL).status_code == 403
    h = entrar(cola, c)
    assert c.get(URL).status_code == 200
    # Las escrituras con sesión exigen CSRF.
    assert c.patch(f"{URL}/visibilidad", json={"lotes": [LOTE_A], "oculto": True}).status_code == 403
    assert c.patch(f"{URL}/visibilidad", json={"lotes": [LOTE_A], "oculto": True}, headers=h).status_code == 200


def test_lista_lotes_con_conteos(cola, c):
    sembrar(cola, "t-a", LOTE_A, ["m-1", "m-2"], [("g1", "generado"), ("g2", "aprobado")])
    sembrar(cola, "t-b", LOTE_B, ["m-2", "m-3"])
    entrar(cola, c)
    items = {(i["origen"], i["fuente_ingesta"]): i for i in c.get(URL).json()["items"]}
    a = items[("Comunidad-A", "manual")]
    assert (a["trabajos"], a["mensajes"], a["mensajes_compartidos"], a["activos"], a["aprobados"], a["oculto"]) == (1, 2, 1, 2, 1, False)
    assert items[("discord", "discord")]["mensajes"] == 2


def test_ocultar_y_volver_a_mostrar(cola, c):
    sembrar(cola, "t-a", LOTE_A, ["m-1"])
    sembrar(cola, "t-b", LOTE_B, ["m-2"])
    h = entrar(cola, c)
    r = c.patch(f"{URL}/visibilidad", json={"lotes": [LOTE_A], "oculto": True}, headers=h)
    assert r.json() == {"trabajos_actualizados": 1}
    assert c.get("/api/dashboard/kpis").json()["total_mensajes"] == 1            # el panel ya no lo cuenta
    assert {i["origen"]: i["oculto"] for i in c.get(URL).json()["items"]} == {"Comunidad-A": True, "discord": False}
    c.patch(f"{URL}/visibilidad", json={"lotes": [LOTE_A], "oculto": False}, headers=h)
    assert c.get("/api/dashboard/kpis").json()["total_mensajes"] == 2


def test_vista_previa_y_eliminar_conserva_lo_compartido(cola, c):
    activos_a = sembrar(cola, "t-a", LOTE_A, ["m-1", "m-2"], [("g1", "generado"), ("g2", "aprobado")])
    sembrar(cola, "t-b", LOTE_B, ["m-2", "m-3"], [("g3", "generado")])
    h = entrar(cola, c)
    previa = c.post(f"{URL}/eliminacion/vista-previa", json={"lotes": [LOTE_A]}, headers=h).json()
    assert previa == {"lotes": 1, "trabajos": 1, "en_proceso": 0, "mensajes": 1, "mensajes_conservados": 1,
                      "activos": 2, "aprobados": 1, "banners": 2}
    # Sin la confirmación literal no se borra nada.
    assert c.post(f"{URL}/eliminacion", json={"lotes": [LOTE_A], "confirmacion": "si"}, headers=h).status_code == 422
    r = c.post(f"{URL}/eliminacion", json={"lotes": [LOTE_A], "confirmacion": "ELIMINAR"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "aprobados_afectados"
    assert contar(cola, "activos") == 3
    r = c.post(f"{URL}/eliminacion", json={"lotes": [LOTE_A], "confirmacion": "ELIMINAR", "incluir_aprobados": True}, headers=h)
    assert r.status_code == 200 and r.json()["mensajes"] == 1
    with cola.conectar() as con:
        assert {f["id_mensaje"] for f in con.execute("SELECT id_mensaje FROM mensajes")} == {"m-2", "m-3"}
        assert {f["id"] for f in con.execute("SELECT id FROM trabajos_worker")} == {"t-b"}
        restantes = {f["id_activo"] for f in con.execute("SELECT id_activo FROM activos")}
        assert not restantes & set(activos_a) and len(restantes) == 1
        assert con.execute("SELECT count(*) n FROM banners WHERE id_activo = ANY(%s)", (activos_a,)).fetchone()["n"] == 0
        assert con.execute("SELECT count(*) n FROM activos_historial WHERE id_activo = ANY(%s)", (activos_a,)).fetchone()["n"] == 0
    assert [i["origen"] for i in c.get(URL).json()["items"]] == ["discord"]


def test_no_elimina_lotes_en_proceso_ni_inexistentes(cola, c):
    sembrar(cola, "t-a", LOTE_A, ["m-1"], estado="procesando")
    h = entrar(cola, c)
    r = c.post(f"{URL}/eliminacion", json={"lotes": [LOTE_A], "confirmacion": "ELIMINAR"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "lote_en_proceso"
    assert contar(cola, "trabajos_worker") == 1 and contar(cola, "mensajes") == 1
    otro = {**LOTE_A, "periodo": "no-existe"}
    r = c.post(f"{URL}/eliminacion/vista-previa", json={"lotes": [otro]}, headers=h)
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "lote_inexistente"
