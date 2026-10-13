"""Matched full-proof shared-publisher WSS/TCP control, with no codec change."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "controlled"))
from run import inputs, logical_counts, payload_bytes, ready, retire, role, sampled, spawn  # noqa: E402
from worker import rpc  # noqa: E402

sys.path.insert(0, str(ROOT.parent / "performance"))
from coordinator import resources  # noqa: E402

sys.path.insert(0, str(ROOT.parents[1] / "tests/wss"))
from wss_fixtures import certificates, contexts, fingerprint  # noqa: E402

sys.path.insert(0, str(ROOT))
from tcp_stream import connect as connect_tcp  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import Client, Endpoint, Reader, ReadGuard, reconstructed  # noqa: E402
from mesh_plus.evidence import clock_domain  # noqa: E402
from mesh_plus.reader import PublicationState  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402
from mesh_plus.wss import connect as connect_wss  # noqa: E402


async def case(args, carrier, fanout, mode, expired=False):
    profile = TmuxMeshProfile()
    codec = profile.bind("beta", "controlled")
    children, clients, streams, consumers, guards = [], [], [], [], []
    observed, admissions = [-1] * fanout, [0] * fanout
    condition = asyncio.Condition()
    failures = []
    revision = "sha256:" + "a" * 64

    async def catalog():
        return revision

    with tempfile.TemporaryDirectory(prefix=".mesh-carrier-") as name:
        root = Path(name)
        root.chmod(0o700)
        try:
            cert = root / "cert"
            cert.mkdir(mode=0o700)
            certificates(cert)
            (cert / "policy.json").write_text(json.dumps({fingerprint(cert): ["beta", "controlled", codec.profile_id]}))
            _, context = contexts(cert)
            hub = await spawn(ROOT / "carrier_worker.py", "hub", "--root", root, "--rows", args.rows,
                              *(["--expired"] if expired else []))
            children.append(hub)
            await ready(hub)
            pub = await spawn(ROOT / "carrier_worker.py", "publisher", "--root", root, "--carrier", carrier)
            children.append(pub)
            endpoint = await ready(pub)

            async def connect():
                channel = (await connect_tcp(endpoint["port"], context) if carrier == "tcp" else
                           await connect_wss(f'wss://localhost:{endpoint["port"]}/mesh/state', context))
                try:
                    client = await Client.connect(channel, host="beta", source="controlled", profile=codec.profile_id, codec=codec.validate_bridge)
                except BaseException:
                    await channel.close()
                    raise
                clients.append(client)
                return client

            readers = [Reader("tmux", [Endpoint("beta", False, revision, connect, codec)], local_host="alpha",
                              catalog_revision=revision, catalog_check=catalog, profile=profile) for _ in range(fanout)]
            guards = [ReadGuard("tmux", format(index + 1, "032x"), profile=profile) for index in range(fanout)]
            original_receipts = None

            def admit(index, frame):
                nonlocal original_receipts
                guards[index].accept(frame)
                if frame.get("mesh", {}).get("status") != "complete":
                    return None
                native = reconstructed(frame, frame["mesh"]["hosts"][0], profile=profile)
                state = codec.inspect_native(native)
                if original_receipts is None:
                    original_receipts = state.receipts
                if state.receipts != original_receipts:
                    raise ValueError("original_receipts_changed")
                if len(guards[index].current(boottime_ms(), clock_domain())) != (0 if expired else args.rows):
                    raise ValueError("current_rows")
                rows = native["snapshot"]["sessions"]
                step = native["viewRevision"] - 1
                if len(rows) != args.rows or {r["sessionId"] for r in rows} != {"$" + str(100 + n) for n in range(args.rows)}:
                    raise ValueError("identities")
                if any(row["name"] != "trace-" + str(step).zfill(5) for row in rows):
                    raise ValueError("trace_content")
                admissions[index] += 1
                return step

            async def consume(index, stream):
                try:
                    async for frame in stream:
                        step = admit(index, frame)
                        if step is not None:
                            async with condition:
                                observed[index] = step
                                condition.notify_all()
                except Exception as error:
                    failures.append(type(error).__name__ + ":" + str(error))
                    async with condition:
                        condition.notify_all()

            async def until(step):
                async with asyncio.timeout(5):
                    async with condition:
                        await condition.wait_for(lambda: failures or all(value == step for value in observed))
                if failures:
                    raise ValueError("consumer_failure:" + str(failures))
                async with asyncio.timeout(5):
                    while len(clients) != fanout or any(c.inspect()["pendingRequests"] for c in clients):
                        await asyncio.sleep(.001)

            states = [PublicationState() for _ in readers]
            if mode == "push":
                for index, reader in enumerate(readers):
                    stream = reader.watch(request_id=format(index + 1, "032x"), proof_interval=60, catalog_interval=5)
                    streams.append(stream)
                    consumers.append(asyncio.create_task(consume(index, stream)))
                await until(0)
                async with asyncio.timeout(5):
                    while any(c.inspect()["operations"]["proofRequests"] != 2 for c in clients):
                        await asyncio.sleep(.001)
            else:
                for reader in readers:
                    await reader.endpoints[0].connect()
            roles = [role(os.getpid(), "reader-driver"), role(hub.pid, "fixture-source"), role(pub.pid, "publisher")]
            sampler = await spawn(ROOT.parent / "controlled/accounting.py")
            children.append(sampler)
            samples = [await sampled(sampler, roles)]
            before, bytes_before = logical_counts(clients), payload_bytes(clients)
            source_before = await rpc(root / "native.sock", {"operation": "inspect"})
            framing_before = [client.channel.inspect() for client in clients]
            trace, latencies = [], []
            started = time.monotonic()
            for step in range(1, args.steps + 1):
                tick = time.monotonic()
                trace.append(await rpc(root / "native.sock", {"operation": "step", "step": step}))
                if mode == "push":
                    await until(step)
                else:
                    for index, (reader, client) in enumerate(zip(readers, clients, strict=True)):
                        outcome = await reader.read_host(client, reader.endpoints[0])
                        value = reader.compose(reader.endpoints, {"beta": outcome}, format(index + 1, "032x"), "watch", state=states[index])
                        if admit(index, value) != step:
                            raise ValueError("poll_step")
                latencies.append((time.monotonic() - tick) * 1000)
                if step % 4 == 0:
                    samples.append(await sampled(sampler, roles))
                await asyncio.sleep(max(0, args.interval - (time.monotonic() - tick)))
            elapsed = time.monotonic() - started
            samples.append(await sampled(sampler, roles))
            after, bytes_after = logical_counts(clients), payload_bytes(clients)
            traffic = {key: after.get(key, 0) - before.get(key, 0) for key in before.keys() | after.keys()}
            if traffic["proofRequests"] != args.steps * fanout or traffic["requestTimeouts"]:
                raise ValueError("proof_work_mismatch")
            if traffic.get("received:data", 0) != (args.steps * fanout if mode == "push" else 0):
                raise ValueError("push_work_mismatch")
            source_after = await rpc(root / "native.sock", {"operation": "inspect"})
            if source_after["counts"]["snapshot"] - source_before["counts"]["snapshot"] != args.steps * fanout:
                raise ValueError("native_acquisition_mismatch")
            measured = resources(samples)
            if measured["errors"]:
                raise ValueError("role_identity_changed")
            value = {"status": "passed", "carrier": carrier, "mode": mode, "fanout": fanout, "rows": args.rows,
                     "steps": args.steps, "expired": expired, "intervalSeconds": args.interval,
                     "elapsedSeconds": elapsed, "trace": trace, "traffic": traffic, "consumerAdmissions": admissions,
                     "canonicalJsonBytes": {key: bytes_after[key] - bytes_before[key] for key in bytes_before},
                     "sourceCountsBefore": source_before["counts"], "sourceCountsAfter": source_after["counts"],
                     "resources": measured, "latencyMs": latencies,
                     "carrierCountersBefore": framing_before,
                     "carrierCountersAfter": [client.channel.inspect() for client in clients],
                     "scope": "study-only full-proof loopback carriage; identical shared-publisher topology and remote proof semantics",
                     "provenanceLimit": "pure generic Reader's legacy SSH path label is a common synthetic placeholder, not production TCP/WSS provenance"}
        finally:
            errors = []
            for task in consumers:
                task.cancel()
            await asyncio.gather(*consumers, return_exceptions=True)
            for stream in streams:
                try:
                    await stream.aclose()
                except Exception as error:
                    errors.append(error)
            for guard in guards:
                guard.disconnect()
            for client in clients:
                try:
                    await client.close()
                except Exception as error:
                    errors.append(error)
            if children and hub.returncode is None:
                try:
                    async with asyncio.timeout(3):
                        while (await rpc(root / "native.sock", {"operation": "inspect"}))["watchers"]:
                            await asyncio.sleep(.01)
                except Exception as error:
                    errors.append(error)
            for child in reversed(children):
                try:
                    await retire(child)
                except Exception as error:
                    errors.append(error)
            if errors:
                original = sys.exc_info()[1]
                raise ExceptionGroup("carrier_case_cleanup", ([original] if isinstance(original, Exception) else []) + errors)
        if any(not client.channel.closed for client in clients):
            raise ValueError("channel_not_closed")
        value["cleanup"] = True
        value["readerMetrics"] = [reader.inspect() for reader in readers]
        if any(m["activeConnections"] or m["cleanupFailures"] for m in value["readerMetrics"]):
            raise ValueError("reader_cleanup")
        return value


async def run(args):
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise ValueError("output_not_empty")
    manifest = inputs()
    manifest["studyHarness"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.py"))}
    (args.output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    from matrix import qualify
    index = []
    for mode in args.modes:
        for fanout in args.fanout:
            for block in range(args.blocks):
                values = []
                for position, carrier in enumerate(("wss", "tcp", "tcp", "wss")):
                    label = f"{mode}-{fanout}-{block}-{position}"
                    try:
                        value = await case(args, carrier, fanout, mode, args.expired)
                        value.update(pair="wss-tcp", block=block, position=position)
                    except Exception as error:
                        (args.output / (label + ".json")).write_text(json.dumps({"status": "failed", "error": str(error)}, indent=2) + "\n")
                        raise
                    (args.output / (label + ".json")).write_text(json.dumps(value, indent=2) + "\n")
                    values.append(value)
                qualify(values)
                index.append({"mode": mode, "fanout": fanout, "block": block, "status": "exact_work_matched"})
                (args.output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
                print(json.dumps(index[-1]), flush=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", choices=("poll", "push"), default=["poll", "push"])
    parser.add_argument("--fanout", nargs="+", type=int, choices=(1, 2, 4), default=[1, 2, 4])
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--interval", type=float, default=.05)
    parser.add_argument("--expired", action="store_true")
    args = parser.parse_args()
    if not args.output.is_absolute() or not 1 <= args.blocks <= 4 or not 1 <= args.steps <= 100 or not .01 <= args.interval <= 3:
        parser.error("bounded_cases")
    asyncio.run(run(args))
