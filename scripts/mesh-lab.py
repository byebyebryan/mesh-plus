"""Owned synthetic transport lab; never imports or collects native provider state.

Each measurement runs in a fresh child process. SSH uses disposable localhost
keys/sshd and the repository's reviewed SSH fixture, not operational hosts.
"""

import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import mesh_plus
from mesh_plus.bridge import Bridge, Publication
from mesh_plus.client import Client, DeliveryError
from mesh_plus.diagnostics import probe
from mesh_plus.protocol import check
from mesh_plus.transport import IPCServer, connect_ipc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from ssh_fixture import ssh_channel  # noqa: E402


class Synthetic:
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot", "proof", "subscribe")

    def __init__(self, host="fixture-host", size=4096):
        self.host, self.padding = host, "x" * size
        self.watchers = 0
        self.restart = False

    def validate(self, payload):
        check(type(payload.get("value")) is int and isinstance(payload.get("padding"), str), "synthetic_payload")

    async def snapshot(self, parameters):
        if parameters.get("fail"):
            raise ValueError("private synthetic failure")
        await asyncio.sleep(parameters.get("delay", 0))
        return {"value": 0, "padding": self.padding}

    async def proof(self, parameters):
        # Measures full-payload transport cost only. Not an Observer receipt proof.
        return await self.snapshot(parameters)

    async def watch(self):
        self.watchers += 1
        try:
            value = 0
            while True:
                yield Publication({"value": value, "padding": self.padding},
                                  "epoch_2" if self.restart else "epoch_1", {"value": value})
                value += 1
                await asyncio.sleep(.05)
        finally:
            self.watchers -= 1


class OwnedResources:
    """Sample only this fresh worker and its descendants; never scan other processes."""

    def __init__(self):
        self.peak_processes = self.peak_rss = 0
        self.cpu = {}

    def sample(self):
        pending, seen, rss = [os.getpid()], set(), 0
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            try:
                base = Path("/proc") / str(pid)
                fields = (base / "stat").read_text().rsplit(")", 1)[1].split()
                ticks = int(fields[11]) + int(fields[12])
                identity = (pid, fields[19])  # Include start time to resist PID reuse.
                first, last = self.cpu.get(identity, (ticks, ticks))
                self.cpu[identity] = first, max(last, ticks)
                rss += max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE") // 1024
                pending.extend(int(value) for value in (base / "task" / str(pid) / "children").read_text().split())
                seen.add(pid)
            except (OSError, ValueError, IndexError):
                # Short-lived processes can disappear between reads.
                continue
        self.peak_processes = max(self.peak_processes, len(seen))
        self.peak_rss = max(self.peak_rss, rss)

    async def watch(self):
        while True:
            self.sample()
            await asyncio.sleep(.02)

    def report(self):
        return {"sampledPeakOwnedProcesses": self.peak_processes,
                "sampledPeakAggregateRssKiB": self.peak_rss,
                "sampledOwnedCpuDeltaMs": round(sum(last - first for first, last in self.cpu.values()) *
                                               1000 / os.sysconf("SC_CLK_TCK"), 3)}


async def connect(channel, source):
    return await Client.connect(channel, host=source.host, source=source.source,
                                profile=source.profile, codec=source.validate)


async def next_data(subscription):
    while True:
        frame = await asyncio.wait_for(anext(subscription), 3)
        if frame["kind"] == "data":
            return frame


@contextlib.asynccontextmanager
async def endpoint(backend, source):
    # StrictModes requires private home ancestry for disposable SSH keys.
    with tempfile.TemporaryDirectory(prefix=".mesh-lab-", dir=Path.home() if backend == "ssh" else None) as name:
        directory = Path(name)
        if backend == "ipc":
            server = await IPCServer(directory / "lab.sock", Bridge(source).serve).start()
            try:
                yield lambda: connect_ipc(directory / "lab.sock")
            finally:
                await server.close()
        else:
            command = [sys.executable, str(Path(__file__).resolve()), "--stdio", "--size", str(len(source.padding)),
                       "--host", source.host]
            async with ssh_channel(directory, command, source.source) as channel:
                used = False
                async def owned():
                    nonlocal used
                    check(not used, "lab_ssh_single_connection")
                    used = True
                    return channel
                yield owned


