"""Owned relay API fixtures; no native, schema allocation or perf acceptance."""

import asyncio
import copy
import gc
import tempfile
import unittest
import weakref
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from test_sync_cache import NATIVE_BINDING, CacheProfile, baseline, transaction

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, SyncBudgets, create_sync_relay, source_binding
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import canonical, decode
from mesh_plus.transport import LineChannel, boottime_ms


class Writer:
    """Test-owned sink copies are oracle output, outside measured relay state."""

    def __init__(self):
        self.transport = self
        self.fragments, self.pending, self.closed = [], None, False
        self.block, self.reached = asyncio.Event(), asyncio.Event()
        self.close_started, self.close_release = asyncio.Event(), asyncio.Event()
        self.close_release.set()
        self.block.set()
        self.limits = (16384, 65536)
        self.write_hook = self.drain_hook = None

    def get_write_buffer_limits(self):
        return self.limits

    def set_write_buffer_limits(self, high, low):
        self.limits = low, high

    def get_write_buffer_size(self):
        return 0 if self.pending is None else len(self.pending)

    def write(self, value):
        if self.closed:
            raise EOFError("channel_closed")
        self.pending = value
        self.reached.set()
        if self.write_hook:
            self.write_hook(value)

    async def drain(self):
        if self.drain_hook:
            await self.drain_hook(self.pending)
        await self.block.wait()
        if not self.closed:
            self.fragments.append(bytes(self.pending))
        self.pending = None

    def close(self):
        self.closed, self.pending = True, None
        self.block.set()
        self.close_started.set()

    async def wait_closed(self):
        await self.close_release.wait()

    def frames(self):
        return [decode(raw) for raw in b"".join(self.fragments).splitlines()]


class Header:
    def __init__(self, ticket):
        self.ticket = weakref.ref(ticket)

    def _live(self):
        ticket = self.ticket()
        if ticket is None or ticket.closed:
            raise ProtocolError("sync_ticket_closed")
        return ticket

    @property
    def materialization_bytes(self):
        self._live()
        return 262144

    def materialize(self):
        _ = self.materialization_bytes
        return copy.deepcopy(self._live().document)


class ScanTicket:
    def __init__(self, document, credit):
        self.document, self.credit, self.closed = document, credit, False
        self.header = Header(self)

    def close(self):
        if not self.closed:
            self.closed = True
            self.document = None
            self.credit.close()


class Codec:
    """Fixture scanner only; real Observer scanner is qualified separately."""

    def __init__(self, descriptor):
        self.encoding = {"id": "mesh-relay-fixture/1", "schema": "e" * 64,
                         "nativeDescriptor": descriptor.native_descriptor_digest}
        self.calls, self.hook, self.saved_budget = [], None, None

    def header(self, raw, budget):
        self.saved_budget = budget
        credit = budget.reserve(262144)
        try:
            value = decode(raw)
            self.calls.append(value["kind"])
            if self.hook:
                self.hook()
            if value["kind"] == "baseline":
                value["tables"] = {name: [] for name in value["tables"]}
            if value["kind"] == "transaction":
                value["operations"] = {name: [] for name in value["operations"]}
            return ScanTicket(value, credit)
        except BaseException:
            credit.close()
            raise

    def head(self, raw, budget):
        result = self.header(raw, budget)
        if result.document["kind"] != "head":
            result.close()
            raise ProtocolError("sync_relay_header")
        return result


class Packet:
    def __init__(self, inputs, raw):
        self.lease = inputs.reserve(inputs.buffer_heap(len(raw)) + 4096, encoded_bytes=len(raw))
        self.data = self.lease.seal(raw)
        self.document = decode(raw)
        self.tag = tuple(self.document["tag"]) if self.document.get("tag") is not None else None
        self.cursor = tuple(self.document["cursor"]) if self.document.get("cursor") is not None else None
        self.status, self.reason = self.document.get("status"), self.document.get("reason")

    def close(self):
        self.data.close()
        self.document = None
        self.lease.close()


class CompletedChanges:
    """Fixture-owned bounded metadata, not the Observer implementation."""

    def __init__(self, inputs, transactions, completion):
        self.lease = inputs.reserve(4096)
        self._transactions, self._completion = transactions, completion
        self.closed = False

    @property
    def transactions(self):
        if self.closed:
            raise ProtocolError("sync_change_batch_closed")
        return self._transactions

    @property
    def completion(self):
        if self.closed:
            raise ProtocolError("sync_change_batch_closed")
        return self._completion

    def close(self):
        if self.closed:
            return
        self.closed = True
        transactions, completion = self._transactions, self._completion
        self._transactions = self._completion = None
        for item in transactions:
            item.close()
        completion.close()
        self.lease.close()


class SourceWatch:
    def __init__(self):
        self.queue, self.closed = asyncio.Queue(), False

    async def __aenter__(self):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.queue.get()

    async def aclose(self):
        self.closed = True
        while not self.queue.empty():
            self.queue.get_nowait().close()


