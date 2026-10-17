"""Controlled two-IPC relay/profile probe; no installed/fleet/perf acceptance."""

import argparse
import asyncio
import gc
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mesh-source", type=Path, required=True)
parser.add_argument("--observer-source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
mesh, observer = args.mesh_source.resolve(), args.observer_source.resolve()
sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]

from agent_observer.mesh_sync_profile import AgentSyncProfile  # noqa: E402
from agent_observer.sync_source import CachedAgentSyncSource  # noqa: E402
from agent_observer.sync_transport import AgentSyncTransportCodec  # noqa: E402
from test_sync_service_delivery import seeded  # noqa: E402

from mesh_plus.protocol import ProtocolError  # noqa: E402
from mesh_plus.sync import OwnedSyncCache, SyncBudgets, create_sync_relay, source_binding  # noqa: E402
from mesh_plus.sync.budget import AllocationLedger  # noqa: E402
from mesh_plus.sync.canonical import canonical, decode  # noqa: E402
from mesh_plus.transport import LineChannel, boottime_ms  # noqa: E402

outcomes = []


class RelaySourceTests(unittest.IsolatedAsyncioTestCase):
    async def probe(self, view, *, invalid=False):
        owner = seeded()  # Owned synthetic ServiceState, no provider or service.
        ledger = AllocationLedger()
        source = relay = channel = capsule = reader = None
        handlers, received = set(), asyncio.Queue()
        original_gc = gc.isenabled()
        gc.disable()
        errors = []
        with tempfile.TemporaryDirectory() as directory:
            native_path = Path(directory) / "native.sock"
            relay_path = Path(directory) / "mesh.sock"

            async def native_input(input_reader, writer):
                handlers.add(asyncio.current_task())
                try:
                    request = json.loads(await input_reader.readline())
                    if request["operation"] == "baseline":
                        raw = owner.sync_baseline(view)
                        if invalid:
                            document = json.loads(raw)
                            # Closed JSON envelope and unchanged claimed roots;
                            # only independent material admission may reject it.
                            document["tables"]["bodies"][0][1] = {"bad": "domain" + "x" * 200000}
                            raw = canonical(document) + b"\n"
                    else:
                        self.assertEqual(request["operation"], "head")
                        raw = owner.sync_head(view, request["challenge"])
                    writer.write(raw)
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()
                    handlers.discard(asyncio.current_task())

            async def relay_output(input_reader, writer):
                handlers.add(asyncio.current_task())
                try:
                    while raw := await input_reader.readline():
                        await received.put(raw)
                finally:
                    writer.close()
                    await writer.wait_closed()
                    handlers.discard(asyncio.current_task())

            native_server = await asyncio.start_unix_server(native_input, native_path)
            native_path.chmod(0o600)
            output_server = await asyncio.start_unix_server(relay_output, relay_path, limit=8470528)
            try:
                source = CachedAgentSyncSource("fixture", native_path, view=view, timeout=2)
                profile = AgentSyncProfile(profile_schema_digest="a" * 64, view=view)
                codec = AgentSyncTransportCodec(view, encoding_id="fixture-expanded/1", expected_host="fixture")
                binding = source_binding("fixture", "agents", profile.descriptor)
                relay = create_sync_relay(source, profile.descriptor, binding, native_codec=codec,
                                          budgets=SyncBudgets(), ledger=ledger)
                request = {"readerEpoch": "a" * 32, "requestId": "source-compatibility",
                           "catalogRevision": "fixture", "hosts": ["fixture"], "route": "owned-ipc",
                           "channelEpoch": "c" * 32, "bridgeId": relay.bridge_id, "role": "transport-relay",
                           "encodingDigest": hashlib.sha256(canonical(dict(codec.encoding))).hexdigest()}
                input_reader, writer = await asyncio.open_unix_connection(relay_path)
                channel = await relay.open_channel(LineChannel(input_reader, writer, "client"), request,
                                                   setup_deadline_ms=boottime_ms() + 15000)
                setup = decode(await asyncio.wait_for(received.get(), 2))
                self.assertEqual(setup["role"], "transport-relay")
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                await capsule.baseline()
                material_line = await asyncio.wait_for(received.get(), 2)
                self.assertEqual(material_line.count(b"\n"), 1)
                material = decode(material_line)
                self.assertEqual(material["sequence"], 1)
                if not invalid:
                    self.assertIn(owner.sync_baseline(view)[:-1], material_line)
                raw = canonical(material["payload"]["native"])
                reader_clock = {"bootId": "fixture-reader", "timeNamespace": "time:999"}
                reader = OwnedSyncCache(profile, binding, request_binding=request, _clock=reader_clock)
                if invalid:
                    try:
                        reader.admit_baseline(raw)
                    except ProtocolError as error:
                        errors.append(error)  # held across cleanup, with GC off
                    self.assertEqual(len(errors), 1)
                else:
                    candidate = reader.admit_baseline(raw)
                    with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                        reader.acquire()
                    # Test-only nonce fixture, as used by Mesh's source tests;
                    # all subsequent proof construction uses public relay APIs.
                    challenge = reader._proof_request(candidate)
                    await capsule.head_after_nonce(challenge)
                    proof = decode(await asyncio.wait_for(received.get(), 2))
                    self.assertEqual(proof["sequence"], 2)
                    view_ref = reader.confirm(candidate, canonical(proof["payload"]), reader_clock)
                    context = view_ref.context(boottime_ms(), reader_clock)
                    self.assertEqual(context["status"], "confirmed")
                    self.assertTrue(any(receipt["current"] for receipt in context["receipts"]))
                outcomes.append({"view": view, "invalidMaterial": invalid,
                                 "records": len(material["payload"]["native"]["tables"]["records"]),
                                 "materialLineBytes": len(material_line), "ledgerPeakBytes": ledger.peak})
            finally:
                if capsule is not None:
                    await capsule.aclose()
                if channel is not None:
                    await channel.aclose()
                if relay is not None:
                    await relay.aclose()
                if source is not None:
                    await source.aclose()
                if reader is not None:
                    reader.close()
                    self.assertEqual(reader.ledger.used + reader.ledger.reserved + reader.ledger.encoded +
                                     reader.ledger.encoded_reserved, 0)
                owner._sync_cache.close()  # test-owned native fixture retirement
                native_server.close()
                output_server.close()
                await native_server.wait_closed()
                await output_server.wait_closed()
                if handlers:
                    await asyncio.wait_for(asyncio.gather(*tuple(handlers)), 2)
                self.assertEqual(ledger.used + ledger.reserved + ledger.encoded + ledger.encoded_reserved, 0)
                self.assertFalse(gc.isenabled())
                if original_gc:
                    gc.enable()

    async def test_full(self):
        await self.probe("full")

    async def test_active(self):
        await self.probe("active")

    async def test_full_invalid_material(self):
        await self.probe("full", invalid=True)

    async def test_active_invalid_material(self):
        await self.probe("active", invalid=True)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RelaySourceTests))
loaded = {}
for module in tuple(sys.modules.values()):
    filename = getattr(module, "__file__", None)
    if filename and Path(filename).suffix == ".py":
        path = Path(filename).resolve()
        for label, root in (("mesh", mesh), ("observer", observer)):
            if path.is_relative_to(root):
                loaded[label + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
report = {"python": sys.version.split()[0], "testsRun": result.testsRun,
          "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
          "cases": outcomes, "loadedInputs": loaded,
          "exclusions": ["No installed package/native provider/service, fixed SSH, hello/controller dispatcher, "
                         "transaction completion, performance/RSS/aggregate capacity acceptance",
                         "Test-owned fixture input, output capture and semantic oracle storage outside relay ledger",
                         "Private test-only Reader nonce builder and native fixture close explicitly disclosed"]}
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x") as output:
    json.dump(report, output, indent=2, sort_keys=True)
    output.write("\n")
raise SystemExit(0 if result.wasSuccessful() else 1)
