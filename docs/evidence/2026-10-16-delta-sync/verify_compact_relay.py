"""Synthetic native Runtime -> compact source -> byte relay -> independent Reader.

The controller is trusted test code. Capture buffers, native owner and semantic
oracles are outside relay accounting. Only nonce setup and native fixture close
use private test helpers. This does not qualify aggregate resources or rollout.
"""

import argparse
import asyncio
import gc
import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ENV = None
OUTCOMES = []


class Case:
    def __init__(self, test, view="full", *, source_compact=True, transport_compact=True):
        self.test, self.view = test, view
        self.source_compact, self.transport_compact = source_compact, transport_compact
        self.owner = ENV.State(host_scope="fixture", configs={"codex": ("/fixture/codex", "explicit")},
                               sync_serialization="compact")
        self.owner.attempt("codex", "history")
        self.owner.accept("codex", "history", ENV.snapshot(), sampled_ms=self.owner.clock(),
                          ttl_ms=60000, runtime_ttl_ms=60000)
        self.ledger = ENV.Ledger()
        self.received, self.handlers, self.patches, self.sent = asyncio.Queue(), set(), [], {}
        self.source = self.relay = self.reader = self.capsule = None
        self.runtime = self.server = self.directory = None
        self.fault_baseline = False

    def capture(self, operation):
        original = getattr(self.owner, "sync_" + operation)

        def captured(*args, **kwargs):
            result = original(*args, **kwargs)
            if operation == "baseline" and self.fault_baseline:
                value = ENV.decode(result)
                value["tables"]["bodies"][0][1][2] = {"opaque": "x" * 200000}
                result = ENV.canonical(value) + b"\n"
            if operation == "changes":
                # Keep a noncanonical exact original completion fragment.
                result = (*result[:-1], result[-1][:-1] + b"  \n")
            self.sent.setdefault(operation, []).append(result)
            return result

        handle = patch.object(self.owner, "sync_" + operation, new=captured)
        handle.start()
        self.patches.append(handle)

    async def start(self):
        for operation in ("baseline", "changes", "head"):
            self.capture(operation)
        self.runtime = ENV.Running(state=self.owner)
        self.runtime.__enter__()
        self.directory = tempfile.TemporaryDirectory()
        output_path = Path(self.directory.name) / "mesh.sock"

        async def output(reader, writer):
            task = asyncio.current_task()
            self.handlers.add(task)
            try:
                while raw := await reader.readline():
                    self.test.assertTrue(raw.endswith(b"\n"))
                    await self.received.put(raw)
            finally:
                writer.close()
                await writer.wait_closed()
                self.handlers.discard(task)

        self.server = await asyncio.start_unix_server(output, output_path, limit=8470528)
        self.profile = ENV.Profile(profile_schema_digest="a" * 64, view=self.view)
        transport = ENV.Transport if self.transport_compact else ENV.ExpandedTransport
        self.codec = transport(self.view, encoding_id="fixture-compact/1", expected_host="fixture")
        self.binding = ENV.binding("fixture", "agents", self.profile.descriptor)
        source = ENV.Source if self.source_compact else ENV.ExpandedSource
        self.source = source("fixture", self.runtime.path, view=self.view, timeout=2)
        self.relay = ENV.relay(self.source, self.profile.descriptor, self.binding,
                               native_codec=self.codec, budgets=ENV.Budgets(), ledger=self.ledger)
        self.request = {"readerEpoch": "a" * 32, "requestId": "compact-native-relay",
                        "catalogRevision": "fixture", "hosts": ["fixture"], "route": "owned-ipc",
                        "channelEpoch": "c" * 32, "bridgeId": self.relay.bridge_id,
                        "role": "transport-relay",
                        "encodingDigest": hashlib.sha256(ENV.canonical(dict(self.codec.encoding))).hexdigest()}
        reader, writer = await asyncio.open_unix_connection(output_path)
        self.channel = await self.relay.open_channel(ENV.Line(reader, writer, "client"), self.request,
                                                     setup_deadline_ms=ENV.now() + 15000)
        setup = ENV.decode(await self.next_line())
        self.test.assertEqual(setup["kind"], "setup")
        self.test.assertEqual(setup["requestBinding"], self.request)
        self.capsule = self.channel.begin_acquisition(deadline_ms=ENV.now() + 15000)
        self.clock = {"bootId": "fixture-reader", "timeNamespace": "time:999"}
        self.reader = ENV.Cache(self.profile, self.binding, request_binding=self.request,
                                native_codec=ENV.Native(self.view, encoding_id="fixture-compact/1",
                                                        expected_host="fixture"), _clock=self.clock)
        return self

    async def next_line(self):
        return await asyncio.wait_for(self.received.get(), 2)

    def fragment(self, line, *, head=False):
        # R4 appends this native field last, then exactly two object closers/LF.
        # Extract from RECEIVED bytes, independently of the owner capture.
        field = b',"head":' if head else b',"native":'
        payload = ENV.decode(line)["payload"]
        name = "head" if head else "native"
        header = {key: value for key, value in payload.items() if key != name}
        marker = b',"payload":' + ENV.canonical(header)[:-1] + field
        # SourceTag itself contains a native key; anchor to the whole bounded
        # payload header rather than the first matching field name.
        start = line.index(marker) + len(marker)
        self.test.assertTrue(line.endswith(b"}}\n"))
        raw = line[start:-3] + b"\n"
        self.test.assertEqual(ENV.decode(raw), payload[name])
        return raw

    def exact(self, line, raw, *, head=False):
        self.test.assertTrue(raw.endswith(b"\n"))
        self.test.assertEqual(self.fragment(line, head=head), raw)

    async def baseline(self):
        await self.capsule.baseline()
        line = await self.next_line()
        self.exact(line, self.sent["baseline"][-1])
        return self.reader.admit_baseline(self.fragment(line))

    async def confirm(self, candidate):
        challenge = self.reader._proof_request(candidate)  # disclosed test-only nonce setup
        await self.capsule.head_after_nonce(challenge)
        line = await self.next_line()
        self.exact(line, self.sent["head"][-1], head=True)
        proof = ENV.decode(line)["payload"]
        self.test.assertEqual(proof["head"]["challenge"], challenge)
        confirmed = self.reader.confirm(candidate, ENV.canonical(proof), self.clock)
        self.test.assertEqual(confirmed.export_committed(),
                              self.owner.snapshot if self.view == "full" else self.owner.active_projection)
        return confirmed

    def advance(self, count):
        if count == 1:
            self.owner.attempt("codex", "history")
        elif count == 4:
            for index in range(2):
                value = ENV.snapshot()
                value["sessions"][0]["title"] = f"compact relay {index}"
                self.owner.attempt("codex", "history")
                self.test.assertTrue(self.owner.accept("codex", "history", value,
                                                       sampled_ms=self.owner.clock(), ttl_ms=60000,
                                                       runtime_ttl_ms=60000))

    async def close(self):
        if self.capsule is not None:
            await self.capsule.aclose()
        if self.relay is not None:
            await self.relay.aclose()
        if self.source is not None:
            await self.source.aclose()
            self.test.assertEqual(self.source.inspect()["activeSessions"], 0)
            self.test.assertEqual(self.source.inspect()["activeSockets"], 0)
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        if self.handlers:
            await asyncio.wait_for(asyncio.gather(*tuple(self.handlers)), 2)
        if self.reader is not None:
            self.reader.close()
            self.test.assertEqual(tuple(getattr(self.reader.ledger, name) for name in
                                        ("used", "reserved", "encoded", "encoded_reserved",
                                         "pending_units", "pending_encoded")), (0,) * 6)
        self.test.assertEqual(tuple(getattr(self.ledger, name) for name in
                                    ("used", "reserved", "encoded", "encoded_reserved", "pending_units")), (0,) * 5)
        if self.runtime is not None:
            self.runtime.__exit__()
            self.runtime = None
        for handle in reversed(self.patches):
            handle.stop()
        self.patches.clear()
        if self.owner._sync_cache is not None:  # owning fixture retirement only
            account = self.owner._sync_cache.account
            self.owner._sync_cache.close()
            self.test.assertEqual(account.snapshot()["used"], account.snapshot()["base"])
        if self.directory is not None:
            self.directory.cleanup()


class CompactRelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cases, self.errors = [], []
        self.assertFalse(gc.isenabled())

    async def asyncTearDown(self):
        for case in self.cases:
            await case.close()
        self.assertFalse(gc.isenabled())

    async def case(self, *args, **kwargs):
        case = Case(self, *args, **kwargs)
        self.cases.append(case)
        return await case.start()

    async def test_full_active_zero_one_four_original_bytes_and_two_fresh_native_proofs(self):
        for view in ("full", "active"):
            for count in (0, 1, 4):
                with self.subTest(view=view, count=count):
                    case = await self.case(view)
                    candidate = await case.baseline()
                    base = candidate.tag.native.wire()
                    with self.assertRaises(ENV.Error):
                        case.reader.acquire()
                    await case.confirm(candidate)
                    case.advance(count)
                    target = case.owner.sync_current_tag(view)
                    await case.capsule.changes(base, target=target)
                    originals = case.sent["changes"][-1]
                    self.assertEqual(len(originals), count + 1)
                    terminal = None
                    for index, original in enumerate(originals):
                        line = await case.next_line()
                        case.exact(line, original)
                        delivery = ENV.decode(line)
                        payload = delivery["payload"]
                        self.assertEqual(delivery["sequence"], index + 3)
                        self.assertEqual(payload["kind"], "material" if index < count else "control")
                        if index < count:
                            candidate = case.reader.stage(case.fragment(line))
                        else:
                            terminal = payload["native"]
                    self.assertEqual(candidate.tag.native.wire(), list(target))
                    if count:
                        with self.assertRaises(ENV.Error):
                            case.reader.acquire()
                    # Even an original valid completion is not a fresh proof.
                    case.reader._proof_request(candidate)
                    with self.assertRaisesRegex(ENV.Error, "sync_proof_shape") as failed:
                        case.reader.confirm(candidate, ENV.canonical(terminal), case.clock)
                    self.errors.append(failed.exception)
                    with self.assertRaises(ENV.Error):
                        case.reader.acquire()
                    await case.confirm(candidate)
                    OUTCOMES.append({"case": "compact-native-relay-reader", "view": view,
                                     "transactions": count, "originalFragmentsEqual": True,
                                     "freshActualHeadProofs": 2, "completionAsProof": "rejected",
                                     "target": list(target), "readerFinalCounters": [0] * 6,
                                     "relayFinalCounters": [0] * 5})

    async def test_wrong_source_or_transport_codec_rejects_before_material_prefix(self):
        for source, transport in ((False, True), (True, False)):
            with self.subTest(sourceCompact=source, transportCompact=transport):
                case = await self.case(source_compact=source, transport_compact=transport)
                try:
                    await case.capsule.baseline()
                except ENV.Error as error:
                    self.errors.append(error)
                else:
                    self.fail("wrong source/transport codec accepted compact material")
                await asyncio.sleep(0)
                self.assertEqual(case.received.qsize(), 0)
                with self.assertRaises(ENV.Error):
                    case.reader.acquire()
                OUTCOMES.append({"case": "wrong-explicit-codec", "sourceCompact": source,
                                 "transportCompact": transport, "materialFrames": 0})

    async def test_opaque_invalid_body_crosses_relay_but_independent_reader_rejects(self):
        case = await self.case()
        case.fault_baseline = True
        await case.capsule.baseline()
        line = await case.next_line()
        case.exact(line, case.sent["baseline"][-1])
        native = ENV.decode(line)["payload"]["native"]
        try:
            case.reader.admit_baseline(case.fragment(line))
        except ENV.Error as error:
            self.assertEqual(str(error), "sync_compact_value_shape")
            self.errors.append(error)
        else:
            self.fail("Reader admitted opaque invalid compact body")
        with self.assertRaises(ENV.Error):
            case.reader.acquire()
        self.assertEqual(len(native["tables"]["bodies"][0][1][2]["opaque"]), 200000)
        OUTCOMES.append({"case": "opaque-invalid-body", "characters": 200000,
                         "originalFragmentEqual": True, "readerAdmission": "rejected",
                         "readerRejection": str(self.errors[-1])})


