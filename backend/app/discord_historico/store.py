"""Persistencia PostgreSQL de las importaciones (psycopg síncrono, como la cola del worker).

Garantías:
- Una importación activa por canal (índice único parcial) y clave de idempotencia opcional.
- Reserva con token y vencimiento: un runner caído libera el trabajo al vencer y otro lo retoma
  desde `cursor_before` (reanudación sin pérdida).
- Cada página se guarda en UNA transacción junto con el cursor: o entra la página completa y el
  cursor avanza, o no entra nada. Repetir una página no duplica (claves primarias + ON CONFLICT).
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ACTIVOS = ("pendiente", "ejecutando")
FINALES = ("completada", "completada_con_limite", "cancelada", "error")
CAMPOS_PUBLICOS = ("id", "guild_id", "canal_id", "canal_nombre", "canal_tipo", "desde_utc", "hasta_utc", "zona",
                   "desde_local", "hasta_local", "max_mensajes", "solicitante", "estado", "cancelacion_solicitada",
                   "paginas", "examinados", "en_rango", "insertados", "existentes", "existentes_en_vivo", "editados",
                   "descartados", "hilos_detectados", "limite_alcanzado", "motivos_parcial", "alcance", "error", "intentos",
                   "creado", "iniciado", "finalizado", "ultimo_avance", "solicitud", "huella_solicitud")
# Estado de IA de un mensaje según la ÚNICA evidencia que vincula mensaje y procesamiento en este
# modelo: trabajos_worker.entrada.interacciones[].id = id_mensaje (la misma relación que usa
# services/ambito.py). 'terminado' = el lote que contenía el mensaje se procesó con éxito. Existir en
# `mensajes` NO es evidencia: la ingesta guarda el mensaje al encolar, antes de procesarlo.
SQL_ESTADO_IA = """(SELECT CASE
        WHEN bool_or(t.estado = 'terminado') THEN 'procesado'
        WHEN bool_or(t.estado IN ('recibido', 'procesando')) THEN 'pendiente'
        WHEN bool_or(t.estado = 'error') THEN 'fallido'
        ELSE 'sin_evidencia' END
    FROM trabajos_worker t WHERE t.entrada -> 'interacciones' @> jsonb_build_array(jsonb_build_object('id', {col})))"""
SQL_TRABAJO_IA = """(SELECT t.id FROM trabajos_worker t
    WHERE t.entrada -> 'interacciones' @> jsonb_build_array(jsonb_build_object('id', {col}))
    ORDER BY (t.estado = 'terminado') DESC, (t.estado IN ('recibido', 'procesando')) DESC, t.actualizado DESC
    LIMIT 1)"""
CAMPOS_HUELLA = ("canal_id", "desde", "hasta", "zona", "max_mensajes")


def huella_solicitud(canal_id, desde, hasta, zona, max_mensajes):
    """Parámetros SOLICITADOS (no los efectivos) y su huella estable.

    Incluye canal, desde, hasta y zona tal como se enviaron (sin espacios exteriores) y
    max_mensajes tal como se envió (None si se omitió). No incluye `confirmar_alcance` (es
    consentimiento, no alcance) ni la hora de la solicitud: por eso repetir la misma petición con
    un rango que termina «hoy» produce la misma huella aunque el corte efectivo ya sea otro.
    """
    solicitud = {"canal_id": canal_id.strip(), "desde": desde.strip(), "hasta": hasta.strip(),
                 "zona": zona.strip(), "max_mensajes": max_mensajes}
    canonico = json.dumps([solicitud[k] for k in CAMPOS_HUELLA], ensure_ascii=False, separators=(",", ":"))
    return solicitud, "v1-" + sha256(canonico.encode()).hexdigest()


class Conflicto(Exception):
    def __init__(self, codigo, existente=None):
        super().__init__(codigo)
        self.codigo, self.existente = codigo, existente


class Store:
    def __init__(self, url, lease=60, max_intentos=5):
        self.url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self.lease, self.max_intentos = lease, max_intentos

    def conectar(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=5)

    def _publico(self, fila):
        return None if fila is None else {k: fila[k] for k in CAMPOS_PUBLICOS}

    # --- API ---
    def por_clave(self, clave_idempotencia, huella):
        """Importación ya creada con esa clave (o None). Huella distinta → Conflicto."""
        with self.conectar() as c:
            return self._por_clave(c, clave_idempotencia, huella)

    def _por_clave(self, c, clave, huella):
        previa = c.execute("SELECT * FROM discord_importaciones WHERE clave_idempotencia=%s", (clave,)).fetchone()
        if previa is None:
            return None
        if previa["huella_solicitud"] != huella:   # incluye filas anteriores a la huella (NULL)
            raise Conflicto("clave_idempotencia_reutilizada", self._publico(previa))
        return self._publico(previa)

    def crear(self, *, guild_id, canal_id, canal_nombre, canal_tipo, rango, max_mensajes, solicitante,
              clave_idempotencia=None, solicitud=None, huella=None):
        """(importacion, nueva). Misma clave y huella → la importación original con su rango congelado.

        Con clave, la clave manda sobre «otra importación activa del canal»: dos solicitudes simultáneas
        con la misma clave convergen en la misma importación aunque una vea a la otra como activa.
        """
        with self.conectar() as c:
            if clave_idempotencia:
                previa = self._por_clave(c, clave_idempotencia, huella)
                if previa:
                    return previa, False
            activa = c.execute("SELECT * FROM discord_importaciones WHERE canal_id=%s AND estado IN ('pendiente','ejecutando')",
                               (canal_id,)).fetchone()
            if activa:
                if clave_idempotencia and activa["clave_idempotencia"] == clave_idempotencia:
                    return self._por_clave(c, clave_idempotencia, huella), False   # gemela confirmada entre lecturas
                raise Conflicto("importacion_activa_en_el_canal", self._publico(activa))
            identificador = "imp-" + uuid4().hex
            try:
                fila = c.execute("""INSERT INTO discord_importaciones
                    (id, guild_id, canal_id, canal_nombre, canal_tipo, desde_utc, hasta_utc, zona, desde_local,
                     hasta_local, max_mensajes, solicitante, clave_idempotencia, solicitud, huella_solicitud)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (identificador, guild_id, canal_id, canal_nombre, canal_tipo, rango.inicio_utc, rango.fin_utc,
                     rango.zona, rango.inicio_local, rango.fin_local, max_mensajes, solicitante,
                     clave_idempotencia, Jsonb(solicitud) if solicitud else None, huella)).fetchone()
            except psycopg.errors.UniqueViolation:
                c.rollback()
                # ¿La ganó una solicitud gemela (misma clave)? Entonces es la misma importación.
                if clave_idempotencia:
                    previa = self._por_clave(c, clave_idempotencia, huella)
                    if previa:
                        return previa, False
                activa = c.execute("SELECT * FROM discord_importaciones WHERE canal_id=%s AND estado IN ('pendiente','ejecutando')",
                                   (canal_id,)).fetchone()
                raise Conflicto("importacion_activa_en_el_canal", self._publico(activa)) from None
            return self._publico(fila), True

    def obtener(self, identificador):
        with self.conectar() as c:
            return self._publico(c.execute("SELECT * FROM discord_importaciones WHERE id=%s", (identificador,)).fetchone())

    def listar(self, limite=20):
        with self.conectar() as c:
            return [self._publico(f) for f in c.execute(
                "SELECT * FROM discord_importaciones ORDER BY creado DESC LIMIT %s", (limite,))]

    def solicitar_cancelacion(self, identificador):
        """Pendiente → cancelada al instante; ejecutando → el runner se detiene entre páginas."""
        with self.conectar() as c:
            fila = c.execute("""UPDATE discord_importaciones SET estado='cancelada', finalizado=clock_timestamp(),
                cancelacion_solicitada=true WHERE id=%s AND estado='pendiente' RETURNING *""", (identificador,)).fetchone()
            if fila is None:
                fila = c.execute("""UPDATE discord_importaciones SET cancelacion_solicitada=true
                    WHERE id=%s AND estado='ejecutando' RETURNING *""", (identificador,)).fetchone()
            if fila is None:
                fila = c.execute("SELECT * FROM discord_importaciones WHERE id=%s", (identificador,)).fetchone()
            return self._publico(fila)

    def reanudar(self, identificador):
        """Solo errores reanudables (límite de Discord, red); conserva el cursor y los contadores."""
        with self.conectar() as c:
            fila = c.execute("SELECT * FROM discord_importaciones WHERE id=%s FOR UPDATE", (identificador,)).fetchone()
            if fila is None:
                return None
            if fila["estado"] != "error" or not (fila["error"] or {}).get("reanudable"):
                raise Conflicto("no_reanudable", self._publico(fila))
            otra = c.execute("""SELECT 1 FROM discord_importaciones WHERE canal_id=%s AND id<>%s
                AND estado IN ('pendiente','ejecutando')""", (fila["canal_id"], identificador)).fetchone()
            if otra:
                raise Conflicto("importacion_activa_en_el_canal", self._publico(fila))
            fila = c.execute("""UPDATE discord_importaciones SET estado='pendiente', error=NULL, finalizado=NULL,
                cancelacion_solicitada=false, intentos=0 WHERE id=%s RETURNING *""", (identificador,)).fetchone()
            return self._publico(fila)

    def mensajes(self, identificador, limite=50, desplazamiento=0):
        """Mensajes de la importación. `estado_ia` se calcula AHORA (no queda obsoleto si el mensaje se
        procesó después por otra vía); `estado_ia_captura` es lo observado al importarlo."""
        with self.conectar() as c:
            filas = c.execute(f"""SELECT m.id_mensaje, m.message_id, m.autor_id, m.fecha, m.editado_en, m.capturado_en,
                    m.texto, m.contenido_disponible, m.tipo_discord, m.adjuntos, m.referencia, m.texto_ultima_version,
                    m.en_ingesta_vivo, m.estado_ia_captura, {SQL_ESTADO_IA.format(col="m.id_mensaje")} estado_ia,
                    {SQL_TRABAJO_IA.format(col="m.id_mensaje")} estado_ia_trabajo, r.resultado
                FROM discord_importacion_mensajes r JOIN discord_mensajes_historicos m USING (id_mensaje)
                WHERE r.importacion_id=%s ORDER BY m.fecha DESC, m.id_mensaje LIMIT %s OFFSET %s""",
                (identificador, limite, desplazamiento)).fetchall()
            for f in filas:
                f["procesado_ia"] = f["estado_ia"] == "procesado"
            total = c.execute("SELECT count(*) n FROM discord_importacion_mensajes WHERE importacion_id=%s",
                              (identificador,)).fetchone()["n"]
            return filas, total

    # --- Runner ---
    def reservar(self):
        """Toma la importación pendiente más antigua (o una 'ejecutando' cuya reserva venció)."""
        with self.conectar() as c:
            fila = c.execute("""SELECT id FROM discord_importaciones
                WHERE estado='pendiente' OR (estado='ejecutando' AND vence <= clock_timestamp())
                ORDER BY creado FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
            if fila is None:
                return None
            token = uuid4().hex
            fila = c.execute("""UPDATE discord_importaciones SET estado='ejecutando', token_ejecucion=%s,
                vence=clock_timestamp() + make_interval(secs => %s), intentos=intentos+1,
                iniciado=coalesce(iniciado, clock_timestamp()) WHERE id=%s RETURNING *""",
                (token, self.lease, fila["id"])).fetchone()
            if fila["intentos"] > self.max_intentos:
                c.execute("""UPDATE discord_importaciones SET estado='error', token_ejecucion=NULL, vence=NULL,
                    finalizado=clock_timestamp(), error=%s WHERE id=%s""",
                    (Jsonb({"codigo": "reintentos_agotados", "reanudable": True}), fila["id"]))
                return None
            return dict(fila)

    def estado_control(self, trabajo):
        """(sigue_siendo_mio, cancelacion_solicitada) y renueva la reserva."""
        with self.conectar() as c:
            fila = c.execute("""UPDATE discord_importaciones SET vence=clock_timestamp() + make_interval(secs => %s)
                WHERE id=%s AND token_ejecucion=%s AND estado='ejecutando' RETURNING cancelacion_solicitada""",
                (self.lease, trabajo["id"], trabajo["token_ejecucion"])).fetchone()
            return (fila is not None, bool(fila and fila["cancelacion_solicitada"]))

    def guardar_pagina(self, trabajo, mensajes, descartes, cursor, examinados, hilos, en_rango):
        """Guarda la página y avanza el cursor en una transacción. Devuelve los contadores sumados."""
        cont = {"insertados": 0, "existentes": 0, "existentes_en_vivo": 0, "editados": 0}
        with self.conectar() as c:
            propio = c.execute("""SELECT id FROM discord_importaciones WHERE id=%s AND token_ejecucion=%s
                AND estado='ejecutando' FOR UPDATE""", (trabajo["id"], trabajo["token_ejecucion"])).fetchone()
            if propio is None:
                return None
            for m in mensajes:
                # «Existente en la ingesta en vivo» (solo almacenado) y «estado de IA» son hechos distintos.
                obs = c.execute(f"""SELECT EXISTS (SELECT 1 FROM mensajes WHERE id_mensaje=%(id)s) en_vivo,
                    {SQL_ESTADO_IA.format(col="%(id)s::text")} estado_ia, {SQL_TRABAJO_IA.format(col="%(id)s::text")} trabajo""",
                    {"id": m["id_mensaje"]}).fetchone()
                en_vivo = obs["en_vivo"]
                previo = c.execute("""SELECT texto, coalesce(texto_ultima_version, texto) actual, editado_en
                    FROM discord_mensajes_historicos WHERE id_mensaje=%s""", (m["id_mensaje"],)).fetchone()
                if previo is None:
                    c.execute("""INSERT INTO discord_mensajes_historicos
                        (id_mensaje, message_id, guild_id, canal_id, autor_id, fecha, editado_en, texto,
                         contenido_disponible, tipo_discord, adjuntos, referencia, importacion_inicial,
                         en_ingesta_vivo, estado_ia_captura, estado_ia_trabajo, procesado_ia)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (m["id_mensaje"], m["message_id"], trabajo["guild_id"], trabajo["canal_id"], m["autor_id"],
                         m["fecha"], m["editado_en"], m["texto"], m["contenido_disponible"], m["tipo_discord"],
                         Jsonb(m["adjuntos"]), m["referencia"], trabajo["id"], en_vivo, obs["estado_ia"],
                         obs["trabajo"], obs["estado_ia"] == "procesado"))
                    resultado = "existente_en_vivo" if en_vivo else "insertado"
                elif m["texto"] != previo["actual"] and m["editado_en"] is not None:
                    # Edición posterior: se conserva la primera captura como fuente y se registra la versión vista.
                    c.execute("""UPDATE discord_mensajes_historicos SET texto_ultima_version=%s, editado_en=%s,
                        edicion_detectada_en=clock_timestamp() WHERE id_mensaje=%s""",
                        (m["texto"], m["editado_en"], m["id_mensaje"]))
                    resultado = "editado"
                else:
                    resultado = "existente_en_vivo" if en_vivo else "existente"
                nuevo = c.execute("""INSERT INTO discord_importacion_mensajes (importacion_id, id_mensaje, resultado)
                    VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""", (trabajo["id"], m["id_mensaje"], resultado)).rowcount
                if nuevo:
                    clave = {"insertado": "insertados", "existente": "existentes",
                             "existente_en_vivo": "existentes_en_vivo", "editado": "editados"}[resultado]
                    cont[clave] += 1
            fila = c.execute("""UPDATE discord_importaciones SET cursor_before=%s, paginas=paginas+1,
                examinados=examinados+%s, en_rango=en_rango+%s, insertados=insertados+%s, existentes=existentes+%s,
                existentes_en_vivo=existentes_en_vivo+%s, editados=editados+%s, hilos_detectados=hilos_detectados+%s,
                descartados=(SELECT coalesce(jsonb_object_agg(k, v), '{}'::jsonb) FROM (
                    SELECT k, sum(v)::int v FROM (
                        SELECT key k, value::int v FROM jsonb_each_text(descartados)
                        UNION ALL SELECT key, value::int FROM jsonb_each_text(%s::jsonb)) x GROUP BY k) y),
                ultimo_avance=clock_timestamp(), vence=clock_timestamp() + make_interval(secs => %s)
                WHERE id=%s RETURNING *""",
                (cursor, examinados, en_rango, cont["insertados"], cont["existentes"], cont["existentes_en_vivo"],
                 cont["editados"], hilos, json.dumps(descartes), self.lease, trabajo["id"])).fetchone()
            return dict(fila)

    def finalizar(self, trabajo, estado, error=None, limite=False):
        """Cierra la importación y devuelve el estado guardado (None si ya no era de este runner).

        Un resultado sin errores que dejó fuera hilos detectados NO se declara completo: queda
        «completada_con_limite» con el motivo «hilos_excluidos» (alcance v1 = canal sin hilos).
        """
        with self.conectar() as c:
            fila = c.execute("""UPDATE discord_importaciones SET
                estado = CASE WHEN %(e)s IN ('completada', 'completada_con_limite') AND hilos_detectados > 0
                              THEN 'completada_con_limite' ELSE %(e)s END,
                motivos_parcial = CASE WHEN %(limite)s THEN '["max_mensajes"]'::jsonb ELSE '[]'::jsonb END
                    || CASE WHEN %(e)s IN ('completada', 'completada_con_limite') AND hilos_detectados > 0
                            THEN '["hilos_excluidos"]'::jsonb ELSE '[]'::jsonb END,
                error=%(error)s, limite_alcanzado=%(limite)s, token_ejecucion=NULL, vence=NULL,
                finalizado=clock_timestamp(), ultimo_avance=clock_timestamp()
                WHERE id=%(id)s AND token_ejecucion=%(token)s AND estado='ejecutando' RETURNING estado""",
                {"e": estado, "error": Jsonb(error) if error else None, "limite": limite, "id": trabajo["id"],
                 "token": trabajo["token_ejecucion"]}).fetchone()
            return fila["estado"] if fila else None
