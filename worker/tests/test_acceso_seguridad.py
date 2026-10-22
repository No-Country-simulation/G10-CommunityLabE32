"""Aceptación de autenticación y autorización sobre PostgreSQL local aislado (127.0.0.1:15439/worker_local).

Cuentas, contraseñas, claves y tokens son ficticios y se generan en cada ejecución. Sin red externa.
Cubre: registro cerrado, roles, sesiones revocables (cookie HttpOnly + CSRF), JWT vencidos o
manipulados, la antigua clave por defecto, límite de intentos, separación operador/puente,
lecturas privadas, healthchecks, visibilidad de importaciones históricas y migración de esquema.
Un único TestClient por prueba: el motor async de la API no se comparte entre event loops.
"""
import base64
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from urllib.parse import urlparse

import pytest

OPERADOR = "operador-" + secrets.token_hex(8)
PUENTE = "puente-" + secrets.token_hex(8)
CLAVE_JWT = secrets.token_urlsafe(48)
CLAVE_PUBLICADA = "super-secret-communitylab-key-32-segura"   # antiguo valor por defecto del repositorio
CONTRASENA = "contrasena-ficticia-" + secrets.token_hex(4)


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
        c.execute("TRUNCATE trabajos_worker, activos, mensajes, solicitudes_procesamiento, estado_puente, banners, "
                  "discord_importacion_mensajes, discord_mensajes_historicos, discord_importaciones")
        c.execute("TRUNCATE usuarios, sesiones RESTART IDENTITY CASCADE")
    return q


@pytest.fixture
def entorno(cola, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", cola.url.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("OPERADOR_TOKEN", OPERADOR)
    monkeypatch.setenv("PUENTE_TOKEN", PUENTE)
    monkeypatch.setenv("JWT_SECRET_KEY", CLAVE_JWT)
    monkeypatch.setenv("SESION_COOKIE_SEGURA", "false")      # TestClient habla HTTP; Secure se prueba aparte
    for v in ("REGISTRO_PUBLICO", "LOGIN_MAX_INTENTOS", "LOGIN_MAX_INTENTOS_IP", "LOGIN_VENTANA_SEGUNDOS"):
        monkeypatch.delenv(v, raising=False)
    from backend.app.core.database import engine
    from backend.app.services.limite_login import LIMITE
    engine.sync_engine.dispose(close=False)
    LIMITE.reiniciar()
    return cola


@pytest.fixture
def c(entorno):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as cliente:
        yield cliente


def crear_cuenta(cola, email, rol="operador", activo=True):
    from backend.app.services.auth import hash_contrasena
    with cola.conectar() as c:
        return c.execute("INSERT INTO usuarios (email, hashed_password, full_name, rol, is_active, created_at) "
                         "VALUES (%s, %s, 'Cuenta ficticia', %s, %s, now()) RETURNING id",
                         (email, hash_contrasena(CONTRASENA), rol, activo)).fetchone()["id"]


def entrar(c, email, contrasena=CONTRASENA):
    """Inicia sesión (reemplaza la cookie anterior). Devuelve la cabecera CSRF y la cookie."""
    c.cookies.clear()
    r = c.post("/api/auth/login", data={"username": email, "password": contrasena})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}, c.cookies.get("cl_sesion")


def como(c, cookie):
    """Actúa con una cookie de sesión guardada, o como anónimo con None."""
    c.cookies.clear()
    if cookie:
        c.cookies.set("cl_sesion", cookie)


def contar(cola, tabla):
    with cola.conectar() as c:
        return c.execute(f"SELECT count(*) n FROM {tabla}").fetchone()["n"]


def lote(ids=("s-1",)):
    return {"origen_comunidad": "prueba", "periodo_referencia": "2026-W43", "cierre_periodo": False,
            "interacciones": [{"id": i, "autor": "a", "canal": "general", "fecha": "2026-10-19T10:00:00Z",
                               "texto": f"Mensaje ficticio {i}"} for i in ids]}


