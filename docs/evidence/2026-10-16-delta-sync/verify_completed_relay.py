"""Controlled actual source-to-relay completion checks; no rollout or CPU claim.

Two disposable Unix sockets carry synthetic ServiceState bytes and real Mesh
output. A writer wrapper supplies deterministic drain/failure boundaries. Its
capture buffers, owner fixtures and semantic oracle are outside relay accounting.
Only Reader nonce setup and native fixture retirement use private test helpers.
"""

import argparse
import asyncio
import gc
import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ENV = None
OUTCOMES = []
OWNER_MODULES = (
    "test_sync_completed_changes", "test_mesh_sync_codec", "test_sync_compact_plan",
    "test_sync_compact", "test_sync_compact_transport", "test_mesh_sync_profile",
    "test_mesh_sync_read", "test_sync_owned_source", "test_sync_source",
    "test_sync_transport", "test_sync_acquisition",
)


class CapturedSession:
    """Transparent public delegation, with bounded test-owned result aliases."""

    def __init__(self, actual):
        self.actual, self.batch, self.refs = actual, None, ()

    def __getattr__(self, name):
        return getattr(self.actual, name)

    async def changes_with_completion(self, *args, **kwargs):
        result = await self.actual.changes_with_completion(*args, **kwargs)
        rows = getattr(result, "transactions", None)
        self.refs = (result.data,) if rows is None else (*rows, result.completion.data)
        self.batch = result
        return result  # identity preserved, no fallback/copy/reseal or added await


class CapturedSource:
    def __init__(self, actual):
        self.actual, self.sessions = actual, []

    def open_session(self, inputs):
        session = CapturedSession(self.actual.open_session(inputs))
        self.sessions.append(session)
        return session

    async def aclose(self):
        await self.actual.aclose()


class GatedWriter:
    """Real StreamWriter plus deterministic, bounded test-owned I/O gates."""

    def __init__(self, actual):
        self.actual, self.transport = actual, actual.transport
        self.pending = self.hold = self.fail = None
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.close_started, self.close_release = asyncio.Event(), asyncio.Event()
        self.close_release.set()

    def write(self, value):
        self.pending = value
        self.actual.write(value)
        if self.fail is not None and value == self.fail:
            raise OSError("controlled partial write failure")

    async def drain(self):
        try:
            if self.hold is not None and self.pending == self.hold:
                self.entered.set()
                await self.release.wait()
            await self.actual.drain()
        finally:
            self.pending = None

    def close(self):
        self.pending = None
        self.actual.close()
        self.close_started.set()

    async def wait_closed(self):
        await self.actual.wait_closed()
        await self.close_release.wait()


