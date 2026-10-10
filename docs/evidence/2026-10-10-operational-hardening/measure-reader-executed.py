"""Fresh-process native-profile Reader measurements over owned IPC/SSH fixtures.

No operational hosts, native collectors or installed service selection. Remote
semantics are identical for both carriers, including nonce-bound full proofs.
"""

import argparse
import asyncio
import contextlib
import copy
import cProfile
import hashlib
import importlib.util
import json
import resource
import sys
import tempfile
import time
from pathlib import Path

import mesh_plus
from mesh_plus.bridge import Bridge, Publication
from mesh_plus.client import Client
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import IPCServer, connect_ipc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from ssh_fixture import ssh_server  # noqa: E402
from test_reader_runtime import CachedPublisher  # noqa: E402

spec = importlib.util.spec_from_file_location("owned_lab", ROOT / "scripts/mesh-lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class Publisher(CachedPublisher):
    def __init__(self, domain, updates, rows=0, frame=None):
        native = json.loads(frame.read_bytes()) if frame else None
        host = (native["source"]["hostId"] if domain == "tmux" else native["hostScope"]) if native else "remote"
        super().__init__(domain, host)
        if native is not None:
            self.cached.frame = native
            self.cached.adapter.native(native)
        self.updates = updates
        if not rows:
            return
        template = self.cached.frame["snapshot"]["sessions"][0]
        sessions = []
        for index in range(rows):
            row = copy.deepcopy(template)
            if domain == "tmux":
                row["sessionId"] = "$" + str(index + 1)
            else:
                identity = f"00000000-0000-0000-0000-{index + 1:012d}"
                row["identity"]["nativeId"] = identity
                row["nativeIds"]["threadId"] = identity
                row["nativeIds"]["sessionTreeRootId"] = identity
            sessions.append(row)
        self.cached.frame["snapshot"]["sessions"] = sessions
        self.cached.adapter.native(self.cached.frame)
        self.updates = updates

    async def watch(self):
        revision = 0
        while True:
            yield Publication(await self.snapshot({}), "epoch_1", {"revision": revision})
            if not self.updates:
                await asyncio.Event().wait()
            await asyncio.sleep(1)
            revision += 1
            self.cached.frame["viewRevision"] += 1
            # Receipt times deliberately stay unchanged: push is not collection.


async def measure(args):
    resources = lab.OwnedResources()
    sampling = asyncio.create_task(resources.watch())
    publisher = Publisher(args.domain, args.updates, args.rows, args.frame)
    try:
        with tempfile.TemporaryDirectory(prefix=".mesh-reader-lab-", dir=Path.home()) as name:
            root = Path(name)
            async with contextlib.AsyncExitStack() as stack:
                if args.carrier == "ssh":
                    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--stdio",
                               "--domain", args.domain, "--rows", str(args.rows),
                               *(["--frame", str(args.frame)] if args.frame else []),
                               *(["--updates"] if args.updates else [])]
                    channel = await stack.enter_async_context(ssh_server(root, command, "default"))
                else:
                    server = await IPCServer(root / "mesh.sock", Bridge(publisher).serve).start()
                    stack.push_async_callback(server.close)
                    async def channel():
                        return await connect_ipc(root / "mesh.sock")

                async def connect():
                    return await Client.connect(await channel(), host=publisher.host, source="default",
                                                profile=publisher.profile, codec=publisher.validate)
                async def catalog():
                    return "sha256:" + "b" * 64
                readers = [Reader(args.domain, [Endpoint(publisher.host, False, "sha256:" + "a" * 64, connect)],
                                  local_host="local", catalog_revision=await catalog(), catalog_check=catalog)
                           for _ in range(args.readers)]
                ready = [asyncio.Event() for _ in readers]
                views = [0] * len(readers)
                latencies = [[] for _ in readers]
                async def consume(index, reader):
                    if args.operation == "snapshot":
                        while True:
                            started = time.monotonic()
                            view = await reader.snapshot()
                            check_result = view.get("mesh", {}).get("status") == "complete"
                            if not check_result:
                                raise AssertionError("Snapshot incomplete")
                            latencies[index].append(round((time.monotonic() - started) * 1000, 3))
                            views[index] += 1
                            ready[index].set()
                            await asyncio.sleep(args.proof_interval)
                    iterator = reader.watch(proof_interval=args.proof_interval)
                    try:
                        async for view in iterator:
                            if "error" in view:
                                raise AssertionError("Reader terminated")
                            views[index] += 1
                            if view["mesh"]["status"] == "complete":
                                ready[index].set()
                    finally:
                        await iterator.aclose()
                tasks = [asyncio.create_task(consume(i, reader)) for i, reader in enumerate(readers)]
                try:
                    await asyncio.wait_for(asyncio.gather(*(event.wait() for event in ready)), 20)
                    start = time.monotonic()
                    cpu_start = resource.getrusage(resource.RUSAGE_SELF)
                    profiler = cProfile.Profile() if args.profile else None
                    if profiler:
                        profiler.enable()
                    await asyncio.sleep(args.seconds)
                    if profiler:
                        profiler.disable()
                    elapsed = time.monotonic() - start
                    cpu_end = resource.getrusage(resource.RUSAGE_SELF)
                    failure = [task.exception() for task in tasks if task.done() and not task.cancelled()]
                    if any(failure):
                        raise AssertionError("Reader failed during measurement")
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                summaries = [reader.inspect() for reader in readers]
                if any(summary["activeConnections"] or summary["cleanupFailures"] or summary["partial"]
                       for summary in summaries):
                    raise AssertionError("Incomplete instrumentation or cleanup")
                return {"domain": args.domain, "carrier": args.carrier, "readers": args.readers,
                        "operation": args.operation, "snapshotLatencyMs": latencies,
                        "fixtureRows": len(publisher.cached.frame["snapshot"]["sessions"]), "updatesEverySeconds": 1 if args.updates else None, "proofIntervalSeconds": args.proof_interval,
                        "steadySeconds": round(elapsed, 3), "views": views, "readerMetrics": summaries,
                        "steadyWorkerCpuMs": round(1000 * (cpu_end.ru_utime + cpu_end.ru_stime -
                                                             cpu_start.ru_utime - cpu_start.ru_stime), 3),
                        "profile": None if profiler is None else sorted(
                            [{"function": (entry.code.co_name if hasattr(entry.code, "co_name") else
                                           str(entry.code)), "calls": entry.callcount,
                              "selfSeconds": round(entry.inlinetime, 6),
                              "totalSeconds": round(entry.totaltime, 6)}
                             for entry in profiler.getstats()], key=lambda row: row["selfSeconds"],
                            reverse=True)[:20],
                        **resources.report()}
    finally:
        sampling.cancel()
        await asyncio.gather(sampling, return_exceptions=True)


