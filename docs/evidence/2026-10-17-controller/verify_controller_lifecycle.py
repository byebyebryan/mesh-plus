"""Actual source/controller lifecycle under disclosed test-owned drain hooks."""

import argparse
import asyncio
import gc
import hashlib
import importlib
import json
import secrets
import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ENV = None
OUTCOMES = []


class SourceCapture:
    """Only public delegation; retained session inventory is test-owned."""

    def __init__(self, source):
        self.actual, self.sessions, self.inputs = source, [], []

    def open_session(self, inputs):
        session = self.actual.open_session(inputs)
        self.sessions.append(session)
        self.inputs.append(inputs)
        return session

    async def aclose(self):
        await self.actual.aclose()
        self.sessions.clear()
        self.inputs.clear()


class Client:
    def __init__(self, case):
        self.case = case
        self.reader = self.writer = self.carrier = self.server = self.cache = None
        self.command_id, self.delivery_id, self.capid = 0, 0, None
        self.candidate, self.last_result = None, None
        self.transactions = self.proofs = 0
        self.received = []  # excluded oracle copies, never production history

    async def start(self):
        case = self.case
        supplied, peer = socket.socketpair()
        self.carrier = ENV.sync.control_carrier_from_ipc(supplied, ledger=case.ledger)
        self.reader, self.writer = await asyncio.open_connection(sock=peer, limit=8470528)
        self.server = asyncio.create_task(ENV.sync.serve_sync_relay(
            case.relay, self.carrier, setup_deadline_ms=ENV.now() + 15000))
        await self.send(dict(protocol="mesh.state-sync/1", kind="hello", nonce="a" * 64))
        hello, _ = await self.read()
        case.test.assertEqual(hello["kind"], "hello")
        self.request = dict(readerEpoch=secrets.token_hex(16), requestId="controller-lifecycle",
                            catalogRevision="fixture", hosts=["fixture"], route="socket-pair",
                            channelEpoch=secrets.token_hex(16), bridgeId=hello["bridgeId"], role="transport-relay",
                            encodingDigest=hashlib.sha256(ENV.canonical(hello["encoding"])).hexdigest())
        self.digest = hashlib.sha256(ENV.canonical(self.request)).hexdigest()
        await self.send(dict(protocol="mesh.state-sync/1", kind="open", controllerVersion=1,
                             requestBinding=self.request, remainingMs=15000))
        setup, _ = await self.read()
        case.test.assertEqual(setup["kind"], "setup")
        self.clock = {"bootId": "fixture-reader", "timeNamespace": "time:999"}
        native = ENV.Native(case.view, encoding_id=case.encoding, expected_host="fixture") if case.compact else None
        self.cache = ENV.sync.OwnedSyncCache(case.profile, case.binding, request_binding=self.request,
                                            native_codec=native, _clock=self.clock)
        await self.begin()
        await self.command("baseline", acquisition=self.capid)
        await self.result()
        await self.head()
        return self

    async def send(self, value):
        self.writer.write(ENV.canonical(value) + b'\n')
        await self.writer.drain()

    async def command(self, operation, **fields):
        self.command_id += 1
        await self.send(dict(protocol="mesh.state-sync/1", kind="command", request=self.digest,
                             sequence=self.command_id, operation=operation, **fields))
        return self.command_id

    async def read(self):
        raw = await asyncio.wait_for(self.reader.readline(), 2)
        self.case.test.assertTrue(raw.endswith(b'\n'), raw[:100])
        value = ENV.decode(raw)
        self.received.append(raw)
        if value["kind"] == "delivery":
            self.delivery_id += 1
            self.case.test.assertEqual((value["sequence"], value["requestBinding"]), (self.delivery_id, self.request))
            payload = value["payload"]
            if "head" in payload:
                current = self.cache.confirm(self.candidate, ENV.canonical(payload), self.clock)
                expected = self.case.owner.active_projection if self.case.view == "active" else self.case.owner.snapshot
                self.case.test.assertEqual(current.export_committed(), expected)
                self.proofs += 1
            else:
                native = payload["native"]
                # Test oracle reserialization for independent Reader admission;
                # byte identity is covered by the frozen 24-scenario runner.
                if native["kind"] == "baseline":
                    self.candidate = self.cache.admit_baseline(ENV.canonical(native) + b'\n')
                elif native["kind"] == "transaction":
                    self.candidate = self.cache.stage(ENV.canonical(native) + b'\n')
                    self.transactions += 1
                else:
                    self.case.test.assertEqual(native["kind"], "control")
        elif value["kind"] == "command-result":
            self.case.test.assertEqual((value["request"], value["through"]), (self.digest, self.delivery_id))
            self.last_result = value
        return value, raw

    async def result(self, command=None):
        command = self.command_id if command is None else command
        while True:
            value, _ = await self.read()
            if value["kind"] == "command-result":
                self.case.test.assertEqual((value["command"], value["status"], value["code"]), (command, "ok", "none"))
                return value

    async def begin(self, remaining=15000):
        self.capid = await self.command("begin", remainingMs=remaining)
        return await self.result()

    async def head(self):
        challenge = self.cache._proof_request(self.candidate)  # disclosed private nonce fixture
        await self.command("head", acquisition=self.capid, challenge=challenge, remainingMs=2000)
        return await self.result()

    async def close(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        if self.server is not None:
            result = await asyncio.wait_for(asyncio.gather(self.server, return_exceptions=True), 2)
            self.case.test.errors.extend(x for x in result if isinstance(x, BaseException))
        if self.carrier is not None:
            await self.carrier.aclose()
        if self.cache is not None:
            self.cache.close()
            self.case.test.assertEqual(tuple(getattr(self.cache.ledger, key) for key in
                                            ("used", "reserved", "encoded", "encoded_reserved", "pending_units", "pending_encoded")), (0,) * 6)


class Case:
    def __init__(self, test, serialization, view):
        self.test, self.view, self.compact = test, view, serialization == "compact"
        self.serialization, self.clients = serialization, []
        self.owner = ENV.State(host_scope="fixture", configs={"codex": ("/fixture/codex", "explicit")},
                               sync_serialization=serialization)
        self.owner.attempt("codex", "history")
        self.owner.accept("codex", "history", ENV.snapshot(), sampled_ms=self.owner.clock(), ttl_ms=60000, runtime_ttl_ms=60000)
        self.runtime = ENV.Running(state=self.owner)
        self.runtime.__enter__()
        self.ledger = ENV.Ledger()
        self.profile = ENV.Profile(profile_schema_digest="a" * 64, view=view)
        self.binding = ENV.sync.source_binding("fixture", "agents", self.profile.descriptor)
        self.encoding = "fixture-compact/1" if self.compact else "fixture-expanded/1"
        self.codec = (ENV.CompactTransport if self.compact else ENV.Transport)(view, encoding_id=self.encoding, expected_host="fixture")
        source = (ENV.CompactSource if self.compact else ENV.Source)("fixture", self.runtime.path, view=view, timeout=2)
        self.source = SourceCapture(source)
        self.relay = ENV.sync.create_sync_relay(self.source, self.profile.descriptor, self.binding,
                                                native_codec=self.codec, budgets=ENV.sync.SyncBudgets(), ledger=self.ledger)

    async def client(self):
        client = Client(self)
        self.clients.append(client)
        return await client.start()

    def advance(self, count=4):
        if count == 1:
            self.owner.attempt("codex", "history")
        else:
            for index in range(2):
                value = ENV.snapshot()
                value["sessions"][0]["title"] = f"lifecycle {index}"
                self.owner.attempt("codex", "history")
                self.owner.accept("codex", "history", value, sampled_ms=self.owner.clock(), ttl_ms=60000, runtime_ttl_ms=60000)

    async def close(self):
        for client in self.clients:
            await client.close()
        await self.relay.aclose()
        self.test.assertEqual(tuple(getattr(self.ledger, key) for key in
                                    ("used", "reserved", "encoded", "encoded_reserved", "pending_units")), (0,) * 5)
        self.runtime.__exit__()
        account = self.owner._sync_cache.account
        self.owner._sync_cache.close()  # owning disposable fixture only
        self.test.assertEqual(account.snapshot()["used"], account.snapshot()["base"])


class Lifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.errors = []
        self.assertFalse(gc.isenabled())

    def physical_inventory(self, owner, ledger):
        # Disclosed test-only, bounded private physical-storage audit. It never
        # returns a raw buffer/record or participates in authority/admission.
        sizes, credits, consuming, revoked = [], set(), 0, 0
        for record in owner._buffers.values():
            self.assertIs(type(record.raw), bytes)
            self.assertIs(record.credit.ledger, ledger)
            self.assertFalse(record.credit.closed)
            self.assertEqual(len(record.raw), record.credit.encoded_amount)
            self.assertNotIn(id(record.credit), credits)
            credits.add(id(record.credit))
            sizes.append(len(record.raw))
            consuming += record.consuming is True
            revoked += record.revoked is True
        return dict(buffers=len(sizes), encodedBytes=sum(sizes), allCreditsDistinct=True,
                    consuming=consuming, revoked=revoked)

    async def test_actual_watch_survives_end_and_expiry_then_head_and_stop(self):
        for serialization in ("expanded", "compact"):
            for view in ("full", "active"):
                with self.subTest(serialization=serialization, view=view):
                    case = Case(self, serialization, view)
                    try:
                        client = await case.client()
                        watchid = await client.command("watch", acquisition=client.capid, cursor=list(case.owner.sync_cursor(view)))
                        await client.result()
                        await client.command("end", acquisition=client.capid)
                        await client.result()
                        self.assertEqual(case.source.actual.inspect()["activeWatches"], 1)
                        await client.begin(remaining=40)
                        await asyncio.sleep(.07)
                        self.assertEqual(case.source.actual.inspect()["activeWatches"], 1)
                        case.advance(1)
                        while client.transactions == 0:
                            await client.read()
                        await client.begin()
                        await client.head()
                        await client.command("stop-watch", acquisition=client.capid, watch=watchid)
                        await client.result()
                        self.assertEqual(case.source.actual.inspect()["activeWatches"], 0)
                        await client.command("end", acquisition=client.capid)
                        await client.result()
                        self.assertEqual(client.proofs, 2)
                        OUTCOMES.append(dict(test="watch-end-expiry-head-stop", serialization=serialization, view=view,
                                             actualFreshProofs=client.proofs, watchTransactions=client.transactions))
                    finally:
                        await case.close()

    async def test_actual_four_transaction_pins_cancellation_close_failure_and_sibling(self):
        for serialization in ("expanded", "compact"):
            for view in ("full", "active"):
                for mode in ("cancel-command", "server-cancel", "source-close", "write-failure"):
                    with self.subTest(serialization=serialization, view=view, mode=mode):
                        await self.held_case(serialization, view, mode)

    async def held_case(self, serialization, view, mode):
        case = Case(self, serialization, view)
        release, entered, unwinding = asyncio.Event(), asyncio.Event(), asyncio.Event()
        try:
            main, sibling = await case.client(), await case.client()
            session = case.source.sessions[0]
            base = main.candidate.tag.native.wire()
            case.advance()
            target = list(case.owner.sync_current_tag(view))
            expected = case.owner.sync_changes(view, base, target)
            self.assertEqual(len(expected), 5)
            native_bytes = sum(map(len, expected))
            input_owner = case.source.inputs[0]
            inventories = {}
            actual = main.carrier.output_channel.writer
            original_write, original_drain = actual.write, actual.drain
            held = [False]
            def write(value):
                held[0] = value == expected[0][:-1]
                original_write(value)
                if held[0] and mode == "write-failure":
                    inventories["beforeWriteFailure"] = self.physical_inventory(input_owner, case.ledger)
                    entered.set()
                    raise OSError("controlled_partial_output")
            async def drain():
                if held[0]:
                    entered.set()
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        unwinding.set()
                        await ENV.finish(asyncio.create_task(release.wait()))
                        raise
                    finally:
                        held[0] = False
                await original_drain()
            with patch.object(actual, "write", new=write), patch.object(actual, "drain", new=drain):
                await main.command("changes", acquisition=main.capid, base=base, target=target,
                                   maxTransactions=4, maxBytes=8388608)
                await asyncio.wait_for(entered.wait(), 2)
                if mode != "write-failure":
                    inventories["held"] = self.physical_inventory(input_owner, case.ledger)
                    self.assertEqual((inventories["held"]["buffers"], inventories["held"]["encodedBytes"],
                                      inventories["held"]["consuming"], inventories["held"]["revoked"]), (5, native_bytes, 5, 0))
                    self.assertEqual(session.inspect()["ownedRefs"], 5)
                    self.assertGreaterEqual(case.ledger.encoded_reserved, native_bytes)
                    if mode == "cancel-command":
                        await main.command("cancel", acquisition=main.capid, command=main.command_id)
                        await asyncio.wait_for(unwinding.wait(), 2)
                    elif mode == "server-cancel":
                        main.server.cancel()
                        main.server.cancel()
                        await asyncio.wait_for(unwinding.wait(), 2)
                    else:
                        await session.aclose()
                        await session.aclose()
                        self.assertTrue(session.inspect()["closed"])
                        self.assertEqual(session.inspect()["ownedRefs"], 0)
                    self.assertGreaterEqual(case.ledger.encoded_reserved, native_bytes)
                    self.assertFalse(main.server.done())
                    inventories["duringCleanup"] = self.physical_inventory(input_owner, case.ledger)
                    self.assertEqual((inventories["duringCleanup"]["buffers"], inventories["duringCleanup"]["encodedBytes"],
                                      inventories["duringCleanup"]["consuming"]), (5, native_bytes, 5))
                release.set()
                await asyncio.wait_for(asyncio.gather(main.server, return_exceptions=True), 2)
            partial = await asyncio.wait_for(main.reader.read(), 2)
            self.assertNotEqual(partial, b'')
            self.assertFalse(partial.endswith(b'\n'), partial[-100:])
            self.assertNotIn(b'\n', partial)
            self.assertNotIn(b'"kind":"command-result"', partial)
            main.cache.disconnect()  # test-owned caller reacts to EOF
            with self.assertRaisesRegex(ENV.Error, "sync_unconfirmed") as failure:
                main.cache.acquire()
            self.errors.append(failure.exception)
            self.assertEqual(main.transactions, 0)
            self.assertEqual(main.proofs, 1)
            self.assertFalse(case.relay._closed)  # disclosed generic factory lifecycle audit
            self.assertFalse(case.source.sessions[1].inspect()["closed"])
            inventories["afterUnwind"] = self.physical_inventory(input_owner, case.ledger)
            self.assertEqual(inventories["afterUnwind"]["buffers"], 0)
            await sibling.command("baseline", acquisition=sibling.capid)
            await sibling.result()
            await sibling.head()
            self.assertEqual(sibling.proofs, 2)
            OUTCOMES.append(dict(test=mode, serialization=serialization, view=view, heldNativeBytes=native_bytes,
                                 mainPartialPrefixOnly=True, mainNewProofs=0, callerDisconnectedOnEOF=True,
                                 siblingFreshProof=True, physicalInventory=inventories))
        finally:
            release.set()
            await case.close()


def main():
    global ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    gc.disable()
    ENV = SimpleNamespace(
        sync=importlib.import_module("mesh_plus.sync"),
        State=importlib.import_module("agent_observer.service_state").ServiceState,
        Running=importlib.import_module("test_service_runtime").Running,
        snapshot=importlib.import_module("test_service_runtime").scoped_snapshot,
        Profile=importlib.import_module("agent_observer.mesh_sync_profile").AgentSyncProfile,
        Source=importlib.import_module("agent_observer.sync_source").CachedAgentSyncSource,
        CompactSource=importlib.import_module("agent_observer.sync_compact_source").CachedCompactAgentSyncSource,
        Transport=importlib.import_module("agent_observer.sync_transport").AgentSyncTransportCodec,
        CompactTransport=importlib.import_module("agent_observer.sync_compact_acquisition").CompactAgentSyncTransportCodec,
        Native=importlib.import_module("agent_observer.mesh_sync_codec").AgentCompactSyncCodec,
        Ledger=importlib.import_module("mesh_plus.sync.budget").AllocationLedger,
        Error=importlib.import_module("mesh_plus.protocol").ProtocolError,
        canonical=importlib.import_module("mesh_plus.sync.canonical").canonical,
        decode=importlib.import_module("mesh_plus.sync.canonical").decode,
        now=importlib.import_module("mesh_plus.transport").boottime_ms,
        finish=importlib.import_module("mesh_plus.transport").finish_owned,
    )
    with args.log.open("x") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Lifecycle))
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).suffix == ".py":
            path = Path(filename).resolve()
            for side, root in (("mesh", mesh), ("observer", observer)):
                if path.is_relative_to(root):
                    loaded[side + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(python=sys.version.split()[0], testsRun=result.testsRun, failures=len(result.failures),
                  errors=len(result.errors), skips=len(result.skipped), cases=OUTCOMES, loadedInputs=loaded,
                  cyclicGC="disabled throughout, retained real errors, no explicit collection",
                  exclusions="Synthetic native data/collection disabled, trusted control plane caller, private Reader nonce/native fixture close/factory closed and bounded physical input-owner inventory audit; public source delegation/session inspect plus private writer-instance drain/write hooks, separate ledgers/oracle copies. No aggregate resource/RSS/CPU/dense2k/nativeprovider/fixedSSH/installedpair/route/adoption acceptance.")
    assert not gc.isenabled()
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips")}))
    raise SystemExit(not (result.wasSuccessful() and not result.skipped and len(OUTCOMES) == 20))


if __name__ == "__main__":
    main()