class Case:
    def __init__(self, test, view="full", count=1):
        self.test, self.view, self.count = test, view, count
        self.owner = ENV.seeded()
        self.ledger = ENV.Ledger()
        self.handlers, self.jobs, self.lines, self.partial = set(), [], [], []
        self.received, self.sent = asyncio.Queue(), {}
        self.transform = None
        self.fail_control = False
        self.capsule = self.reader = self.relay = self.source = self.writer = None
        self.native_server = self.output_server = self.directory = None
        self.closed = False

    async def start(self):
        self.directory = tempfile.TemporaryDirectory()
        native_path = Path(self.directory.name) / "native.sock"
        output_path = Path(self.directory.name) / "mesh.sock"

        async def native(reader, writer):
            self.handlers.add(asyncio.current_task())
            try:
                request = json.loads(await reader.readline())
                operation = request["operation"]
                if operation == "baseline":
                    frames = (self.owner.sync_baseline(self.view),)
                elif operation == "changes":
                    frames = self.owner.sync_changes(self.view, request["baseTag"], request["targetTag"])
                    self.test.assertIs(type(frames), tuple)
                else:
                    self.test.assertEqual(operation, "head")
                    frames = (self.owner.sync_head(self.view, request["challenge"]),)
                if self.transform is not None:
                    frames = self.transform(operation, frames)
                self.sent[operation] = frames
                if operation == "changes" and self.fail_control:
                    # Completion includes a freshly sampled clock; fault the
                    # actual bytes, not an earlier same-target control sample.
                    self.writer.fail = frames[-1][:-1]
                for raw in frames:
                    writer.write(raw)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                self.handlers.discard(asyncio.current_task())

        async def output(reader, writer):
            self.handlers.add(asyncio.current_task())
            try:
                while raw := await reader.readline():
                    if not raw.endswith(b"\n"):
                        # Failed output can terminate at a prefix/native fragment.
                        # Retain/count it, but never treat EOF as an LF frame.
                        self.partial.append(raw)
                        break
                    self.lines.append(raw)
                    await self.received.put(raw)
            finally:
                writer.close()
                await writer.wait_closed()
                self.handlers.discard(asyncio.current_task())

        self.native_server = await asyncio.start_unix_server(native, native_path)
        native_path.chmod(0o600)
        self.output_server = await asyncio.start_unix_server(output, output_path, limit=8470528)
        self.profile = ENV.Profile(profile_schema_digest="a" * 64, view=self.view)
        self.codec = ENV.Codec(self.view, encoding_id="fixture-expanded/1", expected_host="fixture")
        self.binding = ENV.binding("fixture", "agents", self.profile.descriptor)
        self.source = CapturedSource(ENV.Source("fixture", native_path, view=self.view, timeout=2))
        self.relay = ENV.relay(self.source, self.profile.descriptor, self.binding, native_codec=self.codec,
                               budgets=ENV.Budgets(), ledger=self.ledger)
        self.request = {"readerEpoch": "a" * 32, "requestId": "completed-source",
                        "catalogRevision": "fixture", "hosts": ["fixture"], "route": "owned-ipc",
                        "channelEpoch": "c" * 32, "bridgeId": self.relay.bridge_id,
                        "role": "transport-relay",
                        "encodingDigest": hashlib.sha256(ENV.canonical(dict(self.codec.encoding))).hexdigest()}
        self.channel = await self.open_channel()
        self.capsule = self.channel.begin_acquisition(deadline_ms=ENV.now() + 15000)
        await self.capsule.baseline()
        line = await self.next_line()
        self.base = ENV.decode(line)["payload"]["native"]["tag"]
        self.test.assertIn(self.sent["baseline"][0][:-1], line)
        self.reader_clock = {"bootId": "fixture-reader", "timeNamespace": "time:999"}
        self.reader = ENV.Cache(self.profile, self.binding, request_binding=self.request, _clock=self.reader_clock)
        self.candidate = self.reader.admit_baseline(ENV.canonical(ENV.decode(line)["payload"]["native"]))
        self.advance()
        self.target = self.owner.sync_current_tag(self.view)
        self.expected = self.owner.sync_changes(self.view, self.base, self.target)
        self.test.assertEqual(len(self.expected), self.count + 1)
        return self

    async def open_channel(self):
        reader, actual = await asyncio.open_unix_connection(self.directory.name + "/mesh.sock")
        writer = GatedWriter(actual)
        request = self.request if self.writer is None else {
            **self.request, "channelEpoch": "d" * 32, "requestId": "completed-source-sibling"}
        channel = await self.relay.open_channel(ENV.Line(reader, writer, "client"), request,
                                                setup_deadline_ms=ENV.now() + 15000)
        setup = ENV.decode(await self.next_line())
        self.test.assertEqual(setup["kind"], "setup")
        self.test.assertEqual(setup["requestBinding"], request)
        if self.writer is None:
            self.writer = writer
        return channel

    async def next_line(self):
        return await asyncio.wait_for(self.received.get(), 2)

    def advance(self):
        if self.count == 1:
            self.owner.attempt("codex", "history")
        elif self.count == 4:
            for index in range(2):
                value = ENV.snapshot()
                value["sessions"][0]["title"] = f"changed {index}"
                self.owner.attempt("codex", "history")
                self.test.assertTrue(self.owner.accept("codex", "history", value,
                                                       sampled_ms=self.owner.clock(), ttl_ms=60000,
                                                       runtime_ttl_ms=60000))

    async def changes(self, **kwargs):
        return await self.capsule.changes(self.base, target=self.target, **kwargs)

    def job(self):
        task = asyncio.create_task(self.changes())
        self.jobs.append(task)
        return task

    def assert_no_completion(self):
        self.test.assertFalse(any(ENV.decode(raw).get("payload", {}).get("kind") == "control"
                                  for raw in self.lines))

    async def sibling(self):
        channel = await self.open_channel()
        session = self.source.sessions[-1]
        ticket = await session.baseline()
        return channel, ticket

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.writer is not None:
            self.writer.release.set()
            self.writer.close_release.set()
        for task in self.jobs:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.jobs, return_exceptions=True)
        if self.capsule is not None:
            await self.capsule.aclose()
        if self.relay is not None:
            await self.relay.aclose()
        if self.source is not None:
            await self.source.aclose()
        if self.reader is not None:
            self.reader.close()
            self.test.assertEqual(tuple(getattr(self.reader.ledger, name) for name in
                                        ("used", "reserved", "encoded", "encoded_reserved", "pending_units")),
                                  (0, 0, 0, 0, 0))
        self.owner._sync_cache.close()  # owning synthetic fixture retirement only
        for server in (self.native_server, self.output_server):
            if server is not None:
                server.close()
                await server.wait_closed()
        if self.handlers:
            await asyncio.wait_for(asyncio.gather(*tuple(self.handlers)), 2)
        self.test.assertEqual(tuple(getattr(self.ledger, name) for name in
                                    ("used", "reserved", "encoded", "encoded_reserved", "pending_units")),
                              (0, 0, 0, 0, 0))
        if self.directory is not None:
            self.directory.cleanup()


class CompletedRelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cases, self.errors = [], []
        self.assertFalse(gc.isenabled())

    async def asyncTearDown(self):
        for case in self.cases:
            await case.close()
        self.assertFalse(gc.isenabled())

    async def case(self, view="full", count=1):
        case = Case(self, view, count)
        self.cases.append(case)
        return await case.start()

    async def test_full_active_zero_one_four_exact_bytes_independent_admission_and_fresh_proof(self):
        for view in ("full", "active"):
            for count in (0, 1, 4):
                with self.subTest(view=view, count=count):
                    case = await self.case(view, count)
                    # Preserve noncanonical completion whitespace without synthesis.
                    case.transform = lambda op, frames: (*frames[:-1], frames[-1][:-1] + b"  \n") if op == "changes" else frames
                    await case.changes()
                    lines = [await case.next_line() for _ in range(count + 1)]
                    for index, (line, original) in enumerate(zip(lines, case.sent["changes"], strict=True)):
                        self.assertIn(original[:-1], line)
                        payload = ENV.decode(line)["payload"]
                        self.assertEqual(payload["kind"], "material" if index < count else "control")
                        self.assertEqual(ENV.decode(line)["sequence"], index + 2)
                        if index < count:
                            case.candidate = case.reader.stage(ENV.canonical(payload["native"]))
                    self.assertEqual(case.candidate.tag.native.wire(), list(case.target))
                    with self.assertRaises(ENV.ProtocolError):
                        case.reader.acquire()
                    challenge = case.reader._proof_request(case.candidate)  # disclosed test-only nonce setup
                    await case.capsule.head_after_nonce(challenge)
                    proof = ENV.decode(await case.next_line())["payload"]
                    confirmed = case.reader.confirm(case.candidate, ENV.canonical(proof), case.reader_clock)
                    self.assertEqual(confirmed.export_committed(), case.owner.snapshot if view == "full" else case.owner.active_projection)
                    OUTCOMES.append({"case": "exact-source-relay-reader", "view": view,
                                     "transactions": count, "exactOriginalBytes": True,
                                     "freshProofRequired": True, "nativeTag": list(case.target)})
                    await case.close()

    async def test_native_control_boundary_rejects_before_prefix(self):
        for size in (16384, 16385, 65536):
            case = await self.case()
            def pad(op, frames):
                if op != "changes":
                    return frames
                raw = frames[-1]
                return (*frames[:-1], raw[:-1] + b" " * (size - len(raw)) + b"\n")
            case.transform = pad
            if size == 16384:
                await case.changes()
                lines = [await case.next_line(), await case.next_line()]
                self.assertIn(case.sent["changes"][-1][:-1], lines[-1])
                self.assertLessEqual(len(lines[-1]), 65536)
            else:
                with self.assertRaises(ENV.ProtocolError):
                    await case.changes()
                self.assertEqual(case.received.qsize(), 0)
                case.assert_no_completion()
            await case.close()

    async def test_wrong_or_missing_native_terminal_never_exposes_material_prefix(self):
        for mode in ("tag", "epoch", "heartbeat", "missing"):
            case = await self.case()
            sibling, ticket = await case.sibling()
            def corrupt(op, frames):
                if op != "changes":
                    return frames
                if mode == "missing":
                    return frames[:-1]
                value = ENV.decode(frames[-1])
                if mode == "tag":
                    value["tag"], value["cursor"][1:] = list(case.base), case.base[1:]
                elif mode == "epoch":
                    value["cursor"][0] = value["ownerClock"]["ownerEpoch"] = "00000000-0000-0000-0000-000000000008"
                else:
                    value["status"] = "heartbeat"
                return (*frames[:-1], ENV.canonical(value) + b"\n")
            case.transform = corrupt
            try:
                await case.changes()
            except ENV.ProtocolError as error:
                self.errors.append(error)
            else:
                self.fail("uncorrelated source completion forwarded")
            self.assertEqual(case.received.qsize(), 0)
            self.assertGreater(ticket.data.nbytes, 0)
            self.assertIsNotNone(sibling.input_owner())
            ticket.close()
            await case.close()

    async def test_recovery_forwards_exact_original_control_without_material_prefix(self):
        case = await self.case()
        def recover(op, frames):
            if op != "changes":
                return frames
            value = ENV.decode(frames[-1])
            value.update(status="baseline_required", reason="sync_missing_base")
            return (*frames[:-1], ENV.canonical(value) + b" \n")
        case.transform = recover
        await case.changes()
        line = await case.next_line()
        self.assertIn(case.sent["changes"][-1][:-1], line)
        self.assertEqual(ENV.decode(line)["payload"]["native"]["status"], "baseline_required")
        self.assertEqual(case.received.qsize(), 0)

    async def test_material_drain_keeps_original_batch_meta_and_all_pins_until_completion(self):
        case = await self.case(count=4)
        case.writer.hold = case.expected[0][:-1]
        task = case.job()
        await asyncio.wait_for(case.writer.entered.wait(), 2)
        session = case.source.sessions[0]
        self.assertEqual(session.batch.completion.status, "complete")
        self.assertGreaterEqual(case.ledger.encoded_reserved, sum(map(len, case.sent["changes"])))
        self.assertEqual(session.inspect()["ownedBatches"], 1)
        self.assertEqual(session.inspect()["ownedRefs"], 0)  # consuming-ref pruning exercised, batch still owns children
        self.assertEqual(case.received.qsize(), 0)
        case.assert_no_completion()
        case.writer.release.set()
        await task
        lines = [await case.next_line() for _ in range(5)]
        self.assertEqual(ENV.decode(lines[-1])["payload"]["kind"], "control")
        self.assertEqual(session.inspect()["ownedBatches"], 0)

    async def held_failure(self, *, close_source=False, cancel=False, fail_control=False):
        case = await self.case()
        sibling, ticket = await case.sibling()
        case.writer.close_release.clear()
        if close_source or cancel:
            case.writer.hold = case.expected[0][:-1]
        else:
            case.fail_control = fail_control
            if not fail_control:
                case.writer.fail = case.expected[0][:-1]
        task = case.job()
        if close_source or cancel:
            await asyncio.wait_for(case.writer.entered.wait(), 2)
            session = case.source.sessions[0]
            session.inspect()  # registry pruning must not defeat batch-scope retirement
            if close_source:
                await session.aclose()
                case.writer.release.set()
            else:
                task.cancel()
        await asyncio.wait_for(case.writer.close_started.wait(), 2)
        self.assertGreaterEqual(case.ledger.encoded_reserved, sum(map(len, case.sent["changes"])))
        self.assertFalse(task.done())
        self.assertGreater(ticket.data.nbytes, 0)
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
        self.assertFalse(task.done())
        case.writer.close_release.set()
        try:
            await task
        except (ENV.ProtocolError, asyncio.CancelledError) as error:
            self.errors.append(error)
        else:
            self.fail("failed output claimed completion")
        case.assert_no_completion()
        self.assertGreater(ticket.data.nbytes, 0)
        self.assertIsNotNone(sibling.input_owner())
        ticket.close()
        await case.close()
        OUTCOMES.append({"case": "held-output-failure", "sourceScopeClose": close_source,
                         "callerCancel": cancel, "failedControlWrite": fail_control,
                         "partialEofFragments": len(case.partial),
                         "partialEofBytes": sum(map(len, case.partial)),
                         "completeSuccessControls": 0, "finalFiveCounters": [0] * 5})

    async def test_source_scope_close_after_prune_revokes_batch_before_output_cleanup(self):
        await self.held_failure(close_source=True)

    async def test_caller_cancel_during_material_drain_preserves_pins_and_sibling(self):
        await self.held_failure(cancel=True)

    async def test_failed_material_and_control_write_preserves_pins_through_close(self):
        await self.held_failure(fail_control=False)
        await self.held_failure(fail_control=True)


