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

Entrega: reutiliza Entregas (payload y clave guardados antes del POST) y el cliente
HTTP del CLI de #27. Un trabajo solo se da por completado cuando la API informa
`terminado`; `error` y los rechazos 4xx quedan para revisión, nunca se reenvían
con otra clave. La bandeja nunca se modifica.
"""
import argparse
from datetime import datetime, timedelta, timezone
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
                 gracia=3600, espera_http=10, reloj=time.time, latido=None):
        if unidad not in UNIDADES:
            raise ValueError("PUENTE_PERIODO debe ser semana o dia")
        self.entregas = Entregas(estado)
        self.estado, self.bandeja = Path(estado), Path(bandeja)
        self.url, self.origen, self.unidad = url.rstrip("/"), origen, unidad
        self.gracia, self.espera_http, self.reloj = gracia, espera_http, reloj
        self.latido = Path(latido) if latido else None
        with self.entregas.conexion() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS solicitudes_cierre (periodo TEXT PRIMARY KEY, creado TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tardios (ambito TEXT NOT NULL, id TEXT NOT NULL,
                    visto TEXT NOT NULL, PRIMARY KEY(ambito, id));
            """)

    def ambito(self, periodo):
        # Igual que Entregas.preparar: la URL forma parte del ámbito.
        return serializar([self.url, self.origen, periodo])

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
        for periodo in sorted(por_periodo):
            ambito = self.ambito(periodo)
            mensajes = por_periodo[periodo]
            if ambito in planificados:
                resumen["tardios_nuevos"] += self._registrar_tardios(ambito, mensajes)
            elif periodo in solicitudes or fin_de(periodo, self.unidad) + timedelta(seconds=self.gracia) <= ahora:
                self.entregas.preparar(self.url, mensajes, self.origen, periodo, True, construir_lotes)
                resumen["planificados"] += 1
                LOG.info("puente periodo=%s planificado mensajes=%d", periodo, len(mensajes))
        try:
            self._entregar(resumen)
        except SinConexion:
            resumen["sin_conexion"] = True
            LOG.warning("puente api_no_disponible reintento_en_proximo_ciclo")
        return resumen

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
            periodos = c.execute("SELECT count(*) FROM ambitos").fetchone()[0]
        return {"periodos_planificados": periodos, "entregas": entregas, "tardios": tardios}

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
                    unidad=cfg["unidad"], gracia=cfg["gracia"], latido=cfg["latido"])
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
