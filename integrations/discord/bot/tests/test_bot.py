import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from bot_discord.contracts import Config, capture, validate_source, validate_decision, delivery
from bot_discord.discord_client import create_client, check_channel, DiscordTransport
from bot_discord.engine import Engine
from bot_discord.runtime import instance_lock, load_processor
from bot_discord.store import Store, CapacityError
from tests.helpers import config, source, decision, channels, message


class ContractTests(unittest.TestCase):
    def test_reader_filters_before_processing(self):
        c = channels()[200]
        cfg = config(Path("unused"))
        for edits in ({"guild": None}, {"guild": NS(id=999)}, {"channel": NS(id=999)},
                      {"author": NS(bot=True)}, {"webhook_id": 50},
                      {"is_system": lambda: True}, {"content": "  "}):
            with self.subTest(edits=edits):
                self.assertIsNone(capture(message(c, **edits), cfg))
        self.assertEqual(capture(message(c), cfg), source())

    def test_reject_invalid_decisions_before_send(self):
        for edits in ({"message_id": "601"}, {"es_bloqueo": "false"}, {"destination": "999"},
                      {"respuesta": "😀" * 951}, {"tema": ""}, {"alerta": "incorrecta"}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                validate_decision({**decision(), **edits}, source())

    def test_block_never_public_even_if_question_or_achievement(self):
        d = {**decision(kind="bloqueo"), "es_duda": True, "es_logro": True}
        plan = delivery(source(), d, config(Path("unused")))
        self.assertEqual(plan["channel_id"], 300)
        self.assertEqual(plan["kind"], "internal")
        with self.assertRaises(ValueError):
            delivery(source(), {**d, "respuesta": "No debe salir"}, config(Path("unused")))

    def test_testimony_and_other_are_recorded_without_publication(self):
        for kind in ("logro", "otro"):
            self.assertIsNone(delivery(source(), decision(kind=kind), config(Path("unused"))))

    def test_source_validation(self):
        for edits in ({"guild_id": "999"}, {"channel_id": "300"}, {"message_id": "0600"},
                      {"created_at": "2026-10-08"}, {"content": ""}, {"schema_version": "v2"}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                validate_source({**source(), **edits}, config(Path("unused")))

    def test_config_rejects_public_internal_and_bad_ids(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / "config.example.json").read_text())
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "config.json"
            for edits in ({"internal_channel_id": data["channel_ids"][0]}, {"channel_ids": []},
                          {"internal_role_ids": [data["guild_id"]]}, {"max_records": True},
                          {"processor_timeout": 0}, {"guild_id": 100}):
                file.write_text(json.dumps({**data, **edits}))
                with self.subTest(edits=edits), self.assertRaises(ValueError):
                    Config.load(file)
            file.write_text(json.dumps(data))
            self.assertEqual(Config.load(file).database, Path(tmp) / "data/bot.sqlite3")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "bot.sqlite3"
        self.store = Store(self.path, 2)

    def test_atomic_duplicate_under_concurrency_and_after_reopen(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(lambda _: self.store.enqueue(source()), range(20))), 1)
        self.assertFalse(Store(self.path).enqueue(source()))

    def test_conflicting_id_and_capacity_preserve_old_records(self):
        self.store.enqueue(source())
        with self.assertRaises(ValueError):
            self.store.enqueue({**source(), "content": "otro"})
        self.store.enqueue(source("601"))
        with self.assertRaises(CapacityError):
            self.store.enqueue(source("602"))
        self.assertEqual(self.store.summary(), {"queued": 2})

    def test_recovery_does_not_resend_possible_delivery(self):
        self.store.enqueue(source())
        self.store.claim()
        self.store.transition("100:600", "processing", "sending")
        self.store.recover_interrupted()
        self.assertEqual(self.store.get("100:600")["status"], "uncertain")
        self.assertIsNone(self.store.claim())
        with self.assertRaises(ValueError):
            self.store.retry("100:600")

    def test_recovery_before_send_is_safe(self):
        self.store.enqueue(source())
        self.store.claim()
        self.store.recover_interrupted()
        self.assertEqual(self.store.get("100:600")["status"], "queued")
        self.store.claim()
        self.store.transition("100:600", "processing", "ready", decision=decision())
        self.store.claim()
        self.store.recover_interrupted()
        self.assertEqual(self.store.get("100:600")["status"], "ready")

    def test_second_instance_cannot_acquire_same_database(self):
        with instance_lock(self.path):
            with self.assertRaises(OSError):
                with instance_lock(self.path):
                    self.fail("Dos instancias activas")
        with instance_lock(self.path):
            pass


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = config(Path(self.tmp.name) / "bot.sqlite3")
        self.store = Store(self.cfg.database)
        self.processor = AsyncMock(return_value=decision())
        self.transport = NS(prepare=AsyncMock(return_value=object()), send=AsyncMock(return_value="800"))
        self.engine = Engine(self.cfg, self.store, self.processor, self.transport)

    async def drain(self):
        while await self.engine.step():
            pass

    async def test_question_sent_once_after_restart(self):
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "sent")
        self.assertEqual(self.store.get("100:600")["receipt"], "800")
        engine2 = Engine(self.cfg, Store(self.cfg.database), self.processor, self.transport)
        self.assertFalse(await engine2.submit(source()))
        self.assertFalse(await engine2.step())
        self.transport.send.assert_awaited_once()

    async def test_testimony_is_persisted_without_send(self):
        self.processor.return_value = decision(kind="logro")
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "recorded")
        self.assertTrue(json.loads(self.store.get("100:600")["decision"])["es_logro"])
        self.transport.send.assert_not_awaited()

    async def test_timeout_or_invalid_logic_can_be_retried_explicitly(self):
        async def slow(event):
            await asyncio.sleep(10)
        self.processor.side_effect = slow
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "failed_processing")
        self.transport.send.assert_not_awaited()
        self.processor.side_effect = None
        self.store.retry("100:600")
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "sent")

    async def test_processor_exception_does_not_leak_and_next_message_runs(self):
        self.processor.side_effect = [RuntimeError("SECRET"), decision("601")]
        await self.engine.submit(source())
        await self.engine.submit(source("601"))
        await self.drain()
        self.assertNotIn("SECRET", str(self.store.get("100:600")))
        self.assertEqual(self.store.get("100:601")["status"], "sent")

    async def test_processor_cannot_mutate_source_or_change_destination(self):
        async def mutate(event):
            event["channel_id"] = "999"
            return decision()
        self.processor.side_effect = mutate
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.transport.prepare.call_args.args[0]["channel_id"], 200)

    async def test_invalid_decision_never_reaches_transport(self):
        self.processor.return_value = {**decision(), "channel_id": "999"}
        await self.engine.submit(source())
        await self.drain()
        self.transport.prepare.assert_not_awaited()
        self.assertEqual(self.store.get("100:600")["status"], "failed_processing")

    async def test_permissions_failure_retry_does_not_repeat_processing(self):
        self.transport.prepare.side_effect = ValueError("canal privado no verificado")
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "blocked_delivery")
        self.transport.send.assert_not_awaited()
        self.transport.prepare.side_effect = None
        self.store.retry("100:600")
        await self.drain()
        self.processor.assert_awaited_once()
        self.transport.send.assert_awaited_once()

    async def test_network_failure_after_send_is_uncertain_not_retried(self):
        self.transport.send.side_effect = TimeoutError("SECRET")
        await self.engine.submit(source())
        await self.drain()
        self.assertEqual(self.store.get("100:600")["status"], "uncertain")
        self.store.recover_interrupted()
        self.assertFalse(await self.engine.step())
        self.transport.send.assert_awaited_once()

    async def test_ready_decision_survives_restart(self):
        await self.engine.submit(source())
        await self.engine.step()
        self.assertEqual(self.store.get("100:600")["status"], "ready")
        engine2 = Engine(self.cfg, Store(self.cfg.database), self.processor, self.transport)
        await engine2.step()
        self.processor.assert_awaited_once()
        self.transport.send.assert_awaited_once()

    async def test_cancel_during_send_is_not_automatically_retried(self):
        reached = asyncio.Event()
        async def pending(*args):
            reached.set()
            await asyncio.sleep(30)
        self.transport.send.side_effect = pending
        await self.engine.submit(source())
        await self.engine.step()
        task = asyncio.create_task(self.engine.step())
        await asyncio.wait_for(reached.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.store.get("100:600")["status"], "sending")
        self.store.recover_interrupted()
        self.assertEqual(self.store.get("100:600")["status"], "uncertain")
        self.assertFalse(await self.engine.step())


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = config(Path(self.tmp.name) / "bot.sqlite3")
        self.client = create_client(self.cfg, AsyncMock(return_value=decision()))
        self.channels = channels()
        self.client.fetch_channel = AsyncMock(side_effect=lambda cid: self.channels[cid])
        # Controlamos manualmente el consumidor para eliminar carreras en los tests.
        self.client.consume = AsyncMock()
        self.stream = io.StringIO()
        self.output = redirect_stdout(self.stream)
        self.output.__enter__()
        self.network = patch.object(discord.Client, "start", side_effect=AssertionError("sin red"))
        self.network.start()

    async def asyncTearDown(self):
        await self.client.close()
        self.network.stop()
        self.output.__exit__(None, None, None)
        self.tmp.cleanup()

    async def drain(self):
        while await self.client.engine.step():
            pass

    async def test_full_capture_to_reply_uses_reference_without_mentions(self):
        await self.client.on_ready()
        await self.client.on_message(message(self.channels[200]))
        await self.client.on_message(message(self.channels[200]))
        await self.drain()
        send = self.channels[200].send
        send.assert_awaited_once()
        kw = send.call_args.kwargs
        self.assertEqual(kw["reference"].message_id, 600)
        self.assertFalse(kw["mention_author"])
        self.assertEqual(kw["allowed_mentions"].to_dict(), {"parse": []})
        self.assertTrue(kw["suppress_embeds"])
        self.channels[300].send.assert_not_awaited()
        self.assertNotIn("Mensaje ficticio", self.stream.getvalue())

    async def test_block_sends_only_to_private_channel(self):
        self.client.engine.processor.return_value = decision(kind="bloqueo")
        await self.client.on_ready()
        await self.client.on_message(message(self.channels[200]))
        await self.drain()
        self.channels[200].send.assert_not_awaited()
        self.channels[300].send.assert_awaited_once()
        self.assertIn("/100/200/600", self.channels[300].send.call_args.args[0])
        self.assertNotIn("reference", self.channels[300].send.call_args.kwargs)

    async def test_bot_webhook_dm_thread_and_internal_channel_are_ignored(self):
        await self.client.on_ready()
        for msg in [message(self.channels[200], author=NS(id=900, bot=True)),
                    message(self.channels[200], webhook_id=10),
                    message(self.channels[200], guild=None), message(self.channels[300]),
                    message(self.channels[200], channel=Mock(spec=discord.Thread))]:
            await self.client.on_message(msg)
        self.assertEqual(self.client.store.summary(), {})

    async def test_disconnect_blocks_and_resume_rechecks(self):
        await self.client.on_message(message(self.channels[200]))
        self.assertEqual(self.client.store.summary(), {})
        await self.client.on_ready()
        await self.client.on_disconnect()
        self.assertFalse(self.client.channels_verified)
        await self.client.on_resumed()
        self.assertTrue(self.client.channels_verified)
        self.assertEqual(self.client.fetch_channel.await_count, 4)

    async def test_public_alert_destination_stops_startup(self):
        self.channels[300].permissions_for.side_effect = lambda _: NS(view_channel=True, send_messages=True)
        await self.client.on_ready()
        self.assertTrue(self.client.failed)
        self.assertFalse(self.client.channels_verified)

    async def test_revoked_send_permission_does_not_send(self):
        await self.client.on_ready()
        await self.client.on_message(message(self.channels[200]))
        self.channels[200].permissions_for.side_effect = lambda _: NS(view_channel=True, send_messages=False)
        await self.drain()
        self.channels[200].send.assert_not_awaited()
        self.assertEqual(self.client.store.get("100:600")["status"], "blocked_delivery")

    async def test_foreign_role_or_member_exposure_is_rejected(self):
        c = self.channels[300]
        c.guild.roles.append(NS(id=999, tags=None))
        original = c.permissions_for.side_effect
        c.permissions_for.side_effect = lambda target: NS(view_channel=True, administrator=False) if target.id == 999 else original(target)
        with self.assertRaises(ValueError):
            check_channel(c, self.cfg, True)
        c.permissions_for.side_effect = original
        member = Mock(spec=discord.Member)
        member.id = 888
        c.overwrites = {member: discord.PermissionOverwrite(view_channel=True)}
        with self.assertRaises(ValueError):
            check_channel(c, self.cfg, True)

    async def test_minimal_intents(self):
        self.assertTrue(self.client.intents.guild_messages)
        self.assertTrue(self.client.intents.message_content)
        self.assertFalse(self.client.intents.members)
        self.assertFalse(self.client.intents.presences)
        self.assertFalse(self.client.intents.dm_messages)

    async def test_unknown_member_overwrite_is_not_hidden_by_missing_cache(self):
        c = self.channels[300]
        for kind in (discord.User, discord.Role):
            with self.subTest(kind=kind):
                c.overwrites = {discord.Object(id=888, type=kind): discord.PermissionOverwrite(view_channel=True)}
                with self.assertRaises(ValueError):
                    check_channel(c, self.cfg, True)
        c.overwrites = {discord.Object(id=888, type=discord.User): discord.PermissionOverwrite(view_channel=True)}
        check_channel(c, replace(self.cfg, internal_user_ids=frozenset({888})), True)

    async def test_real_background_consumer_drains_and_shuts_down(self):
        await self.client.close()
        self.client = create_client(self.cfg, AsyncMock(return_value=decision()))
        self.client.fetch_channel = AsyncMock(side_effect=lambda cid: self.channels[cid])
        await self.client.on_ready()
        await self.client.on_message(message(self.channels[200]))
        async def wait_sent():
            while self.client.store.get("100:600")["status"] != "sent":
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait_sent(), 3)
        self.channels[200].send.assert_awaited_once()
        await self.client.close()
        self.assertTrue(self.client.runner.done())
