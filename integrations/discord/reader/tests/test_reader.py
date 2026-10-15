"""Casos sintéticos preparados; no necesitan Discord ni credenciales."""

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from discord_reader.core import Config, capture
from discord_reader.store import Inbox, CapacityError, export_jsonl


def message(**changes):
    data = dict(
        id=300, guild=SimpleNamespace(id=100), channel=SimpleNamespace(id=200),
        author=SimpleNamespace(id=400, bot=False), webhook_id=None,
        content="Mensaje ficticio: terminé mi proyecto.",
        created_at=datetime(2026, 10, 7, 12, tzinfo=timezone.utc),
        is_system=lambda: False,
    )
    data.update(changes)
    return SimpleNamespace(**data)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(100, frozenset({200}), Path("unused.sqlite3"), 10)

    def test_source_event_preserves_text_and_stable_ids(self):
        event, reason = capture(message(content="  ¡Hola!\nSegunda línea  "), self.config)
        self.assertEqual(reason, "aceptado")
        self.assertEqual(event, {
            "schema_version": "discord-source-v1", "message_id": "300",
            "guild_id": "100", "channel_id": "200", "author_id": "400",
            "created_at": "2026-10-07T12:00:00+00:00",
            "content": "  ¡Hola!\nSegunda línea  ",
        })

    def test_private_messages_and_other_servers_rejected(self):
        for guild in (None, SimpleNamespace(id=999)):
            self.assertEqual(capture(message(guild=guild), self.config),
                             (None, "servidor_no_autorizado"))

    def test_other_channels_and_child_threads_do_not_inherit_permission(self):
        for channel in (SimpleNamespace(id=201), SimpleNamespace(id=202, parent_id=200)):
            self.assertEqual(capture(message(channel=channel), self.config),
                             (None, "canal_no_autorizado"))

    def test_bots_webhooks_and_system_events_rejected(self):
        for changes in (
            {"author": SimpleNamespace(id=400, bot=True)},
            {"webhook_id": 500}, {"is_system": lambda: True},
        ):
            self.assertIsNone(capture(message(**changes), self.config)[0])

    def test_empty_or_attachment_only_messages_rejected(self):
        for content in ("", " \n\t"):
            self.assertEqual(capture(message(content=content), self.config), (None, "sin_texto"))

    def test_filter_runs_before_content_access(self):
        class Forbidden:
            guild = SimpleNamespace(id=999)

            @property
            def content(self):
                raise AssertionError("No debe inspeccionar contenido no autorizado")
        self.assertEqual(capture(Forbidden(), self.config), (None, "servidor_no_autorizado"))

    def test_configuration_rejects_empty_allowlist_and_invalid_ids(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for data in (
                {"guild_id": "100", "channel_ids": []},
                {"guild_id": "100", "channel_ids": ["*"]},
                {"guild_id": "0", "channel_ids": ["200"]},
                {"guild_id": "100", "channel_ids": ["200"], "max_messages": True},
            ):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    Config.load(path)

    def test_database_path_is_relative_to_configuration(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"guild_id":"100","channel_ids":["200"]}', encoding="utf-8")
            self.assertEqual(Config.load(path).database, (Path(directory) / "data/discord.sqlite3").resolve())

    def test_duplicates_survive_restart_and_export_preserves_unicode(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            event, _ = capture(message(), self.config)
            self.assertTrue(Inbox(database, 10).save(event))
            self.assertFalse(Inbox(database, 10).save(event))
            destination = Path(directory) / "messages.jsonl"
            self.assertEqual(export_jsonl(database, destination), 1)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), event)
            with self.assertRaises(FileExistsError):
                export_jsonl(database, destination)

    def test_capacity_stops_new_records_without_erasing_previous_ones(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            inbox = Inbox(database, 1)
            event, _ = capture(message(), self.config)
            inbox.save(event)
            self.assertFalse(inbox.save(event))
            other, _ = capture(message(id=301), self.config)
            with self.assertRaises(CapacityError):
                inbox.save(other)
            self.assertEqual(export_jsonl(database, Path(directory) / "out.jsonl"), 1)


if __name__ == "__main__":
    unittest.main()
