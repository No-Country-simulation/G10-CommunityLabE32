"""Adaptador real discord.py, con transporte sustituido; nunca conecta."""
import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord_reader.__main__ import create_client
from discord_reader.core import Config
from discord_reader.store import export_jsonl
from test_reader import message


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.database = Path(self.temp.name) / "inbox.sqlite3"
        self.config = Config(100, frozenset({200}), self.database, 10)
        self.client = create_client(self.config)
        self.client.close = AsyncMock()
        self.guild = SimpleNamespace(id=100, me=object())
        self.channel = Mock(spec=discord.TextChannel)
        self.channel.id = 200
        self.channel.guild = self.guild
        self.channel.permissions_for.return_value = SimpleNamespace(view_channel=True)
        self.client.fetch_channel = AsyncMock(return_value=self.channel)
        self.stream = io.StringIO()
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(contextlib.redirect_stdout(self.stream))
        self.stack.enter_context(contextlib.redirect_stderr(self.stream))
        self.stack.enter_context(patch.object(discord.Client, "start", side_effect=AssertionError("Red prohibida")))

    async def asyncTearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def incoming(self, **changes):
        return message(guild=self.guild, channel=self.channel, **changes)

    async def test_capture_export_and_duplicate_through_client(self):
        await self.client.on_ready()
        await self.client.on_message(self.incoming())
        await self.client.on_message(self.incoming())
        out = Path(self.temp.name) / "out.jsonl"
        self.assertEqual(export_jsonl(self.database, out), 1)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["author_id"], "400")
        self.assertEqual(self.client.counters["duplicado"], 1)
        self.assertNotIn("Mensaje ficticio", self.stream.getvalue())
        self.client.fetch_channel.assert_awaited_once_with(200)

    async def test_waits_for_verification_and_rechecks_on_resume(self):
        await self.client.on_message(self.incoming())
        self.assertEqual(self.client.counters["antes_de_verificacion"], 1)
        await self.client.on_ready()
        await self.client.on_disconnect()
        self.assertFalse(self.client.channels_verified)
        await self.client.on_resumed()
        self.assertTrue(self.client.channels_verified)
        self.assertEqual(self.client.fetch_channel.await_count, 2)

    async def test_wrong_guild_stops_client(self):
        self.channel.guild = SimpleNamespace(id=999, me=object())
        await self.client.on_ready()
        self.assertTrue(self.client.failed)
        self.assertFalse(self.client.channels_verified)
        self.client.close.assert_awaited_once()

    async def test_missing_permission_stops_client(self):
        self.channel.permissions_for.return_value.view_channel = False
        await self.client.on_ready()
        self.assertTrue(self.client.failed)
        self.client.close.assert_awaited_once()

    async def test_permission_removed_after_ready_rejects_message(self):
        await self.client.on_ready()
        self.channel.permissions_for.return_value.view_channel = False
        await self.client.on_message(self.incoming())
        self.assertEqual(self.client.counters["sin_permiso_de_lectura"], 1)
        self.assertEqual(self.client.counters["guardado"], 0)

    async def test_explicit_thread_rejected(self):
        thread = Mock(spec=discord.Thread)
        thread.id = 200
        thread.guild = self.guild
        self.client.fetch_channel.return_value = thread
        await self.client.on_ready()
        self.assertTrue(self.client.failed)

    async def test_storage_failure_stops_without_disclosing_content(self):
        await self.client.on_ready()
        with patch("discord_reader.__main__.Inbox.save", side_effect=OSError("NO_MOSTRAR")):
            await self.client.on_message(self.incoming(content="TEXTO_PRIVADO"))
        self.assertTrue(self.client.failed)
        self.client.close.assert_awaited_once()
        self.assertNotIn("NO_MOSTRAR", self.stream.getvalue())
        self.assertNotIn("TEXTO_PRIVADO", self.stream.getvalue())

    async def test_unavailable_channel_fails_closed(self):
        self.client.fetch_channel.side_effect = RuntimeError("NO_MOSTRAR")
        await self.client.on_ready()
        await self.client.on_message(self.incoming())
        self.assertEqual(self.client.counters["guardado"], 0)
        self.client.close.assert_awaited_once()
        self.assertNotIn("NO_MOSTRAR", self.stream.getvalue())

    async def test_intents_do_not_enable_private_messages_or_members(self):
        self.assertTrue(self.client.intents.guild_messages)
        self.assertTrue(self.client.intents.message_content)
        self.assertFalse(self.client.intents.dm_messages)
        self.assertFalse(self.client.intents.members)
        self.assertFalse(self.client.intents.presences)
