"""Cola local durable: planificar antes de enviar, confirmar después del HTTP."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


def serializar(valor):
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Entregas:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS ambitos (id TEXT PRIMARY KEY, cierre INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS entregas (
                    clave TEXT PRIMARY KEY, ambito TEXT NOT NULL, payload TEXT NOT NULL,
                    trabajo TEXT, estado TEXT NOT NULL DEFAULT 'pendiente');
                CREATE TABLE IF NOT EXISTS fuentes (
                    ambito TEXT NOT NULL, id TEXT NOT NULL, contenido TEXT NOT NULL,
                    clave TEXT NOT NULL REFERENCES entregas(clave), PRIMARY KEY(ambito,id));
            """)

    @contextmanager
    def conexion(self):
        c = sqlite3.connect(self.ruta, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def preparar(self, url, interacciones, origen, periodo, cierre, construir_lotes):
        ambito = serializar([url.rstrip('/'), origen, periodo])
        with self.conexion() as c:
            c.execute('BEGIN IMMEDIATE')
            previo = c.execute('SELECT cierre FROM ambitos WHERE id=?', (ambito,)).fetchone()
            if previo and bool(previo['cierre']) != cierre:
                raise ValueError('No cambie --cierre dentro del mismo origen/período; use un período nuevo')
            c.execute('INSERT OR IGNORE INTO ambitos VALUES (?,?)', (ambito, int(cierre)))
            nuevos = []
            for m in sorted(interacciones, key=lambda m: m['id']):
                fila = c.execute('SELECT contenido FROM fuentes WHERE ambito=? AND id=?', (ambito, m['id'])).fetchone()
                if fila:
                    if fila['contenido'] != serializar(m):
                        raise ValueError('ID de mensaje ya registrado con contenido diferente')
                else:
                    nuevos.append(m)
            if previo and cierre and nuevos:
                raise ValueError('El período de cierre ya fue planificado; no añada mensajes a ese período')
            for lote in construir_lotes(nuevos, origen, periodo, cierre):
                payload = serializar(lote)
                clave = 'discord-v1-' + sha256((ambito + payload).encode('utf-8')).hexdigest()
                c.execute('INSERT INTO entregas (clave,ambito,payload) VALUES (?,?,?)', (clave, ambito, payload))
                for m in lote['interacciones']:
                    c.execute('INSERT INTO fuentes VALUES (?,?,?,?)', (ambito, m['id'], serializar(m), clave))
            return [dict(f) for f in c.execute('SELECT * FROM entregas WHERE ambito=? ORDER BY rowid', (ambito,))]

    def confirmar(self, clave, trabajo, estado):
        with self.conexion() as c:
            c.execute('UPDATE entregas SET trabajo=?,estado=? WHERE clave=?', (trabajo, estado, clave))