def sembrar_activo(cola, id_activo="act-seg-1"):
    with cola.conectar() as c:
        c.execute("""INSERT INTO activos (id_activo, formato, titulo, copy, estado, fuentes, version,
            fecha_creacion, fecha_actualizacion) VALUES (%s, 'faq', 'Título ficticio', 'Texto ficticio', 'generado',
            '["m-1"]', 1, now(), now())""", (id_activo,))
    return id_activo


def copy_de(cola, id_activo):
    with cola.conectar() as c:
        return c.execute("SELECT copy FROM activos WHERE id_activo=%s", (id_activo,)).fetchone()["copy"]


LECTURAS_PRIVADAS = ["/api/mensajes", "/api/curaduria/activos", "/api/curaduria/activos/x",
                     "/api/curaduria/activos/x/banners", "/api/banners/x.svg", "/api/v1/trabajos/x",
                     "/api/v1/procesamiento-pendientes/actual", "/api/v1/procesamiento-pendientes/x",
                     "/api/v1/discord/historico/importaciones", "/api/v1/discord/historico/importaciones/x"]
LECTURAS_DE_CUENTA = ["/api/dashboard/kpis", "/api/dashboard/ambitos", "/api/mensajes/sentimiento/resumen",
                      "/api/auth/me", "/api/auth/sesion"]


# --- Público y anónimo -------------------------------------------------------------------

def test_healthchecks_publicos_y_lecturas_privadas_cerradas(c):
    assert c.get("/").status_code == 200 and c.get("/health").json()["estado"] == "ok"
    for ruta in LECTURAS_PRIVADAS + LECTURAS_DE_CUENTA:
        assert c.get(ruta).status_code == 401, ruta


def test_escrituras_anonimas_rechazadas_sin_efectos(entorno, c):
    a = sembrar_activo(entorno)
    assert c.post("/api/v1/trabajos", json=lote()).status_code == 401
    assert c.post("/api/mensajes/procesamientos", files={"file": ("l.json", b"[]")},
                  data={"origen_comunidad": "x", "periodo_referencia": "y"}).status_code == 401
    assert c.patch(f"/api/curaduria/activos/{a}", json={"copy": "Cambiado por anónimo"}).status_code == 401
    assert c.post("/api/v1/procesamiento-pendientes").status_code == 401
    assert c.post(f"/api/curaduria/activos/{a}/banners").status_code == 401
    assert contar(entorno, "trabajos_worker") == 0 and contar(entorno, "solicitudes_procesamiento") == 0
    assert contar(entorno, "banners") == 0 and copy_de(entorno, a) == "Texto ficticio"


def test_registro_publico_cerrado_por_defecto_y_sin_eleccion_de_rol(entorno, c, monkeypatch):
    r = c.post("/api/auth/register", json={"email": "nueva@example.com", "password": CONTRASENA})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "registro_deshabilitado")
    assert contar(entorno, "usuarios") == 0
    monkeypatch.setenv("REGISTRO_PUBLICO", "true")
    assert c.post("/api/auth/register", json={"email": "nueva@example.com", "password": CONTRASENA,
                                              "rol": "administrador"}).status_code == 422
    r = c.post("/api/auth/register", json={"email": "Nueva@Example.com", "password": CONTRASENA})
    assert r.status_code == 201 and r.json()["rol"] == "usuario" and r.json()["email"] == "nueva@example.com"
    assert c.post("/api/auth/register", json={"email": "otra@example.com", "password": "corta"}).status_code == 422
    h, _ = entrar(c, "nueva@example.com")
    r = c.post("/api/v1/procesamiento-pendientes", headers=h)
    assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "permiso_insuficiente")
    assert contar(entorno, "solicitudes_procesamiento") == 0


# --- Roles ------------------------------------------------------------------------------

