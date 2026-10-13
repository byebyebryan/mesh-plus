"""Matched cached trace delivery through released IPC/SSH/WSS and a pure Tmux profile."""

import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import json
import os
import statistics
import sys
import tempfile
import time
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "performance"))
from trace import canonical  # noqa: E402

from coordinator import resources  # noqa: E402
from measure import process  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402
from worker import rpc  # noqa: E402

from mesh_plus.api import Client, Endpoint, Reader, ReadGuard, reconstructed  # noqa: E402
from mesh_plus.evidence import clock_domain  # noqa: E402
from mesh_plus.reader import PublicationState  # noqa: E402
from mesh_plus.testing.ssh_carrier import ssh_server  # noqa: E402
from mesh_plus.transport import boottime_ms, connect_ipc  # noqa: E402


def fingerprints():
    result = {}
    for package in ("mesh_plus", "tmux_observer"):
        root = Path(str(files(package)))
        contents = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.rglob("*")) if p.suffix in (".py", ".json")}
        result[package] = hashlib.sha256(canonical(contents).encode()).hexdigest()
    return result


def inputs():
    expected = json.loads((ROOT / "inputs.json").read_text())
    versions = {name: importlib.metadata.version(name) for name in expected["packages"]}
    if versions != expected["packages"] or fingerprints() != expected["runtimeFingerprints"]:
        raise ValueError("unreviewed_benchmark_environment")
    if sys.version.split()[0] != expected["python"]:
        raise ValueError("unreviewed_benchmark_python")
    return {**expected, "harness": {str(p.relative_to(ROOT.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*sorted(ROOT.glob("*.py")), ROOT.parent / "performance/measure.py",
                  ROOT.parent / "performance/coordinator.py", ROOT.parent / "performance/host.py",
                  ROOT.parents[1] / "tests/wss/wss_fixtures.py"]}}


async def spawn(*arguments):
    return await asyncio.create_subprocess_exec(sys.executable, "-I", "-B", *map(str, arguments),
                                               stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                               stderr=asyncio.subprocess.PIPE, limit=8388609)


async def retire(child):
    if child.returncode is None:
        child.terminate()
        try:
            await asyncio.wait_for(child.wait(), 5)
        except TimeoutError:
            child.kill()
            await child.wait()
    if child.returncode not in (0, -15):
        error = (await child.stderr.read()).decode()
        raise ValueError("worker_retirement_failure:" + str(child.returncode) + ":" + error)


async def ready(child):
    async with asyncio.timeout(10):
        raw = await child.stdout.readline()
    if not raw:
        error = (await child.stderr.read()).decode()
        raise ValueError("worker_not_ready:" + error)
    value = json.loads(raw)
    if not value["ready"]:
        raise ValueError("worker_not_ready")
    return value


def role(pid, name):
    value = process(pid, memory=False)
    if "error" in value:
        raise ValueError("missing_role")
    return {"pid": pid, "birth": value["birth"], "role": name}


def descendants(pid):
    result = []
    path = Path(f"/proc/{pid}/task/{pid}/children")
    for child in map(int, path.read_text().split()):
        result.append(child)
        result.extend(descendants(child))
    return result


def logical_counts(clients):
    result = {}
    for client in clients:
        metric = client.inspect()
        channel = metric["channel"]
        for direction in ("sent", "received"):
            for kind, values in channel["byKind"].get(direction, {}).items():
                key = direction + ":" + kind
                result[key] = result.get(key, 0) + values["frames"]
        for key in ("proofRequests", "snapshotRequests", "requestTimeouts"):
            result[key] = result.get(key, 0) + metric["operations"][key]
    return result


def payload_bytes(clients):
    result = {"sent": 0, "received": 0}
    for client in clients:
        channel = client.inspect()["channel"]
        for direction in result:
            count = channel[direction + "Bytes"]
            if channel["byteScope"] == "completed-json-lines":
                count -= channel[direction + "Frames"]
            result[direction] += count
    return result


async def sampled(child, roles):
    child.stdin.write((canonical(roles) + "\n").encode())
    await child.stdin.drain()
    async with asyncio.timeout(5):
        return json.loads(await child.stdout.readline())


async def case(args, carrier, fanout, mode, expired=False):
    profile = TmuxMeshProfile()
    codec = profile.bind("beta", "controlled")
    children, clients, streams, consumers = [], [], [], []
    guards = []
    condition = asyncio.Condition()
    observed = [-1] * fanout
    failures = []
    revision = "sha256:" + "a" * 64

    async def catalog_check():
        return revision

    with tempfile.TemporaryDirectory(prefix=".mesh-trace-", dir=Path.home()) as name:
        root = Path(name)
        root.chmod(0o700)
        async with contextlib.AsyncExitStack() as stack:
            try:
                hub = await spawn(ROOT / "worker.py", "hub", "--root", root, "--rows", args.rows,
                                  *(["--expired"] if expired else []))
                children.append(hub)
                initial = await ready(hub)
                selection = None
                pub = None
                if carrier == "ssh":
                    command = [sys.executable, "-I", "-B", str(ROOT / "worker.py"), "bridge", "--root", str(root)]
                    connector = await stack.enter_async_context(ssh_server(root, command, "controlled"))
                else:
                    if carrier == "wss":
                        sys.path.insert(0, str(ROOT.parents[1] / "tests/wss"))
                        from wss_fixtures import certificates, fingerprint
                        cert = root / "cert"
                        cert.mkdir(mode=0o700)
                        certificates(cert)
                        (cert / "policy.json").write_text(canonical({fingerprint(cert): ["beta", "controlled", codec.profile_id]}))
                    pub = await spawn(ROOT / "worker.py", "publisher", "--root", root, "--carrier", carrier)
                    children.append(pub)
                    endpoint = await ready(pub)
                    if carrier == "ipc":
                        async def connector():
                            return await connect_ipc(root / "mesh.sock")
                    else:
                        from mesh_plus.wss import Selection, configured_reader
                        cert = root / "cert"
                        (cert / "catalog.json").write_bytes(files("mesh_plus.testing").joinpath("catalog.json").read_bytes())
                        (cert / "registry.json").write_text(canonical({"protocol": "mesh-plus.wss.v1", "endpoints": [
                            {"hostId": "beta", "sourceId": "controlled", "profile": codec.profile_id,
                             "url": f'wss://localhost:{endpoint["port"]}/mesh/state', "product": "state",
                             "capabilities": ["snapshot", "proof", "subscribe"]}]}))
                        selection = Selection.load(cert / "catalog.json", cert / "registry.json", cert / "ca.pem",
                                                   cert / "client.pem", cert / "client.key")
                        stack.callback(selection.close)

                readers = []
                for index in range(fanout):
                    async def connect():
                        client = await Client.connect(await connector(), host="beta", source="controlled",
                                                      profile=codec.profile_id, codec=codec.validate_bridge)
                        clients.append(client)
                        return client
                    if selection is not None:
                        reader = await configured_reader("tmux", selection=selection, source="controlled",
                                                         socket=Path("/unused"), scope="hosts", hosts=["beta"], profile=profile)
                        # Keep owned clients visible for equal-work admission and accounting.
                        connect_wss = reader.endpoints[0].connect

                        async def collect(connect_wss=connect_wss):
                            client = await connect_wss()
                            clients.append(client)
                            return client
                        from dataclasses import replace
                        reader = type(reader)("tmux", [replace(e, connect=collect) for e in reader.endpoints],
                                              local_host="alpha", catalog_revision=selection.revision,
                                              catalog_check=selection.check, profile=profile, bindings=selection.bindings)
                    else:
                        reader = Reader("tmux", [Endpoint("beta", False, revision, connect, codec)], local_host="alpha",
                                        catalog_revision=revision, catalog_check=catalog_check, profile=profile)
                    readers.append(reader)
                    guards.append(ReadGuard("tmux", format(index + 1, "032x"), profile=profile))

                expected_receipts = None
                admissions = [0] * fanout

                def admit(index, frame):
                    nonlocal expected_receipts
                    guard = guards[index]
                    guard.accept(frame)
                    if frame.get("mesh", {}).get("status") != "complete":
                        return None
                    native = reconstructed(frame, frame["mesh"]["hosts"][0], profile=profile)
                    state = codec.inspect_native(native)
                    if expected_receipts is None:
                        expected_receipts = state.receipts
                    if state.receipts != expected_receipts:
                        raise ValueError("consumer_original_receipts_changed")
                    actual = guard.current(boottime_ms(), clock_domain())
                    if len(actual) != (0 if expired else args.rows):
                        raise ValueError("consumer_current_rows")
                    rows = native["snapshot"]["sessions"]
                    if len(rows) != args.rows or {r["sessionId"] for r in rows} != {"$" + str(100 + n) for n in range(args.rows)}:
                        raise ValueError("consumer_identities")
                    step = native["viewRevision"] - 1
                    if any(r["name"] != "trace-" + str(step).zfill(5) for r in rows):
                        raise ValueError("consumer_trace_content")
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
                    # The accepted replacement must also retire all proof requests.
                    async with asyncio.timeout(5):
                        while len(clients) != fanout or any(c.inspect()["pendingRequests"] for c in clients):
                            await asyncio.sleep(.001)

                publications = [PublicationState() for _ in readers]
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

                roles = [role(os.getpid(), "reader-driver"), role(hub.pid, "fixture-source")]
                if pub is not None:
                    roles.append(role(pub.pid, "publisher"))
                if carrier == "ssh":
                    daemon = int((root / "sshd.pid").read_text())
                    roles.append(role(daemon, "ssh-listener"))
                    for pid in descendants(daemon):
                        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                        roles.append(role(pid, "publisher" if b"bridge" in command else "ssh-server-session"))
                    roles.extend(role(c.channel.process.pid, "ssh-client") for c in clients)
                sampler = await spawn(ROOT / "accounting.py")
                children.append(sampler)
                samples = [await sampled(sampler, roles)]
                before = logical_counts(clients)
                bytes_before = payload_bytes(clients)
                source_before = await rpc(root / "native.sock", {"operation": "inspect"})
                trace_hashes = []
                latency = []
                started = time.monotonic()
                for step in range(1, args.steps + 1):
                    tick = time.monotonic()
                    trace_hashes.append(await rpc(root / "native.sock", {"operation": "step", "step": step}))
                    if mode == "push":
                        await until(step)
                    else:
                        for index, (reader, client) in enumerate(zip(readers, clients, strict=True)):
                            outcome = await reader.read_host(client, reader.endpoints[0])
                            response = reader.compose(reader.endpoints, {"beta": outcome}, format(index + 1, "032x"),
                                                      "watch", state=publications[index])
                            if admit(index, response) != step:
                                raise ValueError("poll_step")
                    latency.append((time.monotonic() - tick) * 1000)
                    if step % 4 == 0:
                        samples.append(await sampled(sampler, roles))
                    await asyncio.sleep(max(0, args.interval - (time.monotonic() - tick)))
                elapsed = time.monotonic() - started
                samples.append(await sampled(sampler, roles))
                after = logical_counts(clients)
                bytes_after = payload_bytes(clients)
                traffic = {key: after.get(key, 0) - before.get(key, 0) for key in set(before) | set(after)}
                if traffic["proofRequests"] != args.steps * fanout or traffic["requestTimeouts"]:
                    raise ValueError("unmatched_proof_work")
                if traffic.get("received:data", 0) != (args.steps * fanout if mode == "push" else 0):
                    raise ValueError("unmatched_push_work")
                measured = resources(samples)
                if measured["errors"]:
                    raise ValueError("accounting_roles_changed")
                source_after = await rpc(root / "native.sock", {"operation": "inspect"})
                if source_after["counts"]["snapshot"] - source_before["counts"]["snapshot"] != args.steps * fanout:
                    raise ValueError("unmatched_native_acquisitions")
                result = {"status": "passed", "carrier": carrier, "fanout": fanout, "mode": mode,
                    "expired": expired, "rows": args.rows, "steps": args.steps, "intervalSeconds": args.interval,
                    "elapsedSeconds": elapsed, "traffic": traffic, "trace": trace_hashes,
                    "canonicalJsonBytes": {key: bytes_after[key] - bytes_before[key] for key in bytes_before},
                    "initialTrace": initial["trace"], "resources": measured, "latencyMs": latency,
                    "latencyMedianMs": statistics.median(latency), "consumerAdmissions": admissions,
                    "sourceCountsBefore": source_before["counts"], "sourceCountsAfter": source_after["counts"],
                    "sampleScope": "before/after and every fourth step; own ticks, sampled memory; excludes setup/cleanup",
                    "scope": "loopback controlled synthetic Tmux cache; remote nonce proof semantics on every carrier; no ordinary cadence or native collector"}
            finally:
                cleanup_errors = []
                for task in consumers:
                    task.cancel()
                await asyncio.gather(*consumers, return_exceptions=True)
                for stream in streams:
                    await stream.aclose()
                for guard in guards:
                    guard.disconnect()
                for client in clients:
                    await client.close()
                if children and hub.returncode is None:
                    try:
                        async with asyncio.timeout(3):
                            while (await rpc(root / "native.sock", {"operation": "inspect"}))["watchers"]:
                                await asyncio.sleep(.01)
                    except Exception as error:
                        cleanup_errors.append(error)
                for child in reversed(children):
                    try:
                        await retire(child)
                    except Exception as error:
                        cleanup_errors.append(error)
                if cleanup_errors:
                    original = sys.exc_info()[1]
                    raise ExceptionGroup("case_cleanup_failed", ([original] if isinstance(original, Exception) else []) + cleanup_errors)
            if any(not c.channel.closed for c in clients):
                raise ValueError("channel_not_retired")
            result["cleanup"] = True
            result["agentImported"] = any(name == "agent_observer" or name.startswith("agent_observer.") for name in sys.modules)
            if result["agentImported"]:
                raise ValueError("agent_imported_in_tmux_benchmark")
            result["readerMetrics"] = [reader.inspect() for reader in readers]
            if any(m["activeConnections"] or m["cleanupFailures"] for m in result["readerMetrics"]):
                raise ValueError("reader_cleanup")
    return result


async def run(args):
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise ValueError("output_not_empty")
    manifest = inputs()
    (args.output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for carrier in args.carriers:
        for fanout in args.fanout:
            for mode in args.modes:
                value = await case(args, carrier, fanout, mode, args.expired)
                path = args.output / f"{carrier}-{fanout}-{mode}.json"
                path.write_text(json.dumps(value, indent=2) + "\n")
                print(canonical({key: value[key] for key in ("carrier", "fanout", "mode", "status", "elapsedSeconds", "latencyMedianMs")}), flush=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--carriers", nargs="+", choices=("ipc", "ssh", "wss"), default=["ipc", "ssh", "wss"])
    parser.add_argument("--fanout", nargs="+", type=int, choices=(1, 2, 4), default=[1])
    parser.add_argument("--modes", nargs="+", choices=("poll", "push"), default=["poll", "push"])
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--interval", type=float, default=.05)
    parser.add_argument("--expired", action="store_true")
    args = parser.parse_args()
    if not args.output.is_absolute() or not 1 <= args.steps <= 100 or not .01 <= args.interval <= .1:
        parser.error("bounded_absolute_case_inputs")
    asyncio.run(run(args))
