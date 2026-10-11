"""Fresh-process ABBA study, full native validation, matched publisher workers."""

import argparse
import asyncio
import contextlib
import importlib.metadata
import json
import os
import platform
import resource
import ssl
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from carrier import connect
from configuration import Binding, StudyReader
from fixtures import certificates, contexts

from mesh_plus.api import Client, Endpoint, Reader, ReadGuard, ReferenceProfile
from mesh_plus.evidence import clock_domain, digest
from mesh_plus.protocol import check
from mesh_plus.testing.ssh_carrier import _stop, ssh_server
from mesh_plus.transport import boottime_ms, connect_ipc

STUDY = Path(__file__).resolve().parent


class Samples:
    def __init__(self, publishers):
        self.publishers = publishers
        self.cpu = {}
        self.peak_rss = self.peak_processes = 0

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
                identity = (pid, fields[19])
                first, last = self.cpu.get(identity, (ticks, ticks))
                self.cpu[identity] = first, max(last, ticks)
                rss += max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE") // 1024
                pending.extend(int(v) for v in (base / "task" / str(pid) / "children").read_text().split())
                seen.add(pid)
            except (OSError, ValueError, IndexError):
                continue
        self.peak_rss = max(self.peak_rss, rss)
        self.peak_processes = max(self.peak_processes, len(seen))

    async def watch(self):
        while True:
            self.sample()
            await asyncio.sleep(.02)

    def report(self):
        per_pid = {pid: (last - first) * 1000 / os.sysconf("SC_CLK_TCK")
                   for (pid, _), (first, last) in self.cpu.items()}
        return {"sampledTreeCpuMs": sum(per_pid.values()), "sampledWorkerCpuMs": per_pid.get(os.getpid(), 0),
                "sampledPublisherCpuMs": sum(per_pid.get(pid, 0) for pid in self.publishers),
                "sampledPeakTreeRssKiB": self.peak_rss, "sampledPeakProcesses": self.peak_processes}