def test_usuario_sin_permisos_de_operador_y_operador_autorizado(entorno, c):
    crear_cuenta(entorno, "lectora@example.com", rol="usuario")
    crear_cuenta(entorno, "operadora@example.com", rol="operador")
    a = sembrar_activo(entorno)
    h, _ = entrar(c, "lectora@example.com")
    for ruta in LECTURAS_DE_CUENTA:
        assert c.get(ruta).status_code == 200, ruta
    for ruta in ("/api/mensajes", "/api/curaduria/activos", "/api/v1/discord/historico/importaciones"):
        assert c.get(ruta).status_code == 403, ruta
    assert c.post("/api/v1/procesamiento-pendientes", headers=h).status_code == 403
    assert c.patch(f"/api/curaduria/activos/{a}", json={"copy": "x"}, headers=h).status_code == 403
    assert c.post("/api/v1/trabajos", json=lote(), headers=h).status_code == 403
    assert c.get("/api/auth/usuarios").status_code == 403
    assert contar(entorno, "trabajos_worker") == 0 and contar(entorno, "solicitudes_procesamiento") == 0
    assert copy_de(entorno, a) == "Texto ficticio"
    h, _ = entrar(c, "operadora@example.com")
    assert c.get("/api/mensajes").status_code == 200
    assert c.post("/api/v1/procesamiento-pendientes", headers=h).status_code == 202
    assert c.patch(f"/api/curaduria/activos/{a}", json={"copy": "Texto revisado"}, headers=h).status_code == 200
    assert c.post("/api/v1/trabajos", json=lote(), headers=h).status_code == 202
    assert c.get("/api/auth/usuarios").status_code == 403              # operador no es administrador
    assert contar(entorno, "solicitudes_procesamiento") == 1 and contar(entorno, "trabajos_worker") == 1


def test_csrf_obligatorio_en_escrituras_con_cookie(entorno, c):
    crear_cuenta(entorno, "operadora@example.com")
    a = sembrar_activo(entorno)
    entrar(c, "operadora@example.com")
    for cabeceras in ({}, {"X-CSRF-Token": "falso"}):
        r = c.patch(f"/api/curaduria/activos/{a}", json={"copy": "Sin CSRF"}, headers=cabeceras)
        assert (r.status_code, r.json()["detail"]["codigo"]) == (403, "csrf_invalido")
        assert c.post("/api/v1/procesamiento-pendientes", headers=cabeceras).status_code == 403
        assert c.post("/api/auth/logout", headers=cabeceras).status_code == 403
    assert contar(entorno, "solicitudes_procesamiento") == 0 and copy_de(entorno, a) == "Texto ficticio"
    assert c.get("/api/auth/sesion").status_code == 200                # el logout sin CSRF no cerró la sesión


def test_cookie_httponly_secure_samesite_y_sin_token_en_el_cuerpo(entorno, c, monkeypatch):
    monkeypatch.delenv("SESION_COOKIE_SEGURA")
    crear_cuenta(entorno, "operadora@example.com")
    r = c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "cl_sesion=" in cookie and "httponly" in cookie and "secure" in cookie
    assert "samesite=strict" in cookie and "path=/api" in cookie
    assert set(r.json()) == {"usuario", "csrf_token", "expira"} and "access_token" not in r.text
    assert "hashed_password" not in r.text and r.headers["cache-control"] == "no-store"


# --- Sesiones: vencidas, manipuladas, revocadas -------------------------------------------

def _jwt(clave, **cambios):
    from jose import jwt
    ahora = datetime.now(timezone.utc)
    datos = {"sub": "1", "jti": "inexistente", "iat": int(ahora.timestamp()),
             "exp": int((ahora + timedelta(hours=1)).timestamp()), "typ": "sesion", **cambios}
    return jwt.encode({k: v for k, v in datos.items() if v is not None}, clave, algorithm="HS256")


def rechazado_en_todas(c, token):
    como(c, token)
    for ruta in LECTURAS_PRIVADAS + LECTURAS_DE_CUENTA:
        assert c.get(ruta).status_code == 401, ruta
    assert c.post("/api/v1/procesamiento-pendientes").status_code == 401


