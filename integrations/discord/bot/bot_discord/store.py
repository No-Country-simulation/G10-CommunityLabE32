"""Cola y registro durable. Nunca reenvía automáticamente un envío incierto."""
from contextlib import closing
import json
import sqlite3


class CapacityError(Exception):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Store:
    def __init__(self, path, capacity=10000):
        self.path, self.capacity = path, capacity
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as c, c:
            c.execute("""CREATE TABLE IF NOT EXISTS jobs (
                key TEXT PRIMARY KEY, source TEXT NOT NULL, status TEXT NOT NULL,
                decision TEXT, receipt TEXT, error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def enqueue(self, event):
        key = event["guild_id"] + ":" + event["message_id"]
        payload = encode(event)
        with closing(self.connect()) as c, c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT source FROM jobs WHERE key=?", (key,)).fetchone()
            if old:
                if old["source"] != payload:
                    raise ValueError("Mismo ID con otro contenido")
                return False
            if c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] >= self.capacity:
                raise CapacityError("Capacidad agotada")
            c.execute("INSERT INTO jobs(key,source,status) VALUES (?,?,'queued')", (key, payload))
            return True

    def claim(self):
        with closing(self.connect()) as c, c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE status IN ('queued','ready') ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            target = "processing" if row["status"] == "queued" else "checking"
            c.execute("UPDATE jobs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE key=?", (target,row["key"]))
            return dict(row)

    def transition(self, key, expected, target, decision=None, receipt=None, error=None):
        with closing(self.connect()) as c, c:
            changed = c.execute("""UPDATE jobs SET status=?,decision=COALESCE(?,decision),
                receipt=COALESCE(?,receipt),error=?,updated_at=CURRENT_TIMESTAMP
                WHERE key=? AND status=?""",
                (target, encode(decision) if decision is not None else None,
                 receipt, error, key, expected)).rowcount
            if changed != 1:
                raise RuntimeError("Transición inválida")

    def retry(self, key):
        # No retry de sending/uncertain: pudo haber llegado a Discord.
        with closing(self.connect()) as c, c:
            changed = c.execute("""UPDATE jobs SET status=CASE status
                WHEN 'failed_processing' THEN 'queued' ELSE 'ready' END,
                error=NULL,updated_at=CURRENT_TIMESTAMP
                WHERE key=? AND status IN ('failed_processing','blocked_delivery')""", (key,)).rowcount
            if changed != 1:
                raise ValueError("Estado no reintentable")

    def get(self, key):
        with closing(self.connect()) as c:
            row = c.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
            return dict(row) if row else None

    def summary(self):
        with closing(self.connect()) as c:
            return dict(c.execute("SELECT status,COUNT(*) FROM jobs GROUP BY status").fetchall())

    def recover_interrupted(self):
        # Solo bajo instance_lock, antes de arrancar el cliente. No había envío
        # en processing/checking; sending pudo llegar y requiere revisión humana.
        with closing(self.connect()) as c, c:
            c.execute("""UPDATE jobs SET status=CASE status
                WHEN 'processing' THEN 'queued' WHEN 'checking' THEN 'ready'
                ELSE 'uncertain' END, updated_at=CURRENT_TIMESTAMP
                WHERE status IN ('processing','checking','sending')""")
