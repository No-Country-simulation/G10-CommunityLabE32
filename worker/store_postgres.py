"""Adaptador de referencia local para acordar con Fredy.

Reserva atómica, renovación y token por intento. Entrega al menos una vez;
persistencia de resultados y activos en una sola transacción.
"""
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker.core import Trabajo

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

    def encolar(self, entrada):
        from pipelines.communitylab.grafo import validar_lote
        entrada = validar_lote(entrada)
        if not entrada["interacciones"]:
            raise ValueError("El lote debe contener interacciones")
        if len(entrada["interacciones"]) > 500:
            raise ValueError("El máximo por trabajo es 500 interacciones")
        for m in entrada["interacciones"]:
            validar_limites(m)
        identificador = str(uuid4())
        with self.conectar() as c:
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
                if any(existente[k] != fuente[k] for k in campos):
                    raise ValueError("ID de mensaje existente con contenido diferente")
            c.execute("INSERT INTO trabajos_worker (id,entrada) VALUES (%s,%s)",
                      (identificador, Jsonb(entrada)))
        return identificador

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

    def fallar(self, trabajo, codigo):
        with self.conectar() as c:
            return c.execute("""UPDATE trabajos_worker SET estado='error', error_codigo=%s,
                token=NULL, vence=NULL, historial=historial || '["error"]'::jsonb,
                actualizado=clock_timestamp()
                WHERE id=%s AND token=%s AND estado='procesando' AND vence>clock_timestamp()""",
                (codigo, trabajo.id, trabajo.token)).rowcount == 1

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
                c.execute("""INSERT INTO activos
                    (id_activo,formato,titulo,copy,estado,fuentes,version,fecha_creacion,fecha_actualizacion)
                    VALUES (%s,%s,%s,%s,'generado',%s,1,clock_timestamp(),clock_timestamp())
                    ON CONFLICT (id_activo) DO NOTHING""",
                    (id_activo, formato, titulo, activo["copy"], Jsonb(activo["fuentes"])))
            c.execute("""UPDATE trabajos_worker SET estado='terminado', resultado=%s,
                token=NULL, vence=NULL, error_codigo=NULL,
                historial=historial || '["terminado"]'::jsonb, actualizado=clock_timestamp()
                WHERE id=%s""", (Jsonb(resultado), trabajo.id))
        return True