def test_tokens_vencidos_manipulados_o_con_la_clave_publicada(entorno, c):
    from jose import jwt
    uid = crear_cuenta(entorno, "operadora@example.com")
    _, valido = entrar(c, "operadora@example.com")
    jti = jwt.get_unverified_claims(valido)["jti"]
    ahora = datetime.now(timezone.utc)
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub=str(uid), jti=jti, iat=int((ahora - timedelta(days=31)).timestamp()),
                               exp=int((ahora - timedelta(days=30)).timestamp())))   # vencido
    rechazado_en_todas(c, _jwt(CLAVE_PUBLICADA, sub=str(uid), jti=jti))      # antigua clave por defecto
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub=str(uid), jti=None))            # sin jti
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub=str(uid), jti=jti, exp=None))   # sin exp
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub=str(uid), jti=jti, typ=None))   # sin tipo de sesión
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub=str(uid + 1), jti=jti))        # otro sujeto con la misma sesión
    rechazado_en_todas(c, _jwt(CLAVE_JWT, sub="operadora@example.com", jti=jti))  # email «plausible»
    cabecera, cuerpo, firma = valido.split(".")
    rechazado_en_todas(c, f"{cabecera}.{cuerpo[:-2]}AA.{firma}")             # cuerpo manipulado
    nada = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    rechazado_en_todas(c, f"{nada}.{cuerpo}.")                                # alg=none
    como(c, valido)
    assert c.get("/api/mensajes").status_code == 200                        # control: la sesión real sí vale


def test_clave_jwt_ausente_o_publicada_cierra_el_login_pero_no_el_operador_por_terminal(entorno, c, monkeypatch):
    crear_cuenta(entorno, "operadora@example.com")
    for valor in (None, "corta", CLAVE_PUBLICADA):
        if valor is None:
            monkeypatch.delenv("JWT_SECRET_KEY")
        else:
            monkeypatch.setenv("JWT_SECRET_KEY", valor)
        como(c, None)
        r = c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA})
        assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "autenticacion_no_configurada")
        como(c, _jwt(CLAVE_PUBLICADA))
        assert c.get("/api/mensajes").status_code == 503
        como(c, None)
        assert c.get("/api/mensajes", headers={"X-Operador-Token": OPERADOR}).status_code == 200
        assert c.get("/health").status_code == 200


def test_logout_revoca_la_sesion_en_el_servidor(entorno, c):
    crear_cuenta(entorno, "operadora@example.com")
    h, guardada = entrar(c, "operadora@example.com")
    r = c.post("/api/auth/logout", headers=h)
    assert r.status_code == 204 and "cl_sesion=" in r.headers["set-cookie"]
    assert c.get("/api/auth/sesion").status_code == 401
    rechazado_en_todas(c, guardada)        # reutilizar la cookie copiada antes del logout no sirve


def test_deshabilitar_o_cambiar_rol_revoca_y_el_login_no_revela_la_causa(entorno, c):
    crear_cuenta(entorno, "admin@example.com", rol="administrador")
    uid = crear_cuenta(entorno, "operadora@example.com")
    ha, admin = entrar(c, "admin@example.com")
    _, op = entrar(c, "operadora@example.com")
    assert c.get("/api/mensajes").status_code == 200
    como(c, admin)
    assert c.patch(f"/api/auth/usuarios/{uid}", json={"rol": "usuario"}, headers=ha).status_code == 200
    como(c, op)
    assert c.get("/api/mensajes").status_code == 401                        # revocada al cambiar el rol
    _, op = entrar(c, "operadora@example.com")
    assert c.get("/api/mensajes").status_code == 403                        # nuevo rol, leído de la base
    como(c, admin)
    assert c.patch(f"/api/auth/usuarios/{uid}", json={"is_active": False}, headers=ha).status_code == 200
    como(c, op)
    assert c.get("/api/auth/sesion").status_code == 401
    como(c, None)
    deshabilitada = c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA})
    inexistente = c.post("/api/auth/login", data={"username": "nadie@example.com", "password": CONTRASENA})
    incorrecta = c.post("/api/auth/login", data={"username": "admin@example.com", "password": "otra-" + CONTRASENA})
    assert deshabilitada.status_code == inexistente.status_code == incorrecta.status_code == 401
    assert deshabilitada.json() == inexistente.json() == incorrecta.json()
    como(c, admin)
    mia = c.get("/api/auth/me").json()["id"]
    assert c.patch(f"/api/auth/usuarios/{mia}", json={"rol": "usuario"}, headers=ha).status_code == 409