class Session:
    def __init__(self, source, inputs):
        self.source, self.inputs, self.closed = source, inputs, False
        self.refs, self.packets = [], []  # bounded fixture work only
        self.batches = []
        self.stream = SourceWatch()

    def seal(self, raw):
        with self.inputs.reserve(self.inputs.buffer_heap(len(raw)), encoded_bytes=len(raw)) as lease:
            data = lease.seal(raw)
        self.refs.append(data)
        return data

    async def baseline(self):
        packet = Packet(self.inputs, self.source.raw)
        self.packets.append(packet)
        return packet

    async def changes(self, base, *, target, max_transactions, max_bytes):
        raise AssertionError("legacy changes cannot supply native completion")

    async def changes_with_completion(self, base, *, target, max_transactions, max_bytes):
        if self.source.recovery is not None:
            packet = Packet(self.inputs, self.source.recovery)
            self.packets.append(packet)
            return packet
        refs = tuple(self.seal(raw) for raw in self.source.chain)
        final = [NATIVE_BINDING["ownerEpoch"], target[1], target[2]] if not self.source.chain else decode(
            self.source.chain[-1])["resultCursor"]
        control = {"kind": "control", "descriptor": decode(self.source.profile.descriptor.native_descriptor),
                   "status": "complete", "reason": "sync_complete",
                   "tag": target, "cursor": final, "baseTag": base, "targetTag": target,
                   "ownerClock": {**{key: NATIVE_BINDING[key] for key in
                       ("bootId", "clockDomain", "uid", "hostScope", "ownerEpoch")}, "boottimeMs": 2000}}
        raw = canonical(control) + b"\n"
        if self.source.control_transform:
            raw = self.source.control_transform(control)
        self.source.last_complete = raw
        packet = Packet(self.inputs, raw)
        self.packets.append(packet)
        batch = CompletedChanges(self.inputs, refs, packet)
        self.batches.append(batch)
        if self.source.batch_hook:
            replacement = self.source.batch_hook(batch)
            if replacement is not None:
                return replacement
        return batch

    async def head_after_nonce(self, challenge):
        document = {"kind": "head", "descriptor": decode(self.source.profile.descriptor.native_descriptor),
                    "nativeBindingDigest": self.source.tag.binding, "tag": self.source.tag.wire(),
                    "challenge": challenge, "ownerClock": {**{key: NATIVE_BINDING[key] for key in
                        ("bootId", "clockDomain", "uid", "hostScope", "ownerEpoch")},
                        "boottimeMs": boottime_ms() - 10},
                    "originalReceipts": [], "cohortHeads": [], "attenuation": [["receipt", 1000]]}
        if self.source.moved is not None:
            document["tag"] = self.source.moved.wire()
        return self.seal(canonical(document) + b"\n")

    def watch(self, cursor):
        return self.stream

    async def aclose(self):
        self.closed = True
        await self.stream.aclose()
        for item in self.refs + self.packets:
            item.close()
        for batch in self.batches:
            batch.close()
        self.batches.clear()
        self.refs.clear()
        self.packets.clear()


