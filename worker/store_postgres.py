"""Adaptador de referencia local para acordar con Fredy.

Reserva atómica, renovación y token por intento. Entrega al menos una vez;
persistencia de resultados y activos en una sola transacción.
"""
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json
from copy import deepcopy

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker.core import Trabajo
from pipelines.communitylab.fechas import fecha_utc


class ConflictoIdempotencia(ValueError):
    pass


class ConflictoMensaje(ValueError):
    """Un ID de mensaje ya guardado llega con otro contenido (autor, fecha, canal, tipo o texto)."""

    def __init__(self, id_mensaje):
        super().__init__("ID de mensaje existente con contenido diferente")
        self.id_mensaje = id_mensaje


def canonico(entrada):
    copia = deepcopy(entrada)
    for mensaje in copia["interacciones"]:
        mensaje["fecha"] = fecha_utc(mensaje["fecha"])
    return json.dumps(copia, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

# Mismos máximos que el contrato de lectura; se validan también en llamadas directas a la cola.
LIMITES = {"autor": 150, "canal": 50, "tipo": 50}
TIPO_POR_DEFECTO = "sin_clasificar"


def validar_limites(interaccion):
    for campo, maximo in LIMITES.items():
        valor = interaccion.get(campo)
        if valor is not None and len(str(valor)) > maximo:
            raise ValueError(f"El campo {campo} supera {maximo} caracteres")


class ColaPostgres:
    def __init__(self, url, lease=30, max_intentos=3):
        if lease < 2 or max_intentos < 1:
            raise ValueError("Configuración inválida de reserva")
        self.url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self.lease, self.max_intentos = lease, max_intentos

    def conectar(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=5)

    def inicializar(self):
        with self.conectar() as c:
            c.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

    def encolar(self, entrada, clave_idempotencia=None):
        return self.encolar_detalle(entrada, clave_idempotencia)[0]

    def encolar_detalle(self, entrada, clave_idempotencia=None):
        """(id, nuevo): nuevo=False cuando la misma clave y el mismo contenido reutilizan un trabajo."""
        from pipelines.communitylab.grafo import validar_lote
        entrada = validar_lote(entrada)
        if not entrada["interacciones"]:
            raise ValueError("El lote debe contener interacciones")
        if len(entrada["interacciones"]) > 500:
            raise ValueError("El máximo por trabajo es 500 interacciones")
        for m in entrada["interacciones"]:
            validar_limites(m)
            fecha_utc(m["fecha"])
        contenido = canonico(entrada)
        if clave_idempotencia is None:
            clave_idempotencia = "lote-v1-" + sha256(contenido.encode()).hexdigest()
        if not isinstance(clave_idempotencia, str) or not 1 <= len(clave_idempotencia) <= 128:
            raise ValueError("Clave de idempotencia inválida")
        identificador = str(uuid4())
        with self.conectar() as c:
            nuevo = c.execute("""INSERT INTO trabajos_worker (id,entrada,clave_idempotencia)
                VALUES (%s,%s,%s) ON CONFLICT (clave_idempotencia) DO NOTHING RETURNING id""",
                (identificador, Jsonb(entrada), clave_idempotencia)).fetchone()
            if nuevo is None:
                existente = c.execute("SELECT id,entrada FROM trabajos_worker WHERE clave_idempotencia=%s",
                                      (clave_idempotencia,)).fetchone()
                if canonico(existente["entrada"]) != contenido:
                    raise ConflictoIdempotencia("La clave de idempotencia ya identifica otro lote")
                return existente["id"], False
            # Datos fuente inmutables: no sobrescribir el texto de un activo curado.
            for m in entrada["interacciones"]:
                fuente = {"autor": m["autor"], "fecha": m["fecha"], "canal": m["canal"],
                          "tipo": m.get("tipo") or TIPO_POR_DEFECTO, "texto": m["texto"]}
                c.execute("""INSERT INTO mensajes
                    (id_mensaje, autor, fecha, canal, tipo, texto)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id_mensaje) DO NOTHING""",
                    (m["id"], fuente["autor"], fuente["fecha"], fuente["canal"], fuente["tipo"], fuente["texto"]))
                existente = c.execute("SELECT autor, fecha, canal, tipo, texto FROM mensajes WHERE id_mensaje=%s",
                                      (m["id"],)).fetchone()
                # Sin tipo explícito se acepta el ya guardado; con tipo distinto se rechaza.
                campos = [k for k in existente if k != "tipo" or m.get("tipo")]
                if any((fecha_utc(existente[k]) != fecha_utc(fuente[k])) if k == "fecha"
                       else existente[k] != fuente[k] for k in campos):
                    raise ConflictoMensaje(m["id"])
        return identificador, True

    def obtener(self, identificador):
        with self.conectar() as c:
            return c.execute("""SELECT id, estado, intentos, resultado, error_codigo,
                historial, creado, actualizado FROM trabajos_worker WHERE id=%s""",
                (identificador,)).fetchone()

    def reservar(self):
        with self.conectar() as c:
            c.execute("""UPDATE trabajos_worker SET
                estado=CASE WHEN intentos >= %s THEN 'error' ELSE 'recibido' END,
                error_codigo=CASE WHEN intentos >= %s THEN 'reserva_agotada' ELSE NULL END,
                historial=historial || jsonb_build_array(
                    CASE WHEN intentos >= %s THEN 'error' ELSE 'recibido' END),
                token=NULL, vence=NULL, actualizado=clock_timestamp()
                WHERE estado='procesando' AND vence <= clock_timestamp()""",
                (self.max_intentos, self.max_intentos, self.max_intentos))
            fila = c.execute("""SELECT id, entrada FROM trabajos_worker
                WHERE estado='recibido' ORDER BY creado,id
                FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
            if not fila:
                return None
            token = str(uuid4())
            c.execute("""UPDATE trabajos_worker SET estado='procesando', token=%s,
                vence=clock_timestamp() + %s * interval '1 second', intentos=intentos+1,
                historial=historial || '["procesando"]'::jsonb, actualizado=clock_timestamp()
                WHERE id=%s""", (token, self.lease, fila["id"]))
            return Trabajo(fila["id"], token, fila["entrada"])

    def renovar(self, trabajo):
        with self.conectar() as c:
            return c.execute("""UPDATE trabajos_worker SET
                vence=clock_timestamp() + %s * interval '1 second', actualizado=clock_timestamp()
                WHERE id=%s AND token=%s AND estado='procesando' AND vence>clock_timestamp()""",
                (self.lease, trabajo.id, trabajo.token)).rowcount == 1

    def fallar(self, trabajo, codigo, diagnostico=None):
        # El diagnóstico llega redactado desde el cliente de IA; se guarda para la consulta del trabajo.
        resultado = Jsonb({"diagnostico": diagnostico}) if diagnostico else None
        with self.conectar() as c:
            return c.execute("""UPDATE trabajos_worker SET estado='error', error_codigo=%s,
                resultado=%s, token=NULL, vence=NULL, historial=historial || '["error"]'::jsonb,
                actualizado=clock_timestamp()
                WHERE id=%s AND token=%s AND estado='procesando' AND vence>clock_timestamp()""",
                (codigo, resultado, trabajo.id, trabajo.token)).rowcount == 1

    def terminar(self, trabajo, resultado):
        if resultado.get("estado") != "completado_local" or resultado.get("errores"):
            raise ValueError("Resultado no exitoso")
        formatos = {"post_linkedin_x": "linkedin", "faq_tip_tecnico": "faq",
                    "community_highlights": "newsletter"}
        titulos = {"linkedin": "Logro de la comunidad", "faq": "Preguntas de la comunidad",
                   "newsletter": "Resumen de la comunidad"}
        with self.conectar() as c:
            fila = c.execute("""SELECT id FROM trabajos_worker
                WHERE id=%s AND token=%s AND estado='procesando' AND vence>clock_timestamp()
                FOR UPDATE""", (trabajo.id, trabajo.token)).fetchone()
            if not fila:
                return False
            for activo in resultado["activos_distribucion_generados"]:
                formato = formatos[activo["formato"]]
                # IDs estables por trabajo: un reintento no duplica ni pisa contenido revisado.
                id_activo = "act-" + sha256((trabajo.id + activo["id_activo"]).encode()).hexdigest()[:40]
                titulo = ("[SIMULADO] " if resultado["simulado"] else "") + titulos[formato]
                advertencias = activo.get("advertencias_fidelidad") or []
                c.execute("""INSERT INTO activos
                    (id_activo,formato,titulo,copy,estado,fuentes,version,fecha_creacion,fecha_actualizacion,
                     advertencias_fidelidad)
                    VALUES (%s,%s,%s,%s,'generado',%s,1,clock_timestamp(),clock_timestamp(),%s)
                    ON CONFLICT (id_activo) DO NOTHING""",
                    (id_activo, formato, titulo, activo["copy"], Jsonb(activo["fuentes"]), Jsonb(advertencias)))
                activo["id_activo_curaduria"] = id_activo
            # Persistencia real (PostgreSQL); "almacenamiento" del grafo describe solo la copia externa.
            resultado["persistencia"] = {"postgres": "guardado",
                                         "activos": len(resultado["activos_distribucion_generados"])}
            c.execute("""UPDATE trabajos_worker SET estado='terminado', resultado=%s,
                token=NULL, vence=NULL, error_codigo=NULL,
                historial=historial || '["terminado"]'::jsonb, actualizado=clock_timestamp()
                WHERE id=%s""", (Jsonb(resultado), trabajo.id))
        return True