async def run(args):
    rows = 256 if args.scenario == "large" else 0
    count = 4 if args.scenario == "four" else 1
    profile = ReferenceProfile(args.domain)
    revision = digest({"study": 1})
    clients, nodes, readers, tasks = [], [], [], []
    watches, guards, views, states = [], [], [], []
    cold, latencies = [], []
    checks = {"baseline": 0, "updates": 0, "unavailable": 0, "recoveries": 0,
              "expiredRuntime": 0, "guardAdmissions": 0}
    with tempfile.TemporaryDirectory(prefix=".mesh-wss-measure-", dir=Path.home()) as name:
        root = Path(name)
        if args.carrier == "wss":
            await asyncio.to_thread(certificates, root)
            _, tls = contexts(root)
        async with contextlib.AsyncExitStack() as stack:
            try:
                for index in range(count):
                    directory = root / str(index)
                    directory.mkdir(mode=0o700)
                    command = [sys.executable, str(STUDY / "node.py"), "--root", str(directory),
                               "--domain", args.domain, "--carrier", args.carrier, "--rows", str(rows)]
                    if args.scenario != "idle" and not args.cold:
                        command.append("--updates")
                    node = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                                                               stdout=asyncio.subprocess.PIPE,
                                                               stderr=asyncio.subprocess.PIPE)
                    nodes.append(node)
                    raw = await asyncio.wait_for(node.stdout.readline(), 8)
                    if not raw:
                        raise RuntimeError((await node.stderr.read()).decode()[-4096:])
                    address = json.loads(raw)["address"]
                    if args.carrier == "ssh":
                        ssh_directory = directory / "ssh"
                        ssh_directory.mkdir(mode=0o700)
                        # Persistent source is identical to WSS. socat is just the
                        # forced raw stdio bridge; its process/cost is included.
                        opening = await stack.enter_async_context(ssh_server(
                            ssh_directory, ["/usr/bin/socat", "STDIO", "UNIX-CONNECT:" + address], "default"))
                    elif args.carrier == "ipc":
                        async def opening(path=address):
                            return await connect_ipc(path)
                    else:
                        async def opening(url=address):
                            return await connect(url, tls)
                    codec = profile.bind("beta", "default")
                    binding = Binding("beta", "default", profile.descriptor.profile_id,
                                      address, 0, revision)
                    async def connection(open_channel=opening, codec=codec):
                        client = await Client.connect(await open_channel(), host="beta", source="default",
                                                      profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
                        clients.append(client)
                        return client
                    async def catalog():
                        return revision
                    endpoint = Endpoint("beta", False, binding.token, connection, codec)
                    if args.carrier == "wss":
                        reader = StudyReader(args.domain, [endpoint], local_host="alpha", profile=profile,
                                             catalog_revision=revision, catalog_check=catalog, bindings=(binding,))
                    else:
                        reader = Reader(args.domain, [endpoint], local_host="alpha", profile=profile,
                                        catalog_revision=revision, catalog_check=catalog)
                    readers.append(reader)
                if args.cold:
                    for _ in range(10):
                        start = time.perf_counter()
                        view = await readers[0].snapshot()
                        check(view["mesh"]["status"] == "complete", "study_cold_proof")
                        cold.append(1000 * (time.perf_counter() - start))
                    result = {"domain": args.domain, "carrier": args.carrier, "scenario": "cold",
                              "samplesMs": cold, "proofs": 10, "reader": readers[0].inspect()}
                    return result
                ready_events = []
                for index, reader in enumerate(readers):
                    request = (str(index + 1) * 32)[:32]
                    watch = reader.watch(request_id=request)
                    watches.append(watch)
                    guard = ReadGuard(args.domain, request, profile=profile)
                    guards.append(guard)
                    views.append(None)
                    states.append({"ready": False, "revision": None, "expiry": False})
                    ready_event = asyncio.Event()
                    ready_events.append(ready_event)
                    async def consume(index=index, watch=watch, guard=guard, ready_event=ready_event):
                        async for view in watch:
                            guard.accept(view)
                            checks["guardAdmissions"] += 1
                            check("mesh" in view, "study_unexpected_terminal")
                            host = view["mesh"]["hosts"][0]
                            ready = host["delivery"]["status"] == "ready"
                            state = states[index]
                            if ready:
                                expected_path = "wss" if args.carrier == "wss" else "ssh"
                                check(host["delivery"]["path"] == expected_path, "study_path")
                                proof = host["delivery"]["proof"]
                                check(proof is not None, "study_full_proof")
                                latencies.append(proof["receivedAtMs"] - proof["sentAtMs"])
                                version = host["owner"]["service"]["viewRevision"]
                                if state["revision"] is not None and state["revision"] != version:
                                    checks["updates"] += 1
                                state["revision"] = version
                                if not ready_event.is_set():
                                    checks["baseline"] += 1
                                    ready_event.set()
                                elif not state["ready"]:
                                    checks["recoveries"] += 1
                                expired = all(r["health"] not in {"current", "partial"} for r in host["receipts"]
                                              if args.domain == "tmux" or r["component"] == "runtime")
                                if expired and not state["expiry"]:
                                    checks["expiredRuntime"] += 1
                                    state["expiry"] = True
                            elif state["ready"]:
                                checks["unavailable"] += 1
                                check(not guard.current(boottime_ms(), clock_domain()), "study_revoke")
                            state["ready"] = ready
                            views[index] = view
                    tasks.append(asyncio.create_task(consume()))
                await asyncio.wait_for(asyncio.gather(*(event.wait() for event in ready_events)), 10)
                samples = Samples([node.pid for node in nodes])
                sampler = asyncio.create_task(samples.watch())
                started = time.perf_counter()
                usage = resource.getrusage(resource.RUSAGE_SELF)
                if args.scenario == "recovery":
                    await asyncio.sleep(args.seconds / 2)
                    nodes[0].stdin.write(b'{"operation":"drop"}\n')
                    await nodes[0].stdin.drain()
                    await asyncio.sleep(max(0, args.seconds - (time.perf_counter() - started)))
                else:
                    await asyncio.sleep(args.seconds)
                elapsed = time.perf_counter() - started
                end_usage = resource.getrusage(resource.RUSAGE_SELF)
                samples.sample()
                sampler.cancel()
                await asyncio.gather(sampler, return_exceptions=True)
                for task in tasks:
                    check(not task.done(), "study_watch_ended")
                check(checks["baseline"] == count, "study_baselines")
                if args.scenario != "idle":
                    check(checks["updates"] >= count, "study_updates")
                if args.scenario == "recovery":
                    check(checks["unavailable"] >= 1 and checks["recoveries"] >= 1, "study_recovery")
                result = {"domain": args.domain, "carrier": args.carrier, "scenario": args.scenario,
                          "elapsedSeconds": elapsed, "readers": count, "rows": rows or "original-fixture",
                          "proofIntervalSeconds": 3 if args.domain == "tmux" else 10,
                          "checks": checks.copy(), "proofRttMs": latencies,
                          "steadyWorkerCpuMs": 1000 * (end_usage.ru_utime + end_usage.ru_stime -
                                                       usage.ru_utime - usage.ru_stime), **samples.report(),
                          "metrics": [reader.inspect() for reader in readers],
                          "loadAverage": list(os.getloadavg())}
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                for watch in watches:
                    await watch.aclose()
                for client in clients:
                    await client.close()
                for node in nodes:
                    await _stop(node)
                    check(node.returncode == 0, "study_node_cleanup")
                check(all(reader.inspect()["activeConnections"] == 0 for reader in readers), "study_reader_cleanup")
                check(all(client.channel.closed for client in clients), "study_channel_cleanup")
                if "result" in locals():
                    result["cleanup"] = {"publisherProcessesReaped": len(nodes), "channelsClosed": len(clients),
                                         "activeReaderConnections": 0, "listenersClosed": True}
        result["cleanup"] = {"publisherProcessesReaped": len(nodes), "channelsClosed": len(clients),
                             "activeReaderConnections": 0, "listenersClosed": True}
        return result


async def matrix(args):
    results = []
    for domain in ("tmux", "agent"):
        for scenario in ("idle", "four", "large", "recovery"):
            for carrier in ("ssh", "wss", "wss", "ssh"):
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--domain", domain,
                           "--scenario", scenario, "--carrier", carrier, "--seconds", str(args.seconds)]
                process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                               stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), args.seconds + 40)
                    if process.returncode:
                        # Parent console diagnostic; public report contains no path/key logs.
                        raise RuntimeError(stderr.decode()[-4096:])
                    result = json.loads(stdout)
                    result["order"] = len(results) + 1
                    results.append(result)
                    (Path(args.output) / "runs.json").write_text(json.dumps(results, indent=2) + "\n")
                    print(f"{len(results)}/32 {domain} {scenario} {carrier} passed", file=sys.stderr, flush=True)
                finally:
                    await _stop(process)
    extras = []
    for domain in ("tmux", "agent"):
        for carrier in ("ssh", "wss", "ipc"):
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--domain", domain,
                       "--scenario", "idle", "--carrier", carrier, "--seconds", str(args.seconds)]
            if carrier != "ipc":
                command.append("--cold")
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                           stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), args.seconds + 40)
                if process.returncode:
                    raise RuntimeError(stderr.decode()[-4096:])
                extras.append(json.loads(stdout))
                (Path(args.output) / "extras.json").write_text(json.dumps(extras, indent=2) + "\n")
            finally:
                await _stop(process)
    report = {"format": "mesh-plus.wss-study.measurement.v1", "status": "passed", "runs": len(results),
              "steadySeconds": args.seconds, "extraRuns": len(extras), "coldAcquisitions": 40,
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "tls": ssl.OPENSSL_VERSION, "websockets": importlib.metadata.version("websockets"),
              "topology": "one persistent separate publisher/Bridge worker per Reader; SSH includes forced socat relay",
              "samplingSeconds": .02, "cpuScope": "steady worker, publisher and sampled owned descendants",
              "exclusions": ["short lived descendants between samples", "TLS/NIC bytes", "WAN",
                             "physical suspend", "global RSS bound", "statistical tail latency"],
              "byteScopes": ["completed JSON lines including LF (SSH/IPC)", "completed JSON messages (WSS)",
                             "WebSocket framing before TLS available on raw WSS Channel only"]}
    (Path(args.output) / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--domain", choices=("tmux", "agent"), default="tmux")
    parser.add_argument("--carrier", choices=("ipc", "ssh", "wss"), default="wss")
    parser.add_argument("--scenario", choices=("idle", "four", "large", "recovery"), default="idle")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--cold", action="store_true")
    parser.add_argument("--output", default="/tmp/mesh-wss-study/measurements")
    args = parser.parse_args()
    check(args.seconds > 0, "study_duration")
    if args.worker:
        print(json.dumps(asyncio.run(run(args)), indent=2))
    else:
        Path(args.output).mkdir(parents=True, exist_ok=True)
        asyncio.run(matrix(args))