def main():
    global ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    sync = importlib.import_module("mesh_plus.sync")
    transport = importlib.import_module("mesh_plus.transport")
    canonical = importlib.import_module("mesh_plus.sync.canonical")
    ENV = SimpleNamespace(
        Source=importlib.import_module("agent_observer.sync_source").CachedAgentSyncSource,
        Profile=importlib.import_module("agent_observer.mesh_sync_profile").AgentSyncProfile,
        Codec=importlib.import_module("agent_observer.sync_transport").AgentSyncTransportCodec,
        seeded=importlib.import_module("test_sync_service_delivery").seeded,
        snapshot=importlib.import_module("test_service_runtime").scoped_snapshot,
        Ledger=importlib.import_module("mesh_plus.sync.budget").AllocationLedger,
        ProtocolError=importlib.import_module("mesh_plus.protocol").ProtocolError,
        relay=sync.create_sync_relay, Cache=sync.OwnedSyncCache, Budgets=sync.SyncBudgets,
        binding=sync.source_binding, Line=transport.LineChannel, now=transport.boottime_ms,
        canonical=canonical.canonical, decode=canonical.decode,
    )
    gc.disable()
    owner = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in OWNER_MODULES)
    own = unittest.defaultTestLoader.loadTestsFromTestCase(CompletedRelayTests)
    assert owner.countTestCases() == 186
    assert own.countTestCases() == 8
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite((owner, own)))
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
              "owningComponentTests": 186, "meshActualSeamMethods": 8,
              "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
              "cyclicGC": "disabled; errors/handles held and counters checked without collection",
              "meshExport": str(mesh), "observerExport": str(observer), "loadedInputs": loaded,
              "cases": OUTCOMES,
              "scope": "controlled actual source/scanner/relay/native+Mesh IPC/Reader with synthetic ServiceState; no controller grammar, populated provider, aggregate capacity/RSS/CPU/installed pair or rollout acceptance"}
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__ == "__main__":
    main()