def test_administrador_crea_cuentas_y_el_token_de_operador_no_administra(entorno, c):
    crear_cuenta(entorno, "admin@example.com", rol="administrador")
    assert c.get("/api/auth/usuarios", headers={"X-Operador-Token": OPERADOR}).status_code == 401
    ha, _ = entrar(c, "admin@example.com")
    r = c.post("/api/auth/usuarios", json={"email": "nuevo@example.com", "password": CONTRASENA, "rol": "operador"},
               headers=ha)
    assert r.status_code == 201 and r.json()["rol"] == "operador"
    assert c.post("/api/auth/usuarios", json={"email": "nuevo@example.com", "password": CONTRASENA},
                  headers=ha).status_code == 409
    assert c.post("/api/auth/usuarios", json={"email": "x@example.com", "password": CONTRASENA, "rol": "root"},
                  headers=ha).status_code == 422
    entrar(c, "nuevo@example.com")
    assert c.get("/api/mensajes").status_code == 200


def test_administrador_restablece_contrasena_revoca_sesiones_y_valida_largo(entorno, c):
    crear_cuenta(entorno, "admin@example.com", rol="administrador")
    uid = crear_cuenta(entorno, "operadora@example.com")
    ha, admin = entrar(c, "admin@example.com")
    _, op = entrar(c, "operadora@example.com")
    como(c, admin)
    assert c.patch(f"/api/auth/usuarios/{uid}", json={"new_password": "corta"}, headers=ha).status_code == 422
    temporal = "temporal-" + CONTRASENA
    r = c.patch(f"/api/auth/usuarios/{uid}", json={"new_password": temporal}, headers=ha)
    assert r.status_code == 200 and "password" not in r.text and "hashed" not in r.text
    como(c, op)
    assert c.get("/api/auth/sesion").status_code == 401                    # sesiones previas revocadas
    como(c, None)
    assert c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA}).status_code == 401
    entrar(c, "operadora@example.com", temporal)
    assert c.get("/api/mensajes").status_code == 200
    ho, _ = entrar(c, "operadora@example.com", temporal)
    assert c.patch(f"/api/auth/usuarios/{uid}", json={"new_password": temporal}, headers=ho).status_code == 403


def test_cambiar_contrasena_exige_la_actual_y_revoca_otras_sesiones(entorno, c):
    crear_cuenta(entorno, "operadora@example.com")
    _, otra = entrar(c, "operadora@example.com")
    h, actual = entrar(c, "operadora@example.com")
    nueva = "otra-contrasena-" + secrets.token_hex(4)
    assert c.patch("/api/auth/me", json={"new_password": nueva}, headers=h).status_code == 400
    assert c.patch("/api/auth/me", json={"email": "cambio@example.com"}, headers=h).status_code == 400
    assert c.patch("/api/auth/me", json={"rol": "administrador"}, headers=h).status_code == 422
    assert c.patch("/api/auth/me", json={"current_password": CONTRASENA, "new_password": nueva},
                   headers=h).status_code == 200
    assert c.get("/api/auth/sesion").status_code == 200                     # la sesión actual sigue
    como(c, otra)
    assert c.get("/api/auth/sesion").status_code == 401                     # las demás se revocan
    entrar(c, "operadora@example.com", nueva)


# --- Límite de intentos --------------------------------------------------------------------

