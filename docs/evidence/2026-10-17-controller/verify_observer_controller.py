"""Actual synthetic native Runtime and public controller over IPC and pipe stdio.

Independent Reader admission uses supported codec/cache APIs. Private nonce
setup and native fixture retirement are disclosed. No populated provider,
selected route, installed pair, CPU/RSS or aggregate resource acceptance.
"""

import argparse
import asyncio
import gc
import hashlib
import importlib
import json
import os
import secrets
import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ENV = None
OUTCOMES = []


class ControllerComposition(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.errors = []
        self.assertFalse(gc.isenabled())

    async def exercise(self, transport, serialization, view, count):
        owner = ENV.State(host_scope="fixture", configs={"codex": ("/fixture/codex", "explicit")},
                          sync_serialization=serialization)
        owner.attempt("codex", "history")
        owner.accept("codex", "history", ENV.snapshot(), sampled_ms=owner.clock(),
                     ttl_ms=60000, runtime_ttl_ms=60000)
        records, captures, patches = [], {}, []
        for operation in ("baseline", "changes", "head"):
            original = getattr(owner, "sync_" + operation)
            def capture(*args, _original=original, _operation=operation, **kwargs):
                value = _original(*args, **kwargs)
                if _operation == "changes":
                    value = (*value[:-1], value[-1][:-1] + b"  \n")
                captures.setdefault(_operation, []).append(value)
                return value
            handle = patch.object(owner, "sync_" + operation, new=capture)
            handle.start()
            patches.append(handle)
        runtime = ENV.Running(state=owner)
        runtime.__enter__()
        ledger, relay, cache, carrier, server = ENV.Ledger(), None, None, None, None
        reader_transport = writer = None
        client_bytes = 0
        try:
            profile = ENV.Profile(profile_schema_digest="a" * 64, view=view)
            compact = serialization == "compact"
            encoding = "fixture-compact/1" if compact else "fixture-expanded/1"
            codec = (ENV.CompactTransport if compact else ENV.Transport)(view, encoding_id=encoding,
                                                                         expected_host="fixture")
            source = (ENV.CompactSource if compact else ENV.Source)("fixture", runtime.path, view=view, timeout=2)
            binding = ENV.binding("fixture", "agents", profile.descriptor)
            relay = ENV.relay(source, profile.descriptor, binding, native_codec=codec,
                               budgets=ENV.Budgets(), ledger=ledger)
            if transport == "ipc":
                supplied, peer = socket.socketpair()
                carrier = ENV.ipc(supplied, ledger=ledger)
                reader, writer = await asyncio.open_connection(sock=peer, limit=8470528)
            else:
                read_fd, input_peer = os.pipe()
                output_peer, write_fd = os.pipe()
                carrier = ENV.stdio(read_fd, write_fd, ledger=ledger)
                reader = asyncio.StreamReader(limit=8470528)
                protocol = asyncio.StreamReaderProtocol(reader)
                reader_transport, _ = await asyncio.get_running_loop().connect_read_pipe(
                    lambda: protocol, os.fdopen(output_peer, "rb", buffering=0))
                writer = os.fdopen(input_peer, "wb", buffering=0)
            server = asyncio.create_task(ENV.serve(relay, carrier, setup_deadline_ms=ENV.now() + 15000))

            async def send(value):
                nonlocal client_bytes
                raw = ENV.canonical(value) + b"\n"
                writer.write(raw)
                if transport == "ipc":
                    await writer.drain()
                client_bytes += len(raw)

            async def receive(kind):
                raw = await asyncio.wait_for(reader.readline(), 2)
                self.assertTrue(raw.endswith(b"\n"), raw)
                value = ENV.decode(raw)
                self.assertEqual(value["kind"], kind)
                records.append(raw)
                return value, raw

            async def result(command, through):
                value, _ = await receive("command-result")
                self.assertEqual(set(value), {"protocol", "kind", "request", "command", "operation", "status", "code", "through"})
                self.assertEqual((value["request"], value["command"], value["status"], value["code"], value["through"]),
                                 (digest, command, "ok", "none", through))
                return value

            def fragment(line, field="native"):
                payload = ENV.decode(line)["payload"]
                header = {k: v for k, v in payload.items() if k != field}
                marker = b',"payload":' + ENV.canonical(header)[:-1] + b',"' + field.encode() + b'":'
                start = line.index(marker) + len(marker)
                self.assertTrue(line.endswith(b"}}\n"))
                return line[start:-3] + b"\n"

            nonce = secrets.token_hex(32)
            await send({"protocol": "mesh.state-sync/1", "kind": "hello", "nonce": nonce})
            hello, _ = await receive("hello")
            self.assertEqual(hello["nonce"], nonce)
            self.assertEqual(hello["descriptor"], profile.descriptor.wire())
            self.assertEqual(hello["sourceBinding"], binding)
            self.assertEqual(hello["encoding"], dict(codec.encoding))
            request = {"readerEpoch": secrets.token_hex(16), "requestId": "controller-native",
                       "catalogRevision": "fixture", "hosts": ["fixture"], "route": transport,
                       "channelEpoch": secrets.token_hex(16), "bridgeId": hello["bridgeId"],
                       "role": "transport-relay", "encodingDigest": hashlib.sha256(ENV.canonical(hello["encoding"])).hexdigest()}
            digest = hashlib.sha256(ENV.canonical(request)).hexdigest()
            await send({"protocol": "mesh.state-sync/1", "kind": "open", "controllerVersion": 1,
                        "requestBinding": request, "remainingMs": 15000})
            setup, _ = await receive("setup")
            self.assertEqual(setup["requestBinding"], request)
            clock = {"bootId": "fixture-reader", "timeNamespace": "time:999"}
            native = ENV.Native(view, encoding_id=encoding, expected_host="fixture") if compact else None
            cache = ENV.Cache(profile, binding, request_binding=request, native_codec=native, _clock=clock)

            async def command(sequence, operation, **fields):
                await send({"protocol": "mesh.state-sync/1", "kind": "command", "request": digest,
                            "sequence": sequence, "operation": operation, **fields})

            await command(1, "begin", remainingMs=15000)
            await result(1, 0)
            await command(2, "baseline", acquisition=1)
            baseline, raw = await receive("delivery")
            self.assertEqual(fragment(raw), captures["baseline"][-1])
            candidate = cache.admit_baseline(fragment(raw))
            await result(2, 1)

            async def confirm(sequence, delivery_sequence):
                challenge = cache._proof_request(candidate)  # disclosed test-only nonce setup
                await command(sequence, "head", acquisition=1, challenge=challenge, remainingMs=2000)
                proof, raw = await receive("delivery")
                self.assertEqual(proof["sequence"], delivery_sequence)
                self.assertEqual(fragment(raw, "head"), captures["head"][-1])
                current = cache.confirm(candidate, ENV.canonical(proof["payload"]), clock)
                self.assertEqual(current.export_committed(), owner.snapshot if view == "full" else owner.active_projection)
                await result(sequence, delivery_sequence)

            await confirm(3, 2)
            base = candidate.tag.native.wire()
            if count == 1:
                owner.attempt("codex", "history")
            elif count == 4:
                for index in range(2):
                    value = ENV.snapshot()
                    value["sessions"][0]["title"] = f"controller {index}"
                    owner.attempt("codex", "history")
                    owner.accept("codex", "history", value, sampled_ms=owner.clock(), ttl_ms=60000, runtime_ttl_ms=60000)
            target = list(owner.sync_current_tag(view))
            await command(4, "changes", acquisition=1, base=base, target=target, maxTransactions=4, maxBytes=8388608)
            for index in range(count + 1):
                delivery, raw = await receive("delivery")
                self.assertEqual(delivery["sequence"], index + 3)
                self.assertEqual(fragment(raw), captures["changes"][-1][index])
                if index < count:
                    candidate = cache.stage(fragment(raw))
                else:
                    terminal = delivery["payload"]["native"]
            reply = await result(4, count + 3)
            for wrong in (terminal, reply):
                cache._proof_request(candidate)
                with self.assertRaisesRegex(ENV.Error, "sync_proof_shape") as failure:
                    cache.confirm(candidate, ENV.canonical(wrong), clock)
                self.errors.append(failure.exception)
            self.assertEqual(candidate.tag.native.wire(), list(target))
            await confirm(5, count + 4)
            await command(6, "end", acquisition=1)
            await result(6, count + 4)
            # The peer can read the LF before the sender resumes from drain.
            # Sample completed-line counters after that owned bookkeeping.
            async def counters_settled():
                while carrier.output_channel.inspect()["sentFrames"] < len(records):
                    await asyncio.sleep(0)
            await asyncio.wait_for(counters_settled(), 2)
            metrics = carrier.output_channel.inspect()
            self.assertEqual(metrics["physicalReceivedBytes"], client_bytes)
            self.assertEqual(metrics["physicalSentBytes"], sum(map(len, records)))
            self.assertEqual(metrics["sentFrames"], len(records))
            self.assertEqual(metrics["sentBytes"], metrics["physicalSentBytes"])
            OUTCOMES.append({"transport": transport, "serialization": serialization, "view": view,
                             "transactions": count, "actualHeadProofs": 2, "nativeFragmentsEqual": True,
                             "controllerResultAndNativeCompleteAsProof": "rejected", "wireBytes": metrics,
                             "relayAccountedHeapPeak": ledger.peak,
                             "aggregateResourceAcceptance": False})
        finally:
            if writer is not None:
                writer.close()
                if transport == "ipc":
                    await writer.wait_closed()
            if server is not None:
                results = await asyncio.wait_for(asyncio.gather(server, return_exceptions=True), 2)
                self.errors.extend(x for x in results if isinstance(x, BaseException))
            if relay is not None:
                await relay.aclose()
            if carrier is not None:
                await carrier.aclose()
            if reader_transport is not None:
                reader_transport.close()
            if cache is not None:
                cache.close()
                self.assertEqual(tuple(getattr(cache.ledger, k) for k in
                                       ("used", "reserved", "encoded", "encoded_reserved", "pending_units", "pending_encoded")), (0,) * 6)
            self.assertEqual(tuple(getattr(ledger, k) for k in
                                   ("used", "reserved", "encoded", "encoded_reserved", "pending_units")), (0,) * 5)
            runtime.__exit__()
            for handle in reversed(patches):
                handle.stop()
            account = owner._sync_cache.account
            owner._sync_cache.close()  # owning fixture close only
            self.assertEqual(account.snapshot()["used"], account.snapshot()["base"])
            self.assertFalse(gc.isenabled())

    async def cases(self, transport):
        for serialization in ("expanded", "compact"):
            for view in ("full", "active"):
                for count in (0, 1, 4):
                    with self.subTest(transport=transport, serialization=serialization, view=view, count=count):
                        await self.exercise(transport, serialization, view, count)

    async def test_actual_source_controller_reader_over_unread_ipc(self):
        await self.cases("ipc")

    async def test_actual_source_controller_reader_over_unread_fixed_stdio_pipes(self):
        await self.cases("stdio")


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
    sync = importlib.import_module("mesh_plus.sync")
    ENV = SimpleNamespace(
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
        relay=sync.create_sync_relay, serve=sync.serve_sync_relay, ipc=sync.control_carrier_from_ipc,
        stdio=sync.control_carrier_from_stdio, Cache=sync.OwnedSyncCache,
        binding=sync.source_binding, Budgets=sync.SyncBudgets,
    )
    with args.log.open("x") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ControllerComposition))
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
              "cases": OUTCOMES, "loadedInputs": loaded,
              "cyclicGC": "disabled; held failures; no explicit collection",
              "scope": "24 small actual synthetic Runtime/source/controller/IPC or real pipe stdio/independent Reader scenarios",
              "exclusions": "Trusted caller binding, test-owned Reader nonce setup/capture/oracles and separate accounts; no populated native provider/fixedSSH/aggregate32-64/RSS/CPU/dense2k/recovery/installedpair/selection/rollout acceptance."}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips")}))
    raise SystemExit(0 if result.wasSuccessful() and len(OUTCOMES) == 24 and not result.skipped else 1)


if __name__ == "__main__":
    main()