async def fault_pass():
    source = Synthetic()
    async with endpoint("ipc", source) as channel:
        client = await connect(await channel(), source)
        try:
            sub = await client.subscribe()
            await next_data(sub)
            try:
                await client.request(parameters={"fail": True})
            except DeliveryError as error:
                check(error.code == "source_unavailable", "lab_source_failure")
            else:
                raise AssertionError("source failure accepted")
            for _ in range(20):
                try:
                    await client.request(parameters={"delay": .1}, timeout_ms=10)
                except (TimeoutError, DeliveryError):
                    pass
                else:
                    raise AssertionError("deadline did not fire")
            tasks = [asyncio.create_task(client.request(parameters={"delay": .2})) for _ in range(4)]
            await asyncio.sleep(.01)
            for task in tasks:
                task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            check(all(isinstance(result, asyncio.CancelledError) for result in results), "lab_cancel")
            await client.request()
            await sub.close()
            check(client.inspect()["pendingRequests"] == 0, "lab_requests_leaked")
            check(client.inspect()["bufferedBytes"] == 0, "lab_buffer_leaked")
            restarted = await client.subscribe()
            await next_data(restarted)
            source.restart = True
            try:
                await next_data(restarted)
            except DeliveryError as error:
                check(error.code == "publisher_restart", "lab_restart")
            else:
                raise AssertionError("publisher epoch change accepted")
            await restarted.close()
            await client.request()
        finally:
            await client.close()
        source.restart = False
        for _ in range(20):
            replacement = await connect(await channel(), source)
            await replacement.request()
            await replacement.close()
        report = await probe(lambda: connect_channel(channel, source), mode="subscribe")
        check(report["ok"], "lab_probe")
    check(source.watchers == 0, "lab_watchers_leaked")
    return {"ok": True, "cases": ["source-failure-isolation", "20-deadlines", "cancellation-burst",
                                   "publisher-restart", "20-reconnections", "push-probe", "owned-cleanup"]}


async def connect_channel(channel, source):
    return await connect(await channel(), source)


async def ssh_fault_pass():
    for _ in range(2):
        source = Synthetic()
        async with endpoint("ssh", source) as channel:
            client = await connect(await channel(), source)
            try:
                sub = await client.subscribe()
                await next_data(sub)
                try:
                    await client.request(parameters={"delay": .2}, timeout_ms=15)
                except (TimeoutError, DeliveryError):
                    pass
                else:
                    raise AssertionError("SSH deadline did not fire")
                await client.request()
                pending = asyncio.create_task(client.request(parameters={"delay": 1}))
                await asyncio.sleep(.02)
                await client.channel.close()
                try:
                    await asyncio.wait_for(pending, 1)
                except (EOFError, DeliveryError, ConnectionError):
                    pass
                else:
                    raise AssertionError("disconnect did not terminate request")
            finally:
                await client.close()
    return {"ok": True, "cases": ["deadline-isolation", "push-baseline", "disconnect-wakes-request", "fresh-SSH-reconnect"]}