class Source:
    def __init__(self, profile):
        self.profile = profile
        raw, self.maps, self.tag = baseline(profile)
        self.raw, self.chain, self.moved = raw + b"\n", [], None
        self.control_transform = self.batch_hook = self.recovery = self.last_complete = None
        self.sessions, self.closed = [], False

    def open_session(self, inputs):
        result = Session(self, inputs)
        self.sessions.append(result)
        return result

    async def aclose(self):
        self.closed = True
        for session in self.sessions:
            await session.aclose()


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.profile = CacheProfile()
        self.ledger = AllocationLedger()
        self.source = Source(self.profile)
        self.codec = Codec(self.profile.descriptor)
        self.binding = source_binding("fixture", "agents", self.profile.descriptor)
        self.relay = create_sync_relay(self.source, self.profile.descriptor, self.binding,
                                       native_codec=self.codec, budgets=SyncBudgets(), ledger=self.ledger)
        self.saved_gc = gc.isenabled()
        gc.disable()

    async def asyncTearDown(self):
        await self.relay.aclose()
        self.assertEqual(self.ledger.used, 0)
        self.assertEqual(self.ledger.reserved, 0)
        self.assertEqual(self.ledger.encoded, 0)
        self.assertEqual(self.ledger.encoded_reserved, 0)
        self.assertEqual(self.ledger.pending_units, 0)
        if self.saved_gc:
            gc.enable()

    def request(self, **changes):
        return {"readerEpoch": "a" * 32, "requestId": "test", "catalogRevision": "test",
                "hosts": ["fixture"], "route": "ipc-fixture", "channelEpoch": "c" * 32,
                "bridgeId": self.relay.bridge_id, "role": "transport-relay",
                "encodingDigest": sha256(canonical(self.codec.encoding)).hexdigest(), **changes}

    async def channel(self):
        writer = Writer()
        line = LineChannel(None, writer, "client")
        writer.line = line
        channel = await self.relay.open_channel(line, self.request(), setup_deadline_ms=boottime_ms() + 15000)
        return channel, writer

    async def test_baseline_verbatim_wrapper_and_independent_reader_admission(self):
        channel, writer = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        await capsule.baseline()
        frame = writer.frames()[-1]
        self.assertEqual(frame["sequence"], 1)
        self.assertEqual(frame["payload"]["sourceTag"]["native"], self.source.tag.wire())
        self.assertIn(self.source.raw[:-1], b"".join(writer.fragments))
        self.assertEqual(self.codec.calls, ["baseline"])
        self.assertFalse(hasattr(self.relay, "profile"))
        self.assertFalse(hasattr(channel, "baseline"))
        with self.assertRaisesRegex(ProtocolError, "sync_reference_retired"):
            self.codec.saved_budget.reserve(1)
        # A structurally valid changed body with unchanged claimed roots must
        # still pass through the Reader's independent ordinary admission.
        document = decode(self.source.raw)
        document["tables"]["bodies"][0][1] = {"invalid": "domain"}
        self.source.raw = canonical(document) + b"\n"
        await capsule.baseline()
        reader = OwnedSyncCache(self.profile, self.binding)
        try:
            with self.assertRaises(ProtocolError):
                reader.admit_baseline(canonical(writer.frames()[-1]["payload"]["native"]))
        finally:
            reader.close()
        await capsule.aclose()

    async def test_wrong_role_bridge_and_old_request_reject_before_channel_transfer(self):
        for changes in ({"role": "material-publisher"}, {"bridgeId": "d" * 32}, {"channelEpoch": True}):
            line = LineChannel(None, Writer(), "client")
            with self.assertRaises(ProtocolError):
                await self.relay.open_channel(line, self.request(**changes), setup_deadline_ms=boottime_ms() + 15000)
            self.assertFalse(line.closed)
            await line.close()

    async def test_input_close_revokes_pins_but_live_receive_credit_waits(self):
        channel, _ = await self.channel()
        sibling, _ = await self.channel()
        owner = channel.input_owner()
        lease = owner.reserve(4096, encoded_bytes=1024)
        ref = self.source.sessions[0].seal(b"{}\n")
        owner.close()
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            _ = ref.nbytes
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            lease.resize(8192)
        await channel.aclose()
        held = self.ledger.reserved
        self.assertGreaterEqual(self.ledger.encoded_reserved, 1024)
        self.assertIsNotNone(sibling.input_owner())
        owner.close()
        self.assertEqual(self.ledger.reserved, held)
        lease.close()

    async def test_wrong_owner_ref_retires_only_supplied_handle(self):
        channel, _ = await self.channel()
        sibling, _ = await self.channel()
        wrong = self.source.sessions[1].seal(b"{}\n")
        other = self.source.sessions[1].seal(b"{}\n")
        with self.assertRaisesRegex(ProtocolError, "sync_input_owner"):
            await channel._forward(wrong, boottime_ms() + 1000, channel._check)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            _ = wrong.nbytes
        self.assertEqual(other.nbytes, 3)
        self.assertIsNotNone(sibling.input_owner())

    async def test_close_inside_scanner_never_publishes(self):
        channel, writer = await self.channel()
        self.codec.hook = channel.input_owner().close
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            await capsule.baseline()
        await channel.aclose()
        self.assertEqual(len(writer.frames()), 1)  # setup only

    async def test_blocked_write_pins_input_until_cancellation_unwinds(self):
        channel, writer = await self.channel()
        writer.block.clear()
        writer.close_release.clear()
        writer.reached.clear()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        job = asyncio.create_task(capsule.baseline())
        await writer.reached.wait()
        before = self.ledger.encoded_reserved
        self.assertGreaterEqual(before, len(self.source.raw))
        job.cancel()
        await writer.close_started.wait()
        self.assertGreaterEqual(self.ledger.encoded_reserved, len(self.source.raw))
        job.cancel()  # repeated cancellation while owned physical cleanup waits
        self.assertFalse(job.done())
        writer.close_release.set()
        with self.assertRaises(asyncio.CancelledError):
            await job
        await channel.aclose()
        self.assertIsNone(writer.pending)

    async def test_four_transactions_and_bad_last_header_no_prefix(self):
        channel, writer = await self.channel()
        maps, tag = self.source.maps, self.source.tag
        for generation in range(2, 6):
            raw, maps, tag = transaction(self.profile, maps, tag, generation, generation)
            self.source.chain.append(raw + b"\n")
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        await capsule.changes(self.source.tag, target=tag)
        self.assertEqual([frame["sequence"] for frame in writer.frames()[1:]], [1, 2, 3, 4, 5])
        self.assertEqual(writer.frames()[-1]["payload"]["kind"], "control")
        self.assertIn(self.source.last_complete[:-1], b"".join(writer.fragments))
        await capsule.aclose()
        other, writer2 = await self.channel()
        self.source.chain[-1] = self.source.chain[0]
        capsule = other.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_relay_chain"):
            await capsule.changes(self.source.tag, target=tag)
        self.assertEqual(len(writer2.frames()), 1)
        self.assertTrue(all(self.retired(ref) for ref in self.source.sessions[-1].refs))
        await capsule.aclose()

    def chain(self, count):
        self.source.chain.clear()
        maps, tag = self.source.maps, self.source.tag
        for generation in range(2, count + 2):
            raw, maps, tag = transaction(self.profile, maps, tag, generation, generation)
            self.source.chain.append(raw + b"\n")
        return tag

    async def test_zero_one_and_four_deliver_exact_terminal_after_material(self):
        for count in (0, 1, 4):
            with self.subTest(count=count):
                target = self.chain(count)
                self.source.control_transform = lambda value: canonical(value) + b"  \n"
                channel, writer = await self.channel()
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                await capsule.changes(self.source.tag, target=target)
                deliveries = writer.frames()[1:]
                self.assertEqual([item["sequence"] for item in deliveries], list(range(1, count + 2)))
                self.assertEqual([item["payload"]["kind"] for item in deliveries], ["material"] * count + ["control"])
                self.assertIn(self.source.last_complete[:-1], b"".join(writer.fragments))
                self.assertEqual(deliveries[-1]["payload"]["native"]["cursor"][1:], [target.generation, target.root])
                batch = self.source.sessions[-1].batches[-1]
                self.assertTrue(batch.closed)
                with self.assertRaisesRegex(ProtocolError, "sync_change_batch_closed"):
                    _ = batch.completion
                batch.close()
                await capsule.aclose()
                await channel.aclose()

    async def test_wrong_completion_or_cursor_epoch_never_emits_a_prefix(self):
        target = self.chain(1)
        errors = []
        cases = {
            "base": lambda value: value.update(baseTag=target.wire()),
            "target": lambda value: value.update(targetTag=self.source.tag.wire()),
            "tag": lambda value: value.update(tag=self.source.tag.wire()),
            "epoch": lambda value: value["cursor"].__setitem__(0, "foreign-owner"),
            "root": lambda value: value["cursor"].__setitem__(2, "f" * 64),
            "status": lambda value: value.update(status="heartbeat"),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                def transform(value):
                    change(value)
                    return canonical(value) + b"\n"
                self.source.control_transform = transform
                channel, writer = await self.channel()
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                try:
                    await capsule.changes(self.source.tag, target=target)
                except ProtocolError as error:
                    errors.append(error)
                else:
                    self.fail("invalid completion accepted")
                self.assertEqual(len(writer.frames()), 1)
                self.assertTrue(self.source.sessions[-1].batches[-1].closed)
                await capsule.aclose()
                await channel.aclose()
        self.assertEqual(len(errors), len(cases))

    async def test_chain_cursor_discontinuity_and_malformed_terminal_reject_before_output(self):
        target = self.chain(2)
        changed = decode(self.source.chain[1])
        changed["baseCursor"][0] = changed["resultCursor"][0] = "different-owner"
        self.source.chain[1] = canonical(changed) + b"\n"
        channel, writer = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_relay_chain"):
            await capsule.changes(self.source.tag, target=target)
        self.assertEqual(len(writer.frames()), 1)
        await capsule.aclose()
        await channel.aclose()
        self.source.chain.clear()
        for malformed in (b'{"kind":"control","kind":"control"}\n', b'{"kind":"control"\n'):
            # Packet fixture parses metadata, so corruption must occur after
            # packet construction to reach the independent relay scanner.
            self.source.control_transform = None
            def corrupt(batch):
                old = batch.completion.data
                batch.completion.data = self.source.sessions[-1].seal(malformed)
                old.close()
            self.source.batch_hook = corrupt
            channel, writer = await self.channel()
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            with self.assertRaises(ProtocolError):
                await capsule.changes(self.source.tag, target=self.source.tag)
            self.assertEqual(len(writer.frames()), 1)
            await capsule.aclose()
            await channel.aclose()

    async def test_missing_optional_method_fails_setup_without_legacy_fallback(self):
        with patch.object(Session, "changes_with_completion", None):
            line = LineChannel(None, Writer(), "client")
            with self.assertRaisesRegex(ProtocolError, "sync_relay_setup"):
                await self.relay.open_channel(line, self.request(), setup_deadline_ms=boottime_ms() + 15000)
            self.assertTrue(line.closed)

    async def test_outer_control_bound_and_material_quota_checked_before_prefix(self):
        target = self.chain(1)
        self.source.control_transform = lambda value: canonical(value) + b" " * (65499 - len(canonical(value))) + b"\n"
        for maximum in (8388608, 1):
            channel, writer = await self.channel()
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            expected = "sync_relay_output" if maximum == 8388608 else "sync_catchup_capacity"
            with self.assertRaisesRegex(ProtocolError, expected):
                await capsule.changes(self.source.tag, target=target, max_bytes=maximum)
            self.assertEqual(len(writer.frames()), 1)
            await capsule.aclose()
            await channel.aclose()

    async def test_material_drain_precedes_completion_and_retains_all_input_pins(self):
        target = self.chain(1)
        channel, writer = await self.channel()
        reached, release = asyncio.Event(), asyncio.Event()
        async def hold(value):
            if bytes(value) == self.source.chain[0][:-1]:
                reached.set()
                await release.wait()
        writer.drain_hook = hold
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        job = asyncio.create_task(capsule.changes(self.source.tag, target=target))
        await asyncio.wait_for(reached.wait(), 1)
        batch = self.source.sessions[-1].batches[-1]
        self.assertGreater(batch.lease.heap_bytes, 0)
        self.assertGreater(batch.completion.lease.heap_bytes, 0)
        self.assertGreaterEqual(self.ledger.encoded_reserved, len(self.source.chain[0]) + len(self.source.last_complete))
        self.assertNotIn(self.source.last_complete[:-1], b"".join(writer.fragments))
        release.set()
        await job
        self.assertEqual(writer.frames()[-1]["payload"]["native"]["status"], "complete")
        await capsule.aclose()

    async def test_source_scope_close_during_drain_revokes_without_touching_sibling(self):
        target = self.chain(1)
        channel, writer = await self.channel()
        sibling, _ = await self.channel()
        writer.block.clear()
        writer.close_release.clear()
        writer.reached.clear()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        job = asyncio.create_task(capsule.changes(self.source.tag, target=target))
        await asyncio.wait_for(writer.reached.wait(), 1)
        batch = self.source.sessions[0].batches[-1]
        batch.close()
        total = len(self.source.chain[0]) + len(self.source.last_complete)
        self.assertGreaterEqual(self.ledger.encoded_reserved, total)
        writer.block.set()
        await asyncio.wait_for(writer.close_started.wait(), 1)
        self.assertGreaterEqual(self.ledger.encoded_reserved, total)
        job.cancel()
        await asyncio.sleep(0)
        job.cancel()
        self.assertFalse(job.done())
        writer.close_release.set()
        errors = []
        try:
            await job
        except (ProtocolError, asyncio.CancelledError) as error:
            errors.append(error)
        self.assertEqual(len(errors), 1)
        await channel.aclose()
        self.assertIsNotNone(sibling.input_owner())
        self.assertFalse(any(self.source.last_complete[:-1] in part for part in writer.fragments))
        await capsule.aclose()

    async def test_foreign_or_duplicate_ref_is_not_transferred_or_overreleased(self):
        from types import SimpleNamespace
        target = self.chain(1)
        sibling, _ = await self.channel()
        foreign = self.source.sessions[0].seal(b"{}\n")
        closed = []
        for duplicate in (False, True):
            def invalid(batch):
                refs = (*batch.transactions, batch.completion.data) if duplicate else (foreign,)
                return SimpleNamespace(transactions=refs, completion=batch.completion,
                                       close=lambda: closed.append(True))
            self.source.batch_hook = invalid
            channel, writer = await self.channel()
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            with self.assertRaises(ProtocolError):
                await capsule.changes(self.source.tag, target=target)
            await channel.aclose()
            self.assertEqual(foreign.nbytes, 3)
            self.assertEqual(len(writer.frames()), 1)
            await capsule.aclose()
        self.assertEqual(closed, [])
        self.assertIsNotNone(sibling.input_owner())
        foreign.close()

    async def test_failed_transaction_or_completion_write_preserves_pins_through_close(self):
        target = self.chain(1)
        errors = []
        for control in (False, True):
            channel, writer = await self.channel()
            writer.close_release.clear()
            def fail(value):
                raw = bytes(value)
                expected = self.source.last_complete[:-1] if control else self.source.chain[0][:-1]
                if raw == expected:
                    raise OSError("fixture write failure")
            writer.write_hook = fail
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            job = asyncio.create_task(capsule.changes(self.source.tag, target=target))
            await asyncio.wait_for(writer.close_started.wait(), 1)
            self.assertGreaterEqual(self.ledger.encoded_reserved, len(self.source.chain[0]) + len(self.source.last_complete))
            self.assertFalse(job.done())
            batch = self.source.sessions[-1].batches[-1]
            writer.close_release.set()
            try:
                await job
            except ProtocolError as error:
                errors.append(error)
            await channel.aclose()
            self.assertTrue(batch.closed)
            await capsule.aclose()
        self.assertEqual(len(errors), 2)

    async def test_missing_or_mismatched_control_metadata_has_no_success_prefix(self):
        from types import SimpleNamespace
        target = self.chain(1)
        for name in ("missing", "tag", "reason"):
            def corrupt(batch):
                if name == "missing":
                    return SimpleNamespace(transactions=batch.transactions, completion=None, close=lambda: None)
                setattr(batch.completion, name, self.source.tag.wire() if name == "tag" else "wrong")
            self.source.batch_hook = corrupt
            channel, writer = await self.channel()
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            with self.assertRaises(ProtocolError):
                await capsule.changes(self.source.tag, target=target)
            self.assertEqual(len(writer.frames()), 1)
            await channel.aclose()
            await capsule.aclose()

    async def test_recovery_control_is_original_and_never_a_completed_batch(self):
        channel, writer = await self.channel()
        session = self.source.sessions[-1]
        sample = await session.changes_with_completion(self.source.tag.wire(), target=self.source.tag.wire(),
                                                       max_transactions=4, max_bytes=8388608)
        document = decode(self.source.last_complete)
        sample.close()
        document.update(status="baseline_required", reason="fixture-recovery")
        self.source.recovery = canonical(document) + b" \n"
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        await capsule.changes(self.source.tag, target=self.source.tag)
        self.assertEqual(len(writer.frames()), 2)
        self.assertEqual(writer.frames()[-1]["payload"]["native"]["status"], "baseline_required")
        self.assertIn(self.source.recovery[:-1], b"".join(writer.fragments))
        await capsule.aclose()

    async def test_batch_preallocation_refuses_before_request_or_container_creation(self):
        channel, writer = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        remaining = self.ledger.maximum - self.ledger.used - self.ledger.reserved
        with self.ledger.reserve(remaining - 1024):
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                await capsule.changes(self.source.tag, target=self.source.tag)
            session = self.source.sessions[-1]
            self.assertEqual((session.refs, session.packets, session.batches), ([], [], []))
            self.assertEqual(len(writer.frames()), 1)
        await capsule.aclose()

    @staticmethod
    def retired(ref):
        try:
            _ = ref.nbytes
            return False
        except ProtocolError:
            return True

    async def test_head_original_deadline_covers_source_and_synchronous_scanner(self):
        errors = []
        for phase in ("source", "scanner"):
            for elapsed in (1999, 2000, 2101):
                with self.subTest(phase=phase, elapsed=elapsed):
                    channel, writer = await self.channel()
                    session = self.source.sessions[-1]
                    capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                    start = boottime_ms()
                    clock, writes = [start], []
                    writer.write_hook = lambda value: writes.append(clock[0] - start)
                    original = session.head_after_nonce
                    async def receive(challenge):
                        result = await original(challenge)
                        if phase == "source":
                            clock[0] = start + elapsed
                        return result
                    session.head_after_nonce = receive
                    self.codec.calls.clear()
                    self.codec.hook = lambda: clock.__setitem__(0, start + elapsed)
                    challenge = {"nonce": "b" * 64, "target": "d" * 64,
                                 "request": sha256(canonical(self.request())).hexdigest()}
                    with (patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: clock[0]),
                          patch("mesh_plus.transport.boottime_ms", side_effect=lambda: clock[0]),
                          patch("mesh_plus.sync.relay.clock_domain", return_value={
                              "bootId": "owner-boot", "timeNamespace": "time:1"})):
                        try:
                            await capsule.head_after_nonce(challenge)
                        except ProtocolError as error:
                            errors.append(error)
                            self.assertGreaterEqual(elapsed, 2000)
                        else:
                            self.assertLess(elapsed, 2000)
                    if elapsed >= 2000:
                        self.assertEqual(writes, [])
                        self.assertEqual(len(writer.frames()), 1)
                        if phase == "source":
                            self.assertEqual(self.codec.calls, [])
                    else:
                        self.assertTrue(writes)
                        self.assertTrue(all(value < 2000 for value in writes))
                        self.assertEqual(writer.frames()[-1]["payload"]["kind"], "proof")
                    self.codec.hook = None
                    await capsule.aclose()
                    await channel.aclose()
        self.assertEqual(len(errors), 4)

    async def test_head_expiry_queued_on_either_output_lock_preserves_pending_watch(self):
        errors = []
        for lock_name in ("_output_lock", "line"):
            with self.subTest(lock=lock_name):
                channel, writer = await self.channel()
                session = self.source.sessions[-1]
                watch = await channel.watch(["owner", 1, "f" * 64],
                                            startup_deadline_ms=boottime_ms() + 15000)
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                lock = writer.line.lock if lock_name == "line" else channel._output_lock
                await lock.acquire()
                start = boottime_ms()
                clock, writes, scanned = [start], [], asyncio.Event()
                encoded_before = self.ledger.encoded_reserved
                writer.write_hook = lambda value: writes.append(clock[0] - start)
                self.codec.hook = scanned.set
                challenge = {"nonce": "b" * 64, "target": "d" * 64,
                             "request": sha256(canonical(self.request())).hexdigest()}
                with (patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: clock[0]),
                      patch("mesh_plus.transport.boottime_ms", side_effect=lambda: clock[0]),
                      patch("mesh_plus.sync.relay.clock_domain", return_value={
                          "bootId": "owner-boot", "timeNamespace": "time:1"})):
                    job = asyncio.create_task(capsule.head_after_nonce(challenge))
                    try:
                        await asyncio.wait_for(scanned.wait(), 1)
                        self.assertTrue(session.refs)
                        self.assertGreater(self.ledger.encoded_reserved, encoded_before)
                        self.assertFalse(job.done())
                        clock[0] = start + 2000
                    finally:
                        lock.release()
                    try:
                        await job
                    except ProtocolError as error:
                        errors.append(error)
                    self.assertEqual(writes, [])
                    self.assertFalse(watch._closed)
                    self.assertIsNotNone(channel.input_owner())
                self.codec.hook = None
                await capsule.aclose()
                await watch.aclose()
                await channel.aclose()
        self.assertEqual(len(errors), 2)

    async def test_head_expiry_after_first_fragment_keeps_credit_through_cancelled_close(self):
        channel, writer = await self.channel()
        sibling, _ = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        start = boottime_ms()
        clock, writes, errors = [start], [], []
        def expire(value):
            writes.append(clock[0] - start)
            clock[0] = start + 2000
        writer.write_hook = expire
        writer.close_release.clear()
        challenge = {"nonce": "b" * 64, "target": "d" * 64,
                     "request": sha256(canonical(self.request())).hexdigest()}
        with (patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: clock[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: clock[0]),
              patch("mesh_plus.sync.relay.clock_domain", return_value={
                  "bootId": "owner-boot", "timeNamespace": "time:1"})):
            job = asyncio.create_task(capsule.head_after_nonce(challenge))
            await asyncio.wait_for(writer.close_started.wait(), 1)
            self.assertGreater(self.ledger.encoded_reserved, 131072)
            self.assertFalse(job.done())
            for _ in range(2):
                job.cancel()
                await asyncio.sleep(0)
            self.assertFalse(job.done())
            writer.close_release.set()
            try:
                await job
            except (ProtocolError, asyncio.CancelledError) as error:
                errors.append(error)
        self.assertEqual(writes, [0])
        self.assertEqual(len(writer.frames()), 1)
        self.assertIsNotNone(sibling.input_owner())
        self.assertEqual(len(errors), 1)
        await capsule.aclose()
        await channel.aclose()

    async def test_head_timeout_does_not_reclaim_blocked_watch_output_or_input(self):
        channel, writer = await self.channel()
        session = self.source.sessions[-1]
        watch = await channel.watch([NATIVE_BINDING["ownerEpoch"], 1, self.source.tag.root],
                                    startup_deadline_ms=boottime_ms() + 15000)
        update, _, _ = transaction(self.profile, self.source.maps, self.source.tag, 2, 2)
        writer.reached.clear()
        writer.block.clear()
        await session.stream.queue.put(session.seal(update + b"\n"))
        await asyncio.wait_for(writer.reached.wait(), 1)
        pending = writer.pending
        self.assertIsNotNone(pending)
        watch_credit = self.ledger.encoded_reserved
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        start = boottime_ms()
        clock, scanned, errors = [start], asyncio.Event(), []
        self.codec.hook = scanned.set
        challenge = {"nonce": "b" * 64, "target": "d" * 64,
                     "request": sha256(canonical(self.request())).hexdigest()}
        with (patch("mesh_plus.sync.relay.boottime_ms", side_effect=lambda: clock[0]),
              patch("mesh_plus.transport.boottime_ms", side_effect=lambda: clock[0])):
            job = asyncio.create_task(capsule.head_after_nonce(challenge))
            await asyncio.wait_for(scanned.wait(), 1)
            self.assertGreater(self.ledger.encoded_reserved, watch_credit)
            clock[0] = start + 2000
            try:
                await job
            except ProtocolError as error:
                errors.append(error)
            self.assertFalse(watch._closed)
            self.assertIs(writer.pending, pending)
            self.assertEqual(writer.limits, (0, 0))
            self.assertGreaterEqual(self.ledger.encoded_reserved, watch_credit)
            self.assertIsNotNone(channel.input_owner())
        self.codec.hook = None
        writer.block.set()
        async def delivered():
            while writer.line.inspect()["sentFrames"] < 2:
                await asyncio.sleep(0)
        await asyncio.wait_for(delivered(), 1)
        self.assertEqual(writer.frames()[-1]["payload"]["kind"], "material")
        self.assertEqual(len(errors), 1)
        pending = None
        await capsule.aclose()
        await watch.aclose()
        await channel.aclose()

    async def test_invalid_batch_count_and_mixed_types_close_only_source_owned_scope(self):
        from types import SimpleNamespace

        from mesh_plus.sync.relay_inputs import relay_bytes

        sibling, _ = await self.channel()
        foreign = self.source.sessions[-1].seal(b"{}\n")
        errors, unexpected_transfer = [], []
        # A sibling physical pin remains live through every malformed-result unwind.
        with relay_bytes(sibling, foreign) as raw:
            for kind in ("five", "requested-one", "mixed", "list"):
                target = self.chain(5 if kind == "five" else 2)
                own_refs = []
                def invalid(batch):
                    own_refs.extend((*batch.transactions, batch.completion.data))
                    rows = batch.transactions
                    if kind == "mixed":
                        rows = (rows[0], object())
                    elif kind == "list":
                        rows = list(rows)
                    return SimpleNamespace(transactions=rows, completion=batch.completion,
                                           close=lambda: unexpected_transfer.append(True))
                self.source.batch_hook = invalid
                channel, writer = await self.channel()
                session = self.source.sessions[-1]
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                try:
                    await capsule.changes(self.source.tag, target=target,
                                          max_transactions=1 if kind == "requested-one" else 4)
                except ProtocolError as error:
                    errors.append(error)
                self.assertTrue(session.closed)
                self.assertTrue(all(self.retired(ref) for ref in own_refs))
                with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                    channel.input_owner()
                self.assertEqual(len(writer.frames()), 1)
                self.assertEqual(raw, b"{}\n")
                self.assertGreaterEqual(self.ledger.encoded_reserved, len(raw))
                self.assertIsNotNone(sibling.input_owner())
                await capsule.aclose()
                await channel.aclose()
        self.assertEqual(unexpected_transfer, [])
        self.assertEqual(len(errors), 4)

    async def test_source_error_before_batch_delivery_closes_partial_owned_result(self):
        channel, writer = await self.channel()
        sibling, _ = await self.channel()
        own_refs, errors = [], []
        def fail(batch):
            own_refs.extend((*batch.transactions, batch.completion.data))
            raise ProtocolError("fixture_source_failed_before_delivery")
        self.source.batch_hook = fail
        self.chain(1)
        session = self.source.sessions[0]
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        try:
            await capsule.changes(self.source.tag, target=self.source.tag)
        except ProtocolError as error:
            errors.append(error)
        self.assertTrue(session.closed)
        self.assertTrue(all(self.retired(ref) for ref in own_refs))
        self.assertEqual(len(writer.frames()), 1)
        self.assertIsNotNone(sibling.input_owner())
        self.assertEqual(len(errors), 1)
        await capsule.aclose()
        await channel.aclose()

    async def test_fresh_head_attenuates_actual_moved_tag_without_body_scan(self):
        channel, writer = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        challenge = {"nonce": "b" * 64, "target": "d" * 64,
                     "request": sha256(canonical(self.request())).hexdigest()}
        with patch("mesh_plus.sync.relay.clock_domain", return_value={"bootId": "owner-boot", "timeNamespace": "time:1"}):
            await capsule.head_after_nonce(challenge)
        payload = writer.frames()[-1]["payload"]
        self.assertEqual(self.codec.calls, ["head"])
        self.assertEqual(payload["challenge"], challenge)
        self.assertEqual(payload["sourceTag"]["native"], self.source.tag.wire())
        self.assertLessEqual(payload["remaining"][0][1], 990)
        await capsule.aclose()

    async def test_strict_raw_lf_and_codec_replacement_reject(self):
        for invalid in (self.source.raw[:-1], self.source.raw + b"\n", self.source.raw.replace(b"\n", b"\r\n")):
            channel, writer = await self.channel()
            self.source.raw = invalid
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
            with self.assertRaises(ProtocolError):
                await capsule.baseline()
            self.assertEqual(len(writer.frames()), 1)
            await capsule.aclose()
        channel, _ = await self.channel()
        original = self.codec.header
        self.codec.header = lambda raw, budget: original(raw, budget)
        with self.assertRaisesRegex(ProtocolError, "sync_codec_identity"):
            channel.input_owner()
        self.codec.header = original

    async def test_watch_and_capsule_are_independent_and_sequence_serialized(self):
        channel, writer = await self.channel()
        stream = self.source.sessions[0].stream
        watch = await channel.watch([NATIVE_BINDING["ownerEpoch"], 1, self.source.tag.root],
                                    startup_deadline_ms=boottime_ms() + 15000)
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_relay_busy"):
            await capsule.baseline()
        await capsule.aclose()
        update, _, _ = transaction(self.profile, self.source.maps, self.source.tag, 2, 2)
        ref = self.source.sessions[0].seal(update + b"\n")
        await stream.queue.put(ref)
        async def delivered():
            while writer.line.inspect()["sentFrames"] < 2:
                await asyncio.sleep(0)
        await asyncio.wait_for(delivered(), 1)
        self.assertEqual(writer.frames()[-1]["sequence"], 1)
        await watch.aclose()
        self.assertTrue(stream.closed)
        self.assertIsNotNone(channel.input_owner())

    async def test_capsule_expiry_cannot_reset_and_independent_watch_survives(self):
        channel, _ = await self.channel()
        watch = await channel.watch(["owner", 1, "f" * 64], startup_deadline_ms=boottime_ms() + 15000)
        now = boottime_ms()
        capsule = channel.begin_acquisition(deadline_ms=now + 100)
        with patch("mesh_plus.sync.relay.boottime_ms", return_value=now + 100):
            with self.assertRaisesRegex(ProtocolError, "sync_acquisition_deadline"):
                await capsule.head_after_nonce({"nonce": "b" * 64, "target": "f" * 64,
                                               "request": sha256(canonical(self.request())).hexdigest()})
        with self.assertRaisesRegex(ProtocolError, "sync_relay_busy"):
            channel.begin_acquisition(deadline_ms=boottime_ms() + 1000)
        await capsule.aclose()
        self.assertFalse(watch._closed)
        later = channel.begin_acquisition(deadline_ms=boottime_ms() + 1000)
        await later.aclose()
        await watch.aclose()

    async def test_aliases_have_distinct_wrappers_and_no_shared_ref_capability(self):
        other_binding = source_binding("fixture", "second", self.profile.descriptor)
        other = create_sync_relay(self.source, self.profile.descriptor, other_binding,
                                  native_codec=self.codec, budgets=SyncBudgets(), ledger=self.ledger,
                                  owns_source=False)
        try:
            self.assertNotEqual(other.bridge_id, self.relay.bridge_id)
            with self.assertRaises(AttributeError):
                other.bridge_id = self.relay.bridge_id
            line = LineChannel(None, Writer(), "client")
            channel2 = await other.open_channel(line, self.request(bridgeId=other.bridge_id),
                                                setup_deadline_ms=boottime_ms() + 1000)
            channel1, writer1 = await self.channel()
            one = channel1.begin_acquisition(deadline_ms=boottime_ms() + 1000)
            two = channel2.begin_acquisition(deadline_ms=boottime_ms() + 1000)
            await asyncio.gather(one.baseline(), two.baseline())
            first = writer1.frames()[-1]["payload"]["sourceTag"]
            second = line.writer.frames()[-1]["payload"]["sourceTag"]
            self.assertEqual(first["native"], second["native"])
            self.assertNotEqual(first["root"], second["root"])
            await one.aclose()
            await two.aclose()
        finally:
            await other.aclose()
        self.assertFalse(self.source.closed)

    async def test_at_limit_refuses_receive_before_buffer_creation(self):
        channel, writer = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 1000)
        remainder = self.ledger.maximum - self.ledger.used - self.ledger.reserved
        with self.ledger.reserve(remainder):
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                await capsule.baseline()
            self.assertEqual(self.source.sessions[0].packets, [])
            self.assertEqual(len(writer.frames()), 1)
        await capsule.aclose()

    async def test_held_failure_does_not_keep_scanner_ticket_or_input(self):
        channel, _ = await self.channel()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 1000)
        refs, errors = [], []
        original = ScanTicket.__init__
        def initialize(ticket, document, credit):
            original(ticket, document, credit)
            refs.append(weakref.ref(ticket))
        document = decode(self.source.raw)
        document["descriptor"] = {"wrong": "descriptor"}
        self.source.raw = canonical(document) + b"\n"
        with patch.object(ScanTicket, "__init__", initialize):
            try:
                await capsule.baseline()
            except ProtocolError as error:
                errors.append(error)
        await capsule.aclose()
        await channel.aclose()
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(refs), 1)
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertTrue(all(self.retired(packet.data) for packet in self.source.sessions[0].packets))
        self.assertFalse(gc.isenabled())

    async def test_real_owned_ipc_preserves_strict_single_line_native_fragment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "relay.sock")
            received = asyncio.get_running_loop().create_future()
            async def sink(reader, writer):
                try:
                    setup = await reader.readline()
                    delivery = await reader.readline()
                    received.set_result((setup, delivery))
                finally:
                    writer.close()
                    await writer.wait_closed()
            server = await asyncio.start_unix_server(sink, path)
            reader, writer = await asyncio.open_unix_connection(path)
            line = LineChannel(reader, writer, "client")
            channel = await self.relay.open_channel(line, self.request(), setup_deadline_ms=boottime_ms() + 1000)
            capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 1000)
            try:
                await capsule.baseline()
                setup, frame = await asyncio.wait_for(received, 1)
                self.assertEqual(decode(setup)["kind"], "setup")
                self.assertEqual(frame.count(b"\n"), 1)
                self.assertIn(self.source.raw[:-1], frame)
                self.assertEqual(line.inspect()["sentFrames"], 2)
            finally:
                await capsule.aclose()
                await channel.aclose()
                server.close()
                await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