def main():
    global ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    paths = [str(mesh / "src"), str(observer), str(observer / "tests")]
    sys.path[:0] = paths
    os.environ["PYTHONPATH"] = os.pathsep.join(paths)
    gc.disable()
    sync = importlib.import_module("mesh_plus.sync")
    transport = importlib.import_module("mesh_plus.transport")
    canonical = importlib.import_module("mesh_plus.sync.canonical")
    ENV = SimpleNamespace(
        State=importlib.import_module("agent_observer.service_state").ServiceState,
        Running=importlib.import_module("test_service_runtime").Running,
        snapshot=importlib.import_module("test_service_runtime").scoped_snapshot,
        Source=importlib.import_module("agent_observer.sync_compact_source").CachedCompactAgentSyncSource,
        ExpandedSource=importlib.import_module("agent_observer.sync_source").CachedAgentSyncSource,
        Transport=importlib.import_module("agent_observer.sync_compact_acquisition").CompactAgentSyncTransportCodec,
        ExpandedTransport=importlib.import_module("agent_observer.sync_transport").AgentSyncTransportCodec,
        Native=importlib.import_module("agent_observer.mesh_sync_codec").AgentCompactSyncCodec,
        Profile=importlib.import_module("agent_observer.mesh_sync_profile").AgentSyncProfile,
        Ledger=importlib.import_module("mesh_plus.sync.budget").AllocationLedger,
        Error=importlib.import_module("mesh_plus.protocol").ProtocolError,
        relay=sync.create_sync_relay, Cache=sync.OwnedSyncCache, Budgets=sync.SyncBudgets,
        binding=sync.source_binding, Line=transport.LineChannel, now=transport.boottime_ms,
        canonical=canonical.canonical, decode=canonical.decode,
    )
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CompactRelayTests)
    with args.log.open("x") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    assert not gc.isenabled()
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or Path(filename).suffix != ".py":
            continue
        path = Path(filename).resolve()
        for label, root in (("mesh", mesh), ("observer", observer)):
            if path.is_relative_to(root):
                loaded[label + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"python": sys.version.split()[0], "testsRun": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
              "cyclicGC": "disabled before imports; held errors; no explicit collection",
              "meshExport": str(mesh), "observerExport": str(observer), "loadedInputs": loaded,
              "cases": OUTCOMES,
              "scope": "small synthetic actual Runtime/compact source+scanner/relay/two IPC/independent Reader with trusted direct test controller",
              "exclusions": ["No ordinary controller/carrier grammar, authentication/bootstrap, fixed SSH or installed pair.",
                             "Separate owner, capture/oracle and Reader/relay ledgers do not establish aggregate32/64/RSS/CPU/dense2k/recovery.",
                             "No consuming-pin registry closure, populated native provider, schema/ID allocation/freeze, artifact/selection or rollout."]}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips")}))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 3 and not result.skipped else 1)


if __name__ == "__main__":
    main()
