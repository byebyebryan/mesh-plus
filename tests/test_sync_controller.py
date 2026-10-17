"""Actual minted IPC controller; fixture native source is explicitly synthetic."""

import asyncio
import gc
import socket
import unittest
from hashlib import sha256
from unittest.mock import patch

from test_sync_cache import CacheProfile
from test_sync_relay import Codec, Source

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import (
    SyncBudgets,
    control_carrier_from_ipc,
    create_sync_relay,
    serve_sync_relay,
    source_binding,
)
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import canonical, decode
from mesh_plus.transport import boottime_ms, finish_owned


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gc_enabled = gc.isenabled()
        gc.disable()
        self.profile, self.ledger = CacheProfile(), AllocationLedger()
        self.source = Source(self.profile)
        self.codec = Codec(self.profile.descriptor)
        self.binding = source_binding("fixture", "agents", self.profile.descriptor)
        self.relay = create_sync_relay(self.source, self.profile.descriptor, self.binding,
                                       native_codec=self.codec, budgets=SyncBudgets(), ledger=self.ledger)
        self.clients, self.tasks, self.carriers, self.errors = [], [], [], []

    async def asyncTearDown(self):
        try:
            for writer in self.clients:
                writer.close()
                await writer.wait_closed()
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            await self.relay.aclose()
            for carrier in self.carriers:
                await carrier.aclose()
            self.assertEqual((self.ledger.used, self.ledger.reserved, self.ledger.encoded,
                              self.ledger.encoded_reserved, self.ledger.pending_units), (0,) * 5)
            self.assertFalse(gc.isenabled())
        finally:
            if self.gc_enabled:
                gc.enable()

    async def connect(self, *, request_changes=None):
        supplied, peer = socket.socketpair()
        carrier = control_carrier_from_ipc(supplied, ledger=self.ledger)
        self.carriers.append(carrier)
        task = asyncio.create_task(serve_sync_relay(self.relay, carrier, setup_deadline_ms=boottime_ms() + 15000))
        self.tasks.append(task)
        reader, writer = await asyncio.open_connection(sock=peer)
        self.clients.append(writer)
        await self.send(writer, {"protocol": "mesh.state-sync/1", "kind": "hello", "nonce": "f" * 64})
        hello = await self.read(reader)
        self.assertEqual(hello["kind"], "hello")
        self.assertEqual(hello["nonce"], "f" * 64)
        request = {"readerEpoch": "a" * 32, "requestId": "controller-test", "catalogRevision": "fixture",
                   "hosts": ["fixture"], "route": "socket-pair", "channelEpoch": "c" * 32,
                   "bridgeId": hello["bridgeId"], "role": "transport-relay",
                   "encodingDigest": sha256(canonical(hello["encoding"])).hexdigest(), **(request_changes or {})}
        await self.send(writer, {"protocol": "mesh.state-sync/1", "kind": "open", "controllerVersion": 1,
                                 "requestBinding": request, "remainingMs": 15000})
        if request_changes is None:
            setup = await self.read(reader)
            self.assertEqual(setup["kind"], "setup")
            self.assertEqual(setup["requestBinding"], request)
        return reader, writer, task, sha256(canonical(request)).hexdigest()

    async def send(self, writer, value):
        writer.write(canonical(value) + b"\n")
        await writer.drain()

    async def read(self, reader):
        raw = await asyncio.wait_for(reader.readline(), 2)
        self.assertTrue(raw.endswith(b"\n"), raw)
        return decode(raw)

    def command(self, digest, sequence, operation, **fields):
        return {"protocol": "mesh.state-sync/1", "kind": "command", "request": digest,
                "sequence": sequence, "operation": operation, **fields}

    async def begin(self, writer, reader, digest, sequence=1, remaining=15000):
        await self.send(writer, self.command(digest, sequence, "begin", remainingMs=remaining))
        result = await self.read(reader)
        self.assertEqual((result["command"], result["status"], result["code"]), (sequence, "ok", "none"))
        return result

    async def test_hello_open_begin_material_result_through_end_and_new_capsule(self):
        reader, writer, _task, digest = await self.connect()
        self.assertEqual((await self.begin(writer, reader, digest))["through"], 0)
        await self.send(writer, self.command(digest, 2, "baseline", acquisition=1))
        delivery, result = await self.read(reader), await self.read(reader)
        self.assertEqual(delivery["payload"]["kind"], "material")
        self.assertEqual((delivery["sequence"], result["command"], result["through"]), (1, 2, 1))
        await self.send(writer, self.command(digest, 3, "end", acquisition=1))
        ended = await self.read(reader)
        self.assertEqual((ended["operation"], ended["status"], ended["through"]), ("end", "ok", 1))
        await self.begin(writer, reader, digest, sequence=4)
        metrics = self.carriers[0].output_channel.inspect()
        self.assertEqual(metrics["receivedFrames"], 6)
        self.assertGreater(metrics["physicalReceivedBytes"], 0)
        self.assertGreater(metrics["physicalSentBytes"], 0)

    async def test_zero_change_native_complete_drains_before_ok(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        tag = self.source.tag.wire()
        await self.send(writer, self.command(digest, 2, "changes", acquisition=1, base=tag, target=tag,
                                             maxTransactions=1, maxBytes=8388608))
        control, result = await self.read(reader), await self.read(reader)
        self.assertEqual(control["payload"]["native"]["status"], "complete")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["through"], control["sequence"])

    async def test_original_recovery_drains_then_failed_source_without_success_or_reused_capsule(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        tag = self.source.tag.wire()
        await self.send(writer, self.command(digest, 2, "changes", acquisition=1, base=tag, target=tag,
                                             maxTransactions=1, maxBytes=8388608))
        await self.read(reader)
        await self.read(reader)
        original = decode(self.source.last_complete)
        original.update(status="baseline_required", reason="fixture-recovery")
        self.source.recovery = canonical(original) + b' \n'
        await self.send(writer, self.command(digest, 3, "changes", acquisition=1, base=tag, target=tag,
                                             maxTransactions=1, maxBytes=8388608))
        control, result = await self.read(reader), await self.read(reader)
        self.assertEqual(control["payload"]["native"], original)
        self.assertEqual((result["status"], result["code"], result["through"]), ("failed", "source", 2))
        await self.begin(writer, reader, digest, sequence=4)

    async def test_setup_output_lock_preserves_original_deadline_and_prepaid_copy(self):
        supplied, peer = socket.socketpair()
        carrier = control_carrier_from_ipc(supplied, ledger=self.ledger)
        self.carriers.append(carrier)
        reader, writer = await asyncio.open_connection(sock=peer)
        self.clients.append(writer)
        await carrier.output_channel.lock.acquire()
        now = [boottime_ms()]
        with (patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.controller.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0])):
            task = asyncio.create_task(serve_sync_relay(self.relay, carrier, setup_deadline_ms=now[0] + 100))
            self.tasks.append(task)
            await self.send(writer, {"protocol": "mesh.state-sync/1", "kind": "hello", "nonce": "f" * 64})
            async def waiting():
                while not self.relay._controllers or self.ledger.encoded_reserved < 131072 + 65536:
                    await asyncio.sleep(0)
            await asyncio.wait_for(waiting(), 1)
            self.assertEqual(carrier._output.inspect()["physicalSentBytes"], 0)
            now[0] += 100
            carrier._output.lock.release()
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b'')
            result = (await asyncio.gather(task, return_exceptions=True))[0]
            self.assertIsInstance(result, ProtocolError)
            self.errors.append(result)
        self.assertEqual(len(self.source.sessions), 0)

    async def test_factory_client_limit_includes_pending_hellos_and_close_joins_only_owned_carriers(self):
        readers = []
        for _ in range(17):
            supplied, peer = socket.socketpair()
            carrier = control_carrier_from_ipc(supplied, ledger=self.ledger)
            self.carriers.append(carrier)
            reader, writer = await asyncio.open_connection(sock=peer)
            self.clients.append(writer)
            readers.append(reader)
            task = asyncio.create_task(serve_sync_relay(self.relay, carrier, setup_deadline_ms=boottime_ms() + 15000))
            self.tasks.append(task)
            await asyncio.sleep(0)
        self.assertEqual(len(self.relay._pending_controls), 16)
        self.assertEqual(await asyncio.wait_for(readers[-1].read(), 1), b'')
        result = (await asyncio.gather(self.tasks[-1], return_exceptions=True))[0]
        self.assertIsInstance(result, ProtocolError)
        self.assertEqual(str(result), "sync_relay_busy")
        self.errors.append(result)
        await self.relay.aclose()
        await asyncio.wait_for(asyncio.gather(*self.tasks, return_exceptions=True), 1)
        self.assertEqual(len(self.source.sessions), 0)
        self.assertEqual((len(self.relay._pending_controls), len(self.relay._controllers)), (0, 0))

    async def test_controller_capacity_refuses_before_offer_or_read_and_keeps_other_credit(self):
        base_reserved, base_encoded = self.ledger.reserved, self.ledger.encoded_reserved
        supplied, peer = socket.socketpair()
        self.clients.append((await asyncio.open_connection(sock=peer))[1])
        carrier = control_carrier_from_ipc(supplied, ledger=self.ledger)
        self.carriers.append(carrier)
        held = self.ledger.reserve(self.ledger.maximum - self.ledger.used - self.ledger.reserved - 131071)
        try:
            with patch.object(self.relay, "_offer", side_effect=AssertionError("unpaid offer")):
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity") as failure:
                    await serve_sync_relay(self.relay, carrier, setup_deadline_ms=boottime_ms() + 15000)
            self.errors.append(failure.exception)
            self.assertEqual(carrier._output.inspect()["physicalReceivedBytes"], 0)
            self.assertEqual(self.ledger.reserved, base_reserved + held.amount)
            self.assertEqual(self.ledger.encoded_reserved, base_encoded)
        finally:
            held.close()

    async def test_busy_is_denial_and_no_source_ref_or_work_queue(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        session = self.source.sessions[0]
        entered, release = asyncio.Event(), asyncio.Event()
        original = session.baseline
        async def blocked():
            entered.set()
            await release.wait()
            return await original()
        session.baseline = blocked
        await self.send(writer, self.command(digest, 2, "baseline", acquisition=1))
        await asyncio.wait_for(entered.wait(), 1)
        await self.send(writer, self.command(digest, 3, "baseline", acquisition=1))
        busy = await self.read(reader)
        self.assertEqual((busy["command"], busy["status"], busy["code"], busy["through"]),
                         (3, "failed", "busy", 0))
        self.assertEqual(len(session.packets), 0)
        await self.send(writer, self.command(digest, 4, "end", acquisition=1))
        denied_end = await self.read(reader)
        self.assertEqual((denied_end["status"], denied_end["code"]), ("failed", "busy"))
        release.set()
        self.assertEqual((await self.read(reader))["sequence"], 1)
        self.assertEqual((await self.read(reader))["command"], 2)

    async def test_cancel_has_two_cleanup_receipts_without_rearming_capsule(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        entered = asyncio.Event()
        async def blocked(_challenge):
            entered.set()
            await asyncio.Event().wait()
        self.source.sessions[0].head_after_nonce = blocked
        challenge = {"nonce": "b" * 64, "target": "d" * 64, "request": digest}
        await self.send(writer, self.command(digest, 2, "head", acquisition=1, challenge=challenge, remainingMs=2000))
        await asyncio.wait_for(entered.wait(), 1)
        await self.send(writer, self.command(digest, 3, "cancel", acquisition=1, command=2))
        target, cancelled = await self.read(reader), await self.read(reader)
        self.assertEqual((target["command"], target["status"]), (2, "cancelled"))
        self.assertEqual((cancelled["command"], cancelled["status"]), (3, "ok"))
        await self.begin(writer, reader, digest, sequence=4)

    async def test_expired_head_cancel_receipt_is_suppressed_but_live_cancel_cleanup_ack_remains(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        session = self.source.sessions[0]
        async def held(_challenge):
            lease = session.inputs.reserve(4096, encoded_bytes=1024)
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleanup.set()
                try:
                    await finish_owned(asyncio.create_task(release.wait()))
                finally:
                    lease.close()
        session.head_after_nonce = held
        now = [boottime_ms()]
        challenge = {"nonce": "b" * 64, "target": "d" * 64, "request": digest}
        with (patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.controller.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0])):
            await self.send(writer, self.command(digest, 2, "head", acquisition=1, challenge=challenge, remainingMs=100))
            await asyncio.wait_for(entered.wait(), 1)
            await self.send(writer, self.command(digest, 3, "cancel", acquisition=1, command=2))
            await asyncio.wait_for(cleanup.wait(), 1)
            self.assertGreaterEqual(self.ledger.encoded_reserved, 65536 + 1024)
            now[0] += 150
            release.set()
            acknowledgement = await self.read(reader)
            self.assertEqual((acknowledgement["command"], acknowledgement["status"]), (3, "ok"))
            await self.begin(writer, reader, digest, sequence=4)

    async def test_restricted_head_deadline_crossed_in_scanner_never_starts_proof_output(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        now = [boottime_ms()]
        self.codec.hook = lambda: now.__setitem__(0, now[0] + 101)
        challenge = {"nonce": "b" * 64, "target": "d" * 64, "request": digest}
        with (patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.controller.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.relay.clock_domain", return_value={"bootId": "owner-boot", "timeNamespace": "time:1"})):
            await self.send(writer, self.command(digest, 2, "head", acquisition=1, challenge=challenge, remainingMs=100))
            controller = next(iter(self.relay._controllers))
            async def retired():
                while controller.capid is not None or controller.active_task is not None:
                    await asyncio.sleep(0)
            await asyncio.wait_for(retired(), 1)
            self.assertEqual(self.carriers[0].output_channel.inspect()["byKind"]["sent"].get("delivery"), None)
            self.codec.hook = None
            await self.begin(writer, reader, digest, sequence=3)

    async def test_watch_outlives_end_and_expiry_but_stops_under_exact_new_capsule(self):
        reader, writer, _task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        cursor = ["owner", 1, self.source.tag.root]
        await self.send(writer, self.command(digest, 2, "watch", acquisition=1, cursor=cursor))
        self.assertEqual((await self.read(reader))["status"], "ok")
        stream = self.source.sessions[0].stream
        await self.send(writer, self.command(digest, 3, "end", acquisition=1))
        self.assertEqual((await self.read(reader))["status"], "ok")
        self.assertFalse(stream.closed)
        await self.begin(writer, reader, digest, sequence=4, remaining=30)
        await asyncio.sleep(.05)
        self.assertFalse(stream.closed)
        await self.begin(writer, reader, digest, sequence=5)
        await self.send(writer, self.command(digest, 6, "stop-watch", acquisition=5, watch=2))
        stopped = await self.read(reader)
        self.assertEqual(stopped["status"], "ok")
        self.assertTrue(stream.closed)

    async def test_foreign_bridge_and_request_replay_close_only_this_connection(self):
        good_reader, good_writer, _good_task, good_digest = await self.connect()
        reader, _writer, task, _digest = await self.connect(request_changes={"bridgeId": "e" * 32})
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        await asyncio.gather(task, return_exceptions=True)
        await self.begin(good_writer, good_reader, good_digest)
        reader, writer, task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        await self.send(writer, self.command(digest, 1, "begin", remainingMs=15000))
        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        await asyncio.gather(task, return_exceptions=True)
        self.assertFalse(self.relay._closed)

    async def test_framing_duplicate_and_unknown_variants_have_no_result_or_source_work(self):
        for raw in (b'{"operation":"end","operation":"begin"}\n', b'{"kind":"unknown"}\n',
                    b'{"sequence":-0}\n', b'{}\r\n'):
            reader, writer, task, _digest = await self.connect()
            packets = len(self.source.sessions[-1].packets)
            writer.write(raw)
            await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
            await asyncio.gather(task, return_exceptions=True)
            self.assertEqual(len(self.source.sessions[-1].packets), packets)

    async def test_old_first_byte_survives_busy_reply_and_never_mints_a_new_head_budget(self):
        reader, writer, task, digest = await self.connect()
        await self.begin(writer, reader, digest)
        session = self.source.sessions[0]
        entered = asyncio.Event()
        async def blocked():
            entered.set()
            await asyncio.Event().wait()
        session.baseline = blocked
        await self.send(writer, self.command(digest, 2, "baseline", acquisition=1))
        await asyncio.wait_for(entered.wait(), 1)
        controller = next(iter(self.relay._controllers))
        await controller.channel._output_lock.acquire()
        now = [boottime_ms()]
        challenge = {"nonce": "b" * 64, "target": "d" * 64, "request": digest}
        with (patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.controller.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: now[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0])):
            commands = [self.command(digest, n, "head", acquisition=1, challenge=challenge, remainingMs=2000)
                        for n in (3, 4)]
            writer.write(b"".join(canonical(value) + b"\n" for value in commands))
            await writer.drain()
            for _ in range(20):
                await asyncio.sleep(0)
            now[0] += 2101
            controller.channel._output_lock.release()
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(self.codec.calls, [])


if __name__ == "__main__":
    unittest.main()