async def main(args):
    if args.stdio:
        from mesh_plus.cli import stdio_channel
        await Bridge(Publisher(args.domain, args.updates, args.rows, args.frame)).serve(await stdio_channel())
        return
    if args.case:
        print(json.dumps(await measure(args)))
        return
    cases = []
    for domain in ((args.domain,) if args.frame else ("tmux", "agent")):
        for readers in (1, 4):
            for updates in ((False,) if args.operation == "snapshot" else (False, True)):
                command = [sys.executable, "-B", str(Path(__file__).resolve()), "--case", "--domain", domain,
                           "--carrier", args.carrier, "--readers", str(readers), "--seconds", str(args.seconds),
                           "--operation", args.operation,
                           "--proof-interval", str(args.proof_interval), "--rows", str(args.rows),
                           *(["--frame", str(args.frame)] if args.frame else []),
                           *(["--profile"] if args.profile else []), *(["--updates"] if updates else [])]
                process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                               stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), args.seconds + 40)
                    if process.returncode:
                        raise RuntimeError(stderr.decode())
                    cases.append(json.loads(stdout))
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
    package = Path(mesh_plus.__file__).parent
    report = {"format": "mesh-plus.reader-lab.v1", "sourceVersion": mesh_plus.__version__,
              "python": sys.version.split()[0], "cases": cases,
              "input": None if args.frame is None else {
                  "kind": "private cached native replay", "bytes": args.frame.stat().st_size,
                  "sha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(),
                  "receiptTimesPreserved": True, "providerCollection": False},
              "runtimeDigests": {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(package.rglob("*")) if path.suffix in {".py", ".json"}},
              "harnessDigests": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in [Path(__file__).resolve(), ROOT / "scripts/mesh-lab.py",
                                              ROOT / "tests/ssh_fixture.py", ROOT / "tests/test_reader.py",
                                              ROOT / "tests/test_reader_runtime.py", ROOT / "tests/test_observer.py",
                                              ROOT / "reference/tmux-observer/contracts/service-v1/fixtures/ready.json",
                                              ROOT / "contracts/mesh-read-v1/examples/bridge-candidate.json"]},
              "limits": ["Frozen native fixture publishers, not ordinary fleet/provider acceptance",
                         "Framed byte totals include setup/cleanup; steady worker CPU excludes setup/cleanup",
                         "Owned 20ms process-tree samples include setup and can miss short-lived processes/peaks",
                         "CPU includes the measurement consumer; not an Observer collector cost",
                         "IPC exercises remote validity semantics for like-for-like carriage comparison",
                         "Application bytes exclude encryption, partial writes and failed handshakes",
                         "Payload scaling uses duplicated synthetic records, not large native inventory truth or prolonged operational soak acceptance"]}
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(text)
        print(json.dumps({"format": report["format"], "sourceVersion": report["sourceVersion"],
                          "cases": len(cases), "report": str(args.report)}))
    else:
        print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carrier", choices=("ipc", "ssh"), default="ipc")
    parser.add_argument("--seconds", type=int, choices=range(5, 601), default=10)
    parser.add_argument("--proof-interval", type=float, default=1)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--domain", choices=("tmux", "agent"), default="tmux")
    parser.add_argument("--readers", type=int, choices=range(1, 9), default=1)
    parser.add_argument("--updates", action="store_true")
    parser.add_argument("--rows", type=int, choices=range(0, 2049), default=0,
                        help="synthetic unique rows; zero preserves the original native fixture")
    parser.add_argument("--frame", type=Path, help="private cached native replay input; never written into reports")
    parser.add_argument("--profile", action="store_true", help="instrumented worker trace; adds profiling overhead")
    parser.add_argument("--operation", choices=("watch", "snapshot"), default="watch")
    parser.add_argument("--case", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--stdio", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not .1 <= args.proof_interval <= 60:
        parser.error("proof interval must be .1..60 seconds")
    if args.frame and (args.rows or not args.frame.is_absolute() or args.frame.stat().st_mode & 0o077):
        parser.error("frame must be an absolute private file and cannot be scaled")
    asyncio.run(main(args))