async def measure(backend, hosts, readers, size, rounds):
    check(1 <= hosts <= 16 and 1 <= readers <= 8 and 1 <= rounds <= 100 and
          0 <= size <= 8 * 1024 * 1024 and hosts * readers * size <= 64 * 1024 * 1024, "lab_capacity")
    check(backend == "ipc" or readers == 1, "lab_ssh_readers")
    started, cpu = time.perf_counter(), time.process_time()
    clients, subscriptions, snapshots, proofs, waits = [], [], [], [], []
    async with contextlib.AsyncExitStack() as stack:
        try:
            for host in range(hosts):
                source = Synthetic(f"fixture-host-{host}", size)
                channel = await stack.enter_async_context(endpoint(backend, source))
                for _ in range(readers):
                    client = await connect(await channel(), source)
                    clients.append(client)
                    sub = await client.subscribe()
                    subscriptions.append(sub)
                    await next_data(sub)
            setup = time.perf_counter() - started
            for _ in range(rounds):
                for client, sub in zip(clients, subscriptions):
                    for operation, samples in (("snapshot", snapshots), ("proof", proofs)):
                        before = time.perf_counter()
                        await client.request(operation, timeout_ms=10000)
                        samples.append((time.perf_counter() - before) * 1000)
                    before = time.perf_counter()
                    await next_data(sub)
                    waits.append((time.perf_counter() - before) * 1000)
            metrics = [client.inspect() for client in clients]
        finally:
            for client in clients:
                await client.close()
    elapsed = time.perf_counter() - started
    def summary(samples):
        ordered = sorted(samples)
        return {"meanMs": round(sum(samples) / len(samples), 3),
                "p95Ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 3)}
    return {"backend": backend, "hosts": hosts, "readersPerHost": readers, "payloadPaddingBytes": size,
            "rounds": rounds, "connections": len(clients), "setupMs": round(setup * 1000, 3),
            "elapsedMs": round(elapsed * 1000, 3), "selfCpuMs": round((time.process_time() - cpu) * 1000, 3),
            "reapedChildrenCpuMs": round(sum(resource.getrusage(resource.RUSAGE_CHILDREN)[:2]) * 1000, 3),
            "selfPeakRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "snapshot": summary(snapshots), "syntheticFullPayloadProof": summary(proofs),
            "nextPushDataWait": summary(waits),
            "applicationReceivedBytes": sum(item["channel"]["receivedBytes"] for item in metrics),
            "applicationSentBytes": sum(item["channel"]["sentBytes"] for item in metrics),
            "maxSampledBufferedBytesPerClient": max(item["bufferedBytes"] for item in metrics)}


async def run(args):
    if args.stdio:
        from mesh_plus.cli import stdio_channel
        await Bridge(Synthetic(args.host, args.size)).serve(await stdio_channel())
        return
    if args.case:
        resources = OwnedResources()
        sampling = asyncio.create_task(resources.watch())
        try:
            result = await asyncio.wait_for(measure(args.backend, args.hosts, args.readers, args.size, args.rounds), 120)
            resources.sample()
            result.update(resources.report())
            print(json.dumps(result))
        finally:
            sampling.cancel()
            await asyncio.gather(sampling, return_exceptions=True)
        return
    report = {"format": "mesh-plus.lab.v1", "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
              "faults": await fault_pass(), "measurements": [],
              "inputs": {"python": sys.version.split()[0], "meshVersion": mesh_plus.__version__,
                         "jsonschemaVersion": importlib.metadata.version("jsonschema"), "kernel": platform.release(),
                         "labSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         "sshFixtureSha256": hashlib.sha256((ROOT / "tests/ssh_fixture.py").read_bytes()).hexdigest(),
                         "lockSha256": hashlib.sha256((ROOT / "contracts/LOCK.json").read_bytes()).hexdigest(),
                         "runtimeDigests": {str(path.relative_to(Path(mesh_plus.__file__).parent)): hashlib.sha256(path.read_bytes()).hexdigest()
                                            for path in sorted(Path(mesh_plus.__file__).parent.rglob("*"))
                                            if path.is_file() and path.suffix in {".py", ".json"}}},
              "limits": ["Synthetic localhost only; no Observer receipt, fleet WAN or suspend acceptance",
                         "Proof is artificial full-payload cost, not proof correctness",
                         "RSS is fresh worker peak only; excludes SSH descendants and kernel buffers",
                         "CPU children covers reaped direct children, not the complete SSH process tree",
                         "Owned tree sampled every 20ms; misses short-lived processes and blocked-loop peaks",
                         "Sampled CPU is first-to-last observation delta; sampled aggregate RSS double-counts shared pages",
                         "Bytes are completed application JSON lines including LF, not encrypted network bytes",
                         "Push wait includes cadence and queued data; not publisher-to-consumer latency",
                         "Buffered bytes is an end-of-work sample, not a high-water bound",
                         "SSH fixture uses one reader per host; multi-reader SSH pool savings remain unmeasured"]}
    if args.faults_only:
        print(json.dumps(report, indent=2))
        return
    if args.ssh:
        report["sshFaults"] = await ssh_fault_pass()
    matrix = [(1, 1, 4096), (4, 1, 4096), (16, 1, 4096), (1, 8, 4096), (4, 2, 4096),
              (1, 1, 1024 * 1024), (1, 2, 1024 * 1024), (1, 1, 8 * 1024 * 1024)]
    if args.ssh:
        matrix += [(1, 1, 4096), (4, 1, 4096), (1, 1, 1024 * 1024)]
    for index, (hosts, readers, size) in enumerate(matrix):
        backend = "ssh" if index >= 8 else "ipc"
        child = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()), "--case",
                    "--backend", backend, "--hosts", str(hosts), "--readers", str(readers), "--size", str(size),
                    "--rounds", str(args.rounds), stdout=asyncio.subprocess.PIPE)
        try:
            output, _ = await asyncio.wait_for(child.communicate(), 150)
            check(child.returncode == 0, "lab_case_failed")
            report["measurements"].append(json.loads(output))
            print(f"completed {backend}: {hosts} hosts, {readers} readers/host, {size} padding bytes", file=sys.stderr)
        finally:
            if child.returncode is None:
                child.terminate()
                try:
                    await asyncio.wait_for(child.wait(), 10)
                except TimeoutError:
                    child.kill()
                    await child.wait()
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--ssh", action="store_true")
    parser.add_argument("--faults-only", action="store_true")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--case", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--stdio", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", default="fixture-host")
    parser.add_argument("--backend", choices=("ipc", "ssh"), default="ipc")
    parser.add_argument("--hosts", type=int, default=1)
    parser.add_argument("--readers", type=int, default=1)
    parser.add_argument("--size", type=int, default=4096)
    args = parser.parse_args()
    async def managed():
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        try:
            await run(args)
        finally:
            loop.remove_signal_handler(signal.SIGTERM)
    asyncio.run(managed())


if __name__ == "__main__":
    main()
