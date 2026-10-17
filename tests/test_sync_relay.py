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
        self.block.set()
        self.limits = (16384, 65536)

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

    async def drain(self):
        await self.block.wait()
        if not self.closed:
            self.fragments.append(bytes(self.pending))
        self.pending = None

    def close(self):
        self.closed, self.pending = True, None
        self.block.set()

    async def wait_closed(self):
        pass

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

    def close(self):
        self.data.close()
        self.document = None
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
        return tuple(self.seal(raw) for raw in self.source.chain)

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
        self.refs.clear()
        self.packets.clear()


class Source:
    def __init__(self, profile):
        self.profile = profile
        raw, self.maps, self.tag = baseline(profile)
        self.raw, self.chain, self.moved = raw + b"\n", [], None
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
        writer.reached.clear()
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        job = asyncio.create_task(capsule.baseline())
        await writer.reached.wait()
        before = self.ledger.encoded_reserved
        self.assertGreaterEqual(before, len(self.source.raw))
        job.cancel()
        job.cancel()
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
        self.assertEqual([frame["sequence"] for frame in writer.frames()[1:]], [1, 2, 3, 4])
        await capsule.aclose()
        other, writer2 = await self.channel()
        self.source.chain[-1] = self.source.chain[0]
        capsule = other.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_relay_chain"):
            await capsule.changes(self.source.tag, target=tag)
        self.assertEqual(len(writer2.frames()), 1)
        self.assertTrue(all(self.retired(ref) for ref in self.source.sessions[-1].refs))
        await capsule.aclose()

    @staticmethod
    def retired(ref):
        try:
            _ = ref.nbytes
            return False
        except ProtocolError:
            return True

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
        watch = await channel.watch(["owner", 1, "f" * 64], startup_deadline_ms=boottime_ms() + 15000)
        capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
        with self.assertRaisesRegex(ProtocolError, "sync_relay_busy"):
            await capsule.baseline()
        await capsule.aclose()
        ref = self.source.sessions[0].seal(self.source.raw)
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