def test_limite_de_intentos_temporal_y_sin_bloquear_a_otras_ips(entorno, c, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_INTENTOS", "3")
    crear_cuenta(entorno, "operadora@example.com")
    for _ in range(3):
        assert c.post("/api/auth/login", data={"username": "operadora@example.com",
                                               "password": "mala-mala-mala"}).status_code == 401
    r = c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (429, "demasiados_intentos")
    from backend.app.services.limite_login import LimiteLogin
    reloj = {"t": 0.0}
    limite = LimiteLogin(reloj=lambda: reloj["t"])
    for _ in range(3):
        limite.fallo("10.0.0.1", "operadora@example.com")
    assert limite.bloqueado("10.0.0.1", "operadora@example.com")
    assert not limite.bloqueado("10.0.0.2", "operadora@example.com")      # la víctima entra desde otra IP
    reloj["t"] = 901.0
    assert not limite.bloqueado("10.0.0.1", "operadora@example.com")      # temporal, no permanente


def test_ip_real_solo_desde_el_proxy_declarado():
    from backend.app.services.limite_login import ip_cliente
    proxy = lambda nombre: frozenset({"172.18.0.5"}) if nombre == "proxy" else frozenset()
    pedir = lambda origen, real: NS(client=NS(host=origen), headers={"x-real-ip": real})
    # nginx (resuelto por nombre) sí: su X-Real-IP es la del cliente.
    assert ip_cliente(pedir("172.18.0.5", "203.0.113.7"), "proxy", proxy) == "203.0.113.7"
    # Otro contenedor de la MISMA red privada (web, puente) que falsifica la cabecera: no se le cree.
    assert ip_cliente(pedir("172.18.0.9", "203.0.113.7"), "proxy", proxy) == "172.18.0.9"
    # Sin proxy declarado nunca se confía, aunque el origen sea privado o loopback.
    assert ip_cliente(pedir("127.0.0.1", "203.0.113.7"), "", proxy) == "127.0.0.1"
    assert ip_cliente(pedir("10.0.0.3", "203.0.113.7"), "", proxy) == "10.0.0.3"
    # CIDR explícito y valores inválidos.
    assert ip_cliente(pedir("10.1.2.3", "203.0.113.8"), "10.1.0.0/16", proxy) == "203.0.113.8"
    assert ip_cliente(pedir("172.18.0.5", "no-es-ip"), "proxy", proxy) == "172.18.0.5"


def test_cabecera_falsificada_no_elude_el_limite(entorno, c, monkeypatch):
    """Sin proxy declarado (TestClient), cambiar X-Real-IP en cada intento no reinicia el contador."""
    monkeypatch.setenv("LOGIN_MAX_INTENTOS", "3")
    monkeypatch.setenv("LOGIN_PROXY_CONFIABLE", "")
    crear_cuenta(entorno, "operadora@example.com")
    for i in range(3):
        c.post("/api/auth/login", data={"username": "operadora@example.com", "password": "mala-mala-mala"},
               headers={"X-Real-IP": f"198.18.0.{i + 1}"})
    r = c.post("/api/auth/login", data={"username": "operadora@example.com", "password": CONTRASENA},
               headers={"X-Real-IP": "198.18.0.99"})
    assert (r.status_code, r.json()["detail"]["codigo"]) == (429, "demasiados_intentos")


# --- Puente y operador no intercambiables ----------------------------------------------------

def test_credenciales_de_puente_y_operador_no_intercambiables(entorno, c, monkeypatch):
    bearer_op, bearer_puente = {"Authorization": f"Bearer {OPERADOR}"}, {"Authorization": f"Bearer {PUENTE}"}
    assert c.post("/api/v1/puente/solicitudes/tomar", json={"origen": "discord"}, headers=bearer_op).status_code == 401
    assert c.post("/api/v1/procesamiento-pendientes", headers={"X-Operador-Token": PUENTE}).status_code == 401
    assert c.post("/api/v1/procesamiento-pendientes", headers=bearer_puente).status_code == 401
    assert c.get("/api/mensajes", headers=bearer_puente).status_code == 401
    assert c.post("/api/v1/trabajos", json=lote(), headers=bearer_op).status_code == 401
    r = c.post("/api/v1/trabajos", json=lote(), headers=bearer_puente)
    assert r.status_code == 202
    assert c.get(r.json()["consulta"], headers=bearer_puente).status_code == 200
    assert c.post("/api/v1/puente/solicitudes/tomar", json={"origen": "discord"}, headers=bearer_puente).status_code == 200
    monkeypatch.delenv("PUENTE_TOKEN")
    r = c.post("/api/v1/puente/solicitudes/tomar", json={"origen": "discord"},
               headers={"Authorization": "Bearer token-puente-interno"})       # antiguo token por defecto
    assert (r.status_code, r.json()["detail"]["codigo"]) == (503, "acceso_no_configurado")
    monkeypatch.setenv("PUENTE_TOKEN", "otro-" + PUENTE)                       # leído en cada petición
    assert c.post("/api/v1/puente/solicitudes/tomar", json={"origen": "discord"}, headers=bearer_puente).status_code == 401
    assert contar(entorno, "trabajos_worker") == 1


# --- Discord histórico: visibilidad por cuenta -------------------------------------------------

def _importacion(cola, identificador, solicitante, estado="completada"):
    with cola.conectar() as c:
        c.execute("""INSERT INTO discord_importaciones (id, guild_id, canal_id, canal_nombre, canal_tipo, desde_utc,
            hasta_utc, zona, desde_local, hasta_local, max_mensajes, solicitante, estado)
            VALUES (%s, '111111111111111111', '222222222222222222', 'c', 0, '2026-09-01Z', '2026-09-02Z', 'UTC',
                    'a', 'b', 10, %s, %s)""", (identificador, solicitante, estado))


def test_importaciones_ajenas_no_visibles_cambiando_el_id(entorno, c):
    ana = crear_cuenta(entorno, "ana@example.com")
    crear_cuenta(entorno, "beto@example.com")
    crear_cuenta(entorno, "admin@example.com", rol="administrador")
    _importacion(entorno, "imp-de-ana", f"usuario:{ana}", estado="pendiente")
    _importacion(entorno, "imp-terminal", "operador:token-compartido")
    base = "/api/v1/discord/historico/importaciones"
    h, _ = entrar(c, "beto@example.com")
    assert c.get(base).json()["items"] == []
    for ruta in (f"{base}/imp-de-ana", f"{base}/imp-de-ana/mensajes"):
        assert c.get(ruta).status_code == 404, ruta
    for accion in ("cancelar", "reanudar"):
        assert c.post(f"{base}/imp-de-ana/{accion}", headers=h).status_code == 404
    entrar(c, "ana@example.com")
    assert [i["id"] for i in c.get(base).json()["items"]] == ["imp-de-ana"]
    assert c.get(f"{base}/imp-de-ana").json()["estado"] == "pendiente"
    entrar(c, "admin@example.com")
    assert {i["id"] for i in c.get(base).json()["items"]} == {"imp-de-ana", "imp-terminal"}
    como(c, None)
    assert [i["id"] for i in c.get(base, headers={"X-Operador-Token": OPERADOR}).json()["items"]] == ["imp-terminal"]
    with entorno.conectar() as cx:
        assert cx.execute("SELECT estado FROM discord_importaciones WHERE id='imp-de-ana'").fetchone()["estado"] == "pendiente"


# --- Migración desde un esquema anterior ----------------------------------------------------

def test_migracion_desde_esquema_sin_cuentas_y_con_usuarios_sin_rol(entorno):
    """Producción hoy no tiene `usuarios`; la rama de Ian la creaba sin `rol` ni `sesiones`.
    Datos ficticios. Tras inicializar: tablas nuevas, datos intactos y cuentas previas sin privilegios."""
    with entorno.conectar() as cx:
        cx.execute("INSERT INTO trabajos_worker (id, entrada) VALUES ('t-previo', '{}'::jsonb)")
        cx.execute("DROP TABLE sesiones")
        cx.execute("DROP TABLE usuarios")
    entorno.inicializar()
    assert contar(entorno, "usuarios") == 0 and contar(entorno, "sesiones") == 0
    with entorno.conectar() as cx:
        cx.execute("DROP TABLE sesiones")
        cx.execute("DROP TABLE usuarios")
        cx.execute("""CREATE TABLE usuarios (id serial PRIMARY KEY, email varchar(255) NOT NULL UNIQUE,
            hashed_password varchar(255) NOT NULL, full_name varchar(255), is_active boolean NOT NULL,
            created_at timestamptz NOT NULL)""")
        cx.execute("INSERT INTO usuarios (email, hashed_password, is_active, created_at) "
                   "VALUES ('previa@example.com', 'hash-ficticio', true, now())")
    entorno.inicializar()
    entorno.inicializar()                                   # reaplicar es idempotente
    with entorno.conectar() as cx:
        assert cx.execute("SELECT rol FROM usuarios WHERE email='previa@example.com'").fetchone()["rol"] == "usuario"
        assert cx.execute("SELECT count(*) n FROM trabajos_worker WHERE id='t-previo'").fetchone()["n"] == 1
    with pytest.raises(Exception):
        with entorno.conectar() as cx:
            cx.execute("UPDATE usuarios SET rol='root'")


# --- Primer administrador -------------------------------------------------------------------

def test_crear_primer_administrador_sin_credenciales_predeterminadas(entorno, c, monkeypatch, capsys):
    import io
    from backend.scripts import crear_usuario
    monkeypatch.setattr("sys.stdin", io.StringIO(CONTRASENA + "\n"))
    crear_usuario.main(["--email", "Primera@Example.com", "--rol", "administrador", "--contrasena-stdin"])
    salida = capsys.readouterr()
    assert "rol=administrador" in salida.out and CONTRASENA not in salida.out + salida.err
    with pytest.raises(SystemExit):              # no reemplaza una cuenta existente
        crear_usuario.crear(entorno.url, "primera@example.com", "operador", CONTRASENA)
    with pytest.raises(SystemExit):              # contraseña corta
        crear_usuario.crear(entorno.url, "otra@example.com", "operador", "corta")
    assert contar(entorno, "usuarios") == 1
    entrar(c, "primera@example.com")
    assert c.get("/api/auth/usuarios").status_code == 200


def test_restablecer_administrador_revoca_sesiones_y_reactiva(entorno, c, monkeypatch, capsys):
    """Recuperación si se pierde la contraseña del administrador o queda deshabilitado."""
    import io
    from backend.scripts import crear_usuario
    uid = crear_cuenta(entorno, "admin@example.com", rol="administrador")
    _, vieja = entrar(c, "admin@example.com")
    with entorno.conectar() as cx:
        cx.execute("UPDATE usuarios SET is_active=false WHERE id=%s", (uid,))
    nueva = "restablecida-" + secrets.token_hex(6)
    monkeypatch.setattr("sys.stdin", io.StringIO(nueva + "\n"))
    crear_usuario.main(["--email", "admin@example.com", "--rol", "administrador", "--contrasena-stdin", "--restablecer"])
    salida = capsys.readouterr()
    assert "sesiones revocadas" in salida.out and nueva not in salida.out + salida.err
    como(c, vieja)
    assert c.get("/api/auth/sesion").status_code == 401                     # la sesión anterior ya no vale
    entrar(c, "admin@example.com", nueva)
    assert c.get("/api/auth/usuarios").status_code == 200
    with pytest.raises(SystemExit):                                           # no crea cuentas nuevas
        crear_usuario.restablecer(entorno.url, "nadie@example.com", "operador", nueva)


def test_verificar_acceso_recorre_login_real_sin_mostrar_secretos(entorno, monkeypatch):
    import socket
    import threading
    import time as _t
    import uvicorn
    from backend.app.main import app
    from backend.scripts.verificar_acceso import verificar
    crear_cuenta(entorno, "admin@example.com", rol="administrador")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        _t.sleep(0.05)
    try:
        lineas = []
        assert verificar(f"http://127.0.0.1:{puerto}", "admin@example.com", CONTRASENA, lineas.append) == 0
        assert lineas == ["login=200", "sesion=200 rol=administrador lectura_administrador=200"]
        malas = []
        assert verificar(f"http://127.0.0.1:{puerto}", "admin@example.com", "otra-" + CONTRASENA, malas.append) == 1
        assert malas == ["login=401"]
        assert not any(CONTRASENA in l for l in lineas + malas)
    finally:
        servidor.should_exit = True
        hilo.join(10)
