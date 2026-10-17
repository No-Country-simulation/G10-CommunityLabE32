"""Puente permanente: bandeja del lector (SQLite, solo lectura) -> API de trabajos.

Política de período (compatible con el contrato de entregas del PR #27):
- Período = semana ISO UTC de la fecha del mensaje ("2026-W42") o día ("2026-10-15").
- Cada período se envía UNA sola vez, como exportación final inmutable con
  cierre_periodo=true, cuando vence (fin del período + gracia) o cuando se pide
  explícitamente con `cerrar --periodo`. Así hay un único cierre durable y los
  activos (post, FAQ, highlights) se generan una sola vez por período.
- Un mensaje que llega después de que su período se planificó es «tardío»: se
  registra y no se envía (el contrato de #27 no admite añadirlo). No hay cierre
  incremental continuo.

Procesamiento parcial bajo demanda ("Procesar pendientes" en la interfaz):
- La API registra una solicitud; el puente la toma (PUENTE_TOKEN) en su ciclo normal,
  sin programador adicional. Sin PUENTE_TOKEN la función queda desactivada.
- Por cada período ABIERTO arma un lote con cierre_periodo=false que contiene solo los
  mensajes nuevos (no enviados antes en un parcial) y, como contexto, hasta
  PUENTE_MAX_PREVIOS mensajes ya procesados en parciales anteriores, marcados previo=true
  (sirven para la recurrencia de dudas; no generan alertas ni posts repetidos).
- El conjunto de mensajes queda fijado al tomar la solicitud; lo que llega después
  espera a la siguiente. Sin mensajes nuevos no se envía nada (cero llamadas a Gemini).
- Si el trabajo termina en error o es rechazado, sus mensajes se liberan para la próxima
  solicitud (no hay reintento automático que consuma cuota).
- El cierre semanal sigue igual, se aplaza mientras haya parciales del período en curso y
  marca previo=true lo ya procesado en parciales terminados.

Entrega: reutiliza Entregas (payload y clave guardados antes del POST) y el cliente
HTTP del CLI de #27. Un trabajo solo se da por completado cuando la API informa
`terminado`; `error` y los rechazos 4xx quedan para revisión, nunca se reenvían
con otra clave. La bandeja nunca se modifica.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time

from .entregas_discord import Entregas, serializar
from .normalizador_discord import construir_lotes, normalizar_eventos
from .prueba_integracion_discord import ErrorBackend, SinConexion, _pedir, enviar_lote
from .normalizador_discord import MAX_INTERACCIONES_POR_LOTE

LOG = logging.getLogger("communitylab.puente")
UNIDADES = {"semana", "dia"}
FINALES = {"terminado", "error", "rechazado"}


def leer_bandeja(ruta):
    """Foto consistente de la bandeja en una sola lectura, sin escribir en ella."""
    ruta = Path(ruta).resolve()
    if not ruta.exists():
        return []
    conexion = sqlite3.connect(ruta.as_uri() + "?mode=ro", uri=True, timeout=30)
    try:
        filas = conexion.execute("SELECT payload FROM messages ORDER BY sequence").fetchall()
    finally:
        conexion.close()
    eventos = []
    for (payload,) in filas:
        try:
            eventos.append(json.loads(payload))
        except ValueError:
            eventos.append(None)  # cuenta como rechazado en la normalización
    return eventos


def periodo_de(fecha_utc, unidad):
    fecha = datetime.fromisoformat(fecha_utc).astimezone(timezone.utc)
    if unidad == "dia":
        return fecha.strftime("%Y-%m-%d")
    anio, semana, _ = fecha.isocalendar()
    return f"{anio}-W{semana:02d}"


def fin_de(periodo, unidad):
    if unidad == "dia":
        return datetime.strptime(periodo, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    lunes = datetime.strptime(periodo + "-1", "%G-W%V-%u").replace(tzinfo=timezone.utc)
    return lunes + timedelta(days=7)


class Puente:
    def __init__(self, estado, bandeja, url, *, origen="discord", unidad="semana",
                 gracia=3600, espera_http=10, reloj=time.time, latido=None, token=None,
                 max_previos=100):
        if unidad not in UNIDADES:
            raise ValueError("PUENTE_PERIODO debe ser semana o dia")
        self.entregas = Entregas(estado)
        self.estado, self.bandeja = Path(estado), Path(bandeja)
        self.url, self.origen, self.unidad = url.rstrip("/"), origen, unidad
        self.gracia, self.espera_http, self.reloj = gracia, espera_http, reloj
        self.latido = Path(latido) if latido else None
        # Control de solicitudes en la misma API: .../api/v1/trabajos -> .../api/v1/puente
        self.control = self.url.rsplit("/", 1)[0] + "/puente"
        self.token = token or None
        if type(max_previos) is not int or not 0 <= max_previos < MAX_INTERACCIONES_POR_LOTE:
            raise ValueError("PUENTE_MAX_PREVIOS fuera de rango")
        self.max_previos = max_previos
        with self.entregas.conexion() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS solicitudes_cierre (periodo TEXT PRIMARY KEY, creado TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tardios (ambito TEXT NOT NULL, id TEXT NOT NULL,
                    visto TEXT NOT NULL, PRIMARY KEY(ambito, id));
                -- Solicitudes parciales tomadas de la API y sus entregas (trazabilidad y reinicios).
                CREATE TABLE IF NOT EXISTS solicitudes_parciales (id TEXT PRIMARY KEY,
                    estado TEXT NOT NULL, creado TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entregas_solicitud (solicitud TEXT NOT NULL, clave TEXT NOT NULL,
                    periodo TEXT NOT NULL, nuevos INTEGER NOT NULL, contexto INTEGER NOT NULL,
                    PRIMARY KEY(solicitud, clave));
            """)

    def ambito(self, periodo):
        # Igual que Entregas.preparar: la URL forma parte del ámbito.
        return serializar([self.url, self.origen, periodo])

    def ambito_parcial(self, periodo):
        # Ámbito distinto del cierre: los parciales nunca cuentan como cierre del período.
        return serializar([self.url, self.origen, periodo, "parcial"])

    def _pedir_control(self, ruta, datos=None):
        return _pedir(f"{self.control}/{ruta}", datos if datos is not None else None,
                      timeout=self.espera_http, cabeceras={"Authorization": f"Bearer {self.token}"})

    def solicitar_cierre(self, periodo):
        with self.entregas.conexion() as c:
            c.execute("INSERT OR IGNORE INTO solicitudes_cierre VALUES (?, ?)",
                      (periodo, datetime.now(timezone.utc).isoformat()))

    def ciclo(self):
        """Un ciclo completo. Devuelve un resumen sin contenido de mensajes."""
        resumen = {"planificados": 0, "tardios_nuevos": 0, "enviados": 0, "finalizados": 0,
                   "sin_conexion": False, "rechazados_bandeja": 0}
        normalizados = normalizar_eventos([e for e in leer_bandeja(self.bandeja) if e is not None])
        resumen["rechazados_bandeja"] = normalizados["estadisticas"]["rechazados"]
        por_periodo = {}
        for m in normalizados["interacciones"]:
            por_periodo.setdefault(periodo_de(m["fecha"], self.unidad), []).append(m)
        ahora = datetime.fromtimestamp(self.reloj(), timezone.utc)
        with self.entregas.conexion() as c:
            planificados = {r[0] for r in c.execute("SELECT id FROM ambitos")}
            solicitudes = {r[0] for r in c.execute("SELECT periodo FROM solicitudes_cierre")}
        abiertos = {}
        for periodo in sorted(por_periodo):
            ambito = self.ambito(periodo)
            mensajes = por_periodo[periodo]
            if ambito in planificados:
                resumen["tardios_nuevos"] += self._registrar_tardios(ambito, mensajes)
            elif periodo in solicitudes or fin_de(periodo, self.unidad) + timedelta(seconds=self.gracia) <= ahora:
                if self._parciales_en_curso(periodo):
                    resumen["cierres_aplazados"] = resumen.get("cierres_aplazados", 0) + 1
                    LOG.info("puente periodo=%s cierre_aplazado parciales_en_curso", periodo)
                    continue
                procesados = self._procesados_en_parciales(periodo)
                marcados = [{**m, "previo": True} if m["id"] in procesados else m for m in mensajes]
                self.entregas.preparar(self.url, marcados, self.origen, periodo, True, construir_lotes)
                resumen["planificados"] += 1
                LOG.info("puente periodo=%s planificado mensajes=%d previos=%d", periodo, len(mensajes),
                         len(procesados & {m["id"] for m in mensajes}))
            else:
                abiertos[periodo] = mensajes
        try:
            if self.token:
                self._atender_solicitud(abiertos, resumen)
            self._entregar(resumen)
            if self.token:
                self._informar(abiertos)
        except SinConexion:
            resumen["sin_conexion"] = True
            LOG.warning("puente api_no_disponible reintento_en_proximo_ciclo")
        return resumen

    # --- Procesamiento parcial bajo demanda -------------------------------------------

    def _parciales_en_curso(self, periodo):
        with self.entregas.conexion() as c:
            return c.execute("SELECT count(*) FROM entregas WHERE ambito=? AND estado NOT IN "
                             "('terminado','error','rechazado')", (self.ambito_parcial(periodo),)).fetchone()[0] > 0

    def _procesados_en_parciales(self, periodo):
        """IDs ya incluidos (como nuevos) en parciales terminados del período."""
        with self.entregas.conexion() as c:
            return {r[0] for r in c.execute(
                "SELECT f.id FROM fuentes f JOIN entregas e ON e.clave=f.clave "
                "WHERE f.ambito=? AND e.estado='terminado'", (self.ambito_parcial(periodo),))}

    def pendientes(self, abiertos):
        """Mensajes de períodos abiertos que aún no entraron en ningún parcial."""
        salida = {}
        with self.entregas.conexion() as c:
            for periodo, mensajes in abiertos.items():
                enviados = {r[0] for r in c.execute("SELECT id FROM fuentes WHERE ambito=?",
                                                    (self.ambito_parcial(periodo),))}
                n = sum(1 for m in mensajes if m["id"] not in enviados)
                if n:
                    salida[periodo] = n
        return salida

    def _atender_solicitud(self, abiertos, resumen):
        with self.entregas.conexion() as c:
            activa = c.execute("SELECT id FROM solicitudes_parciales WHERE estado='planificada'").fetchone()
        if activa:
            return  # Una sola a la vez; la API tampoco entrega otra mientras esta sigue abierta.
        try:
            tomada = self._pedir_control("solicitudes/tomar", {"origen": self.origen,
                                                               "pendientes": self.pendientes(abiertos)})
        except ErrorBackend as error:
            LOG.warning("puente solicitud_no_tomada http=%s", error.estado_http)
            return
        identificador = tomada.get("id")
        if not isinstance(identificador, str) or not identificador:
            return
        lotes = self.planificar_parcial(identificador, abiertos)
        resumen["parciales"] = len(lotes)
        LOG.info("puente solicitud=%s lotes_parciales=%d", identificador, len(lotes))

    def planificar_parcial(self, solicitud, abiertos):
        """Fija (una sola vez por solicitud) qué mensajes nuevos entran y los guarda antes del POST."""
        with self.entregas.conexion() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM solicitudes_parciales WHERE id=?", (solicitud,)).fetchone():
                return [dict(r) for r in c.execute(
                    "SELECT * FROM entregas_solicitud WHERE solicitud=? ORDER BY rowid", (solicitud,))]
            planes = []
            for periodo in sorted(abiertos):
                ambito = self.ambito_parcial(periodo)
                ya = {r[0]: r[1] for r in c.execute("SELECT id, contenido FROM fuentes WHERE ambito=?", (ambito,))}
                nuevos = sorted((m for m in abiertos[periodo] if m["id"] not in ya), key=lambda m: m["id"])
                if not nuevos:
                    continue
                # Contexto: los parciales anteriores ya terminados, más recientes primero.
                terminados = {r[0] for r in c.execute(
                    "SELECT f.id FROM fuentes f JOIN entregas e ON e.clave=f.clave "
                    "WHERE f.ambito=? AND e.estado='terminado'", (ambito,))}
                previos = sorted((m for m in abiertos[periodo] if m["id"] in terminados),
                                 key=lambda m: (m["fecha"], m["id"]), reverse=True)
                for inicio in range(0, len(nuevos), MAX_INTERACCIONES_POR_LOTE - self.max_previos):
                    bloque = nuevos[inicio:inicio + MAX_INTERACCIONES_POR_LOTE - self.max_previos]
                    contexto = [{**m, "previo": True} for m in previos[:self.max_previos]]
                    lote = {"origen_comunidad": self.origen, "periodo_referencia": periodo,
                            "cierre_periodo": False,
                            "interacciones": sorted(bloque + contexto, key=lambda m: m["id"])}
                    payload = serializar(lote)
                    clave = "discord-parcial-v1-" + sha256((ambito + solicitud + payload).encode()).hexdigest()
                    c.execute("INSERT OR IGNORE INTO ambitos VALUES (?,0)", (ambito,))
                    c.execute("INSERT INTO entregas (clave,ambito,payload) VALUES (?,?,?)", (clave, ambito, payload))
                    for m in bloque:
                        c.execute("INSERT INTO fuentes VALUES (?,?,?,?)", (ambito, m["id"], serializar(m), clave))
                    c.execute("INSERT INTO entregas_solicitud VALUES (?,?,?,?,?)",
                              (solicitud, clave, periodo, len(bloque), len(contexto)))
                    planes.append({"solicitud": solicitud, "clave": clave, "periodo": periodo,
                                   "nuevos": len(bloque), "contexto": len(contexto)})
            c.execute("INSERT INTO solicitudes_parciales VALUES (?,?,?)",
                      (solicitud, "planificada" if planes else "sin_pendientes",
                       datetime.now(timezone.utc).isoformat()))
            return planes

    def _liberar(self, clave):
        """Un parcial fallido o rechazado devuelve sus mensajes a pendientes (se conserva la entrega)."""
        with self.entregas.conexion() as c:
            if c.execute("SELECT 1 FROM entregas_solicitud WHERE clave=?", (clave,)).fetchone():
                liberados = c.execute("DELETE FROM fuentes WHERE clave=?", (clave,)).rowcount
                LOG.warning("puente parcial_fallido mensajes_liberados=%d", liberados)

    def _informar(self, abiertos):
        """Informa a la API el avance de cada solicitud abierta y los pendientes actuales."""
        with self.entregas.conexion() as c:
            abiertas = [r[0] for r in c.execute(
                "SELECT id FROM solicitudes_parciales WHERE estado IN ('planificada','sin_pendientes')")]
        for solicitud in abiertas:
            with self.entregas.conexion() as c:
                lotes = [dict(r) for r in c.execute(
                    "SELECT s.periodo, s.nuevos, s.contexto, e.trabajo, e.estado FROM entregas_solicitud s "
                    "JOIN entregas e ON e.clave=s.clave WHERE s.solicitud=? ORDER BY s.rowid", (solicitud,))]
            finales = all(l["estado"] in FINALES for l in lotes)
            estado = "sin_pendientes" if not lotes else ("finalizada" if finales else "en_curso")
            try:
                self._pedir_control(f"solicitudes/{solicitud}/informe",
                                    {"origen": self.origen, "estado": estado, "lotes": lotes,
                                     "pendientes": self.pendientes(abiertos)})
            except ErrorBackend as error:
                LOG.warning("puente informe_fallido http=%s", error.estado_http)
                continue
            if estado != "en_curso":
                with self.entregas.conexion() as c:
                    c.execute("UPDATE solicitudes_parciales SET estado='informada' WHERE id=?", (solicitud,))

    def _registrar_tardios(self, ambito, mensajes):
        nuevos = 0
        with self.entregas.conexion() as c:
            enviados = {r[0] for r in c.execute("SELECT id FROM fuentes WHERE ambito=?", (ambito,))}
            for m in mensajes:
                if m["id"] not in enviados:
                    nuevos += c.execute("INSERT OR IGNORE INTO tardios VALUES (?,?,?)",
                                        (ambito, m["id"], datetime.now(timezone.utc).isoformat())).rowcount
        if nuevos:
            LOG.warning("puente tardios_nuevos=%d (periodo ya cerrado; no se envían)", nuevos)
        return nuevos

    def _entregar(self, resumen):
        with self.entregas.conexion() as c:
            pendientes = [dict(r) for r in c.execute(
                "SELECT clave, payload, trabajo, estado FROM entregas WHERE estado NOT IN ('terminado','error','rechazado') "
                "ORDER BY rowid")]
        for entrega in pendientes:
            trabajo = entrega["trabajo"]
            if not trabajo:
                try:
                    # Misma clave y mismo payload: un reenvío devuelve el mismo trabajo (idempotencia #27).
                    trabajo = enviar_lote(self.url, json.loads(entrega["payload"]), entrega["clave"])
                except ErrorBackend as error:
                    if error.estado_http and 400 <= error.estado_http < 500 and error.estado_http != 429:
                        self.entregas.confirmar(entrega["clave"], None, "rechazado")
                        self._liberar(entrega["clave"])
                        LOG.error("puente entrega_rechazada http=%s requiere_revision", error.estado_http)
                        continue
                    LOG.warning("puente api_error http=%s reintento_en_proximo_ciclo", error.estado_http)
                    return
                self.entregas.confirmar(entrega["clave"], trabajo, "aceptado")
                resumen["enviados"] += 1
            try:
                estado = _pedir(f"{self.url}/{trabajo}", timeout=self.espera_http).get("estado")
            except ErrorBackend as error:
                LOG.warning("puente consulta_fallida http=%s", error.estado_http)
                continue
            if estado in ("terminado", "error"):
                self.entregas.confirmar(entrega["clave"], trabajo, estado)
                if estado == "error":
                    self._liberar(entrega["clave"])
                resumen["finalizados"] += 1
                LOG.info("puente trabajo=%s estado=%s", trabajo, estado)

    def reconciliar(self):
        """Tras restaurar PostgreSQL a un punto anterior: los trabajos que la API ya no conoce
        (HTTP 404) vuelven a 'pendiente' sin trabajo, para reenviarse con la MISMA clave y el
        MISMO payload. No toca entregas cuyo trabajo existe. Requiere la API disponible."""
        cambios = {"verificadas": 0, "reabiertas": 0}
        with self.entregas.conexion() as c:
            filas = [dict(r) for r in c.execute("SELECT clave, trabajo FROM entregas WHERE trabajo IS NOT NULL")]
        for fila in filas:
            try:
                _pedir(f"{self.url}/{fila['trabajo']}", timeout=self.espera_http)
                cambios["verificadas"] += 1
            except ErrorBackend as error:
                if error.estado_http != 404:
                    raise
                with self.entregas.conexion() as c:
                    c.execute("UPDATE entregas SET trabajo=NULL, estado='pendiente' WHERE clave=?", (fila["clave"],))
                cambios["reabiertas"] += 1
        return cambios

    def resumen_estado(self):
        with self.entregas.conexion() as c:
            entregas = {r[0]: r[1] for r in c.execute("SELECT estado, count(*) FROM entregas GROUP BY estado")}
            tardios = c.execute("SELECT count(*) FROM tardios").fetchone()[0]
            periodos = c.execute("SELECT count(*) FROM ambitos WHERE cierre=1").fetchone()[0]
            solicitudes = {r[0]: r[1] for r in c.execute(
                "SELECT estado, count(*) FROM solicitudes_parciales GROUP BY estado")}
        return {"periodos_planificados": periodos, "entregas": entregas, "tardios": tardios,
                "solicitudes_parciales": solicitudes}

    def escribir_latido(self, resumen):
        if self.latido:
            temporal = self.latido.with_suffix(".tmp")
            temporal.write_text(json.dumps({"ts": self.reloj(), "sin_conexion": resumen["sin_conexion"]}))
            os.replace(temporal, self.latido)


