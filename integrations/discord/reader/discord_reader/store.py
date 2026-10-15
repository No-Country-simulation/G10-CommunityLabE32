"""Bandeja local durable. La clave evita duplicados incluso tras reiniciar."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3


class CapacityError(RuntimeError):
    pass


class Inbox:
    def __init__(self, path, maximum):
        self.path = Path(path)
        self.maximum = maximum
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(guild_id, message_id)
            )""")

    def save(self, event):
        # Cada llamada usa su propia conexión; es segura desde asyncio.to_thread.
        with closing(sqlite3.connect(self.path, timeout=10)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute(
                "SELECT 1 FROM messages WHERE guild_id=? AND message_id=?",
                (event["guild_id"], event["message_id"]),
            ).fetchone()
            if exists:
                return False
            if conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] >= self.maximum:
                raise CapacityError("La bandeja alcanzó su capacidad.")
            conn.execute(
                "INSERT INTO messages(guild_id,message_id,payload) VALUES (?,?,?)",
                (event["guild_id"], event["message_id"], json.dumps(event, ensure_ascii=False)),
            )
        return True


def export_jsonl(database, destination):
    """Exporta una foto consistente sin modificar la BD ni sobrescribir archivos."""
    database = Path(database).resolve()
    destination = Path(destination).resolve()
    count = 0
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
        rows = conn.execute("SELECT payload FROM messages ORDER BY sequence")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as output:
            for (payload,) in rows:
                output.write(payload + "\n")
                count += 1
    return count