def latido_sano(ruta, maximo, reloj=time.time):
    try:
        return reloj() - json.loads(Path(ruta).read_text())["ts"] <= maximo
    except (OSError, ValueError, KeyError, TypeError):
        return False


def configuracion(env=os.environ):
    return {"estado": env.get("PUENTE_ESTADO", "/data/puente/entregas.sqlite3"),
            "bandeja": env.get("PUENTE_BANDEJA", "/data/bandeja/discord.sqlite3"),
            "url": env.get("PUENTE_URL", "http://api:8000/api/v1/trabajos"),
            "origen": env.get("PUENTE_ORIGEN", "discord"),
            "unidad": env.get("PUENTE_PERIODO", "semana"),
            "gracia": int(env.get("PUENTE_GRACIA_SEGUNDOS", "3600")),
            "token": env.get("PUENTE_TOKEN") or None,
            "max_previos": int(env.get("PUENTE_MAX_PREVIOS", "100")),
            "latido": env.get("PUENTE_LATIDO", "/tmp/communitylab-puente-latido.json")}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Puente Discord -> API de CommunityLab")
    comandos = parser.add_subparsers(dest="comando", required=True)
    servir = comandos.add_parser("servir", help="Ciclo permanente")
    servir.add_argument("--intervalo", type=float, default=float(os.environ.get("PUENTE_INTERVALO", "30")))
    cerrar = comandos.add_parser("cerrar", help="Solicita el cierre explícito de un período")
    cerrar.add_argument("--periodo", required=True)
    comandos.add_parser("estado", help="Resumen sin contenido")
    comandos.add_parser("reconciliar", help="Reabre entregas cuyo trabajo ya no existe (tras restaurar la BD)")
    salud = comandos.add_parser("salud", help="Healthcheck por latido")
    salud.add_argument("--maximo", type=float, default=float(os.environ.get("PUENTE_LATIDO_MAXIMO", "120")))
    args = parser.parse_args(argv)
    cfg = configuracion()
    if args.comando == "salud":
        return 0 if latido_sano(cfg["latido"], args.maximo) else 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    puente = Puente(cfg["estado"], cfg["bandeja"], cfg["url"], origen=cfg["origen"],
                    unidad=cfg["unidad"], gracia=cfg["gracia"], latido=cfg["latido"],
                    token=cfg["token"], max_previos=cfg["max_previos"])
    if args.comando == "cerrar":
        puente.solicitar_cierre(args.periodo)
        print(f"cierre_solicitado periodo={args.periodo}")
        return 0
    if args.comando == "reconciliar":
        print(json.dumps(puente.reconciliar()))
        return 0
    if args.comando == "estado":
        print(json.dumps(puente.resumen_estado()))
        return 0
    detenido = {"valor": False}
    for senal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(senal, lambda *_: detenido.update(valor=True))
    LOG.info("puente iniciado periodo=%s gracia=%ss", cfg["unidad"], cfg["gracia"])
    while not detenido["valor"]:
        try:
            resumen = puente.ciclo()
            puente.escribir_latido(resumen)
        except (sqlite3.Error, OSError, ValueError) as exc:
            # Sin texto de la excepción: puede contener rutas o contenido.
            LOG.error("puente ciclo_fallido tipo=%s", type(exc).__name__)
        fin = time.monotonic() + args.intervalo
        while not detenido["valor"] and time.monotonic() < fin:
            time.sleep(0.5)
    LOG.info("puente detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
