"""Redacted, cached-only profiling of an explicitly selected operational fleet.

Run with installed Mesh and pure domain packages. No collection, route reports,
publisher restart, source configuration writes or provider actions are admitted.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

import mesh_plus
from mesh_plus.bridge import Bridge
from mesh_plus.configured_read import configured_reader
from mesh_plus.library_authority import LibraryMeshAuthority
from mesh_plus.observer import ObserverAdapter, clock_domain
from mesh_plus.transport import IPCServer, boottime_ms
from mesh_plus.view import ReadGuard, row_host


def process_tree():
    pending, found = [os.getpid()], {}
    while pending:
        pid = pending.pop()
        if pid in found:
            continue
        try:
            root = Path(f"/proc/{pid}")
            fields = (root / "stat").read_text().rpartition(") ")[2].split()
            found[pid] = {
                "cpuTicks": sum(int(fields[i]) for i in (11, 12, 13, 14)),
                "rssBytes": int(fields[21]) * os.sysconf("SC_PAGE_SIZE"),
            }
            for task in (root / "task").iterdir():
                pending.extend(int(child) for child in (task / "children").read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            continue
        if len(found) + len(pending) > 256:
            raise RuntimeError("owned_process_capacity")
    return found


async def profile(args):
    authority = LibraryMeshAuthority()
    authorities = [authority]
    readers, streams, tasks = [], [], []
    frames = [{"total": 0, "kinds": {}, "statuses": {}, "rotationRevocations": 0,
               "maxRows": 0, "firstCompleteMs": None, "hostRotations": {},
               "hostRecoveries": {}} for _ in range(args.readers)]
    started = time.monotonic()
    peak_rss = peak_processes = 0
    initial = sum(row["cpuTicks"] for row in process_tree().values())
    latest = initial
    next_progress = started + 60
    failure = None
    server = None
    temporary = tempfile.TemporaryDirectory(prefix="mesh-profile-")
    try:
        socket = args.socket
        if args.native_socket:
            catalog = await authority.load()
            socket = Path(temporary.name) / "bridge.sock"
            adapter = ObserverAdapter(args.domain, catalog.local_host, args.source, args.socket)
            server = await IPCServer(socket, Bridge(adapter).serve, max_clients=args.readers).start()
        for _ in frames:
            reader_authority = LibraryMeshAuthority()
            authorities.append(reader_authority)
            readers.append(await configured_reader(args.domain, source=args.source, socket=socket,
                                                   scope=args.scope, authority=reader_authority, report_routes=False))

        async def consume(index, reader):
            request = uuid.uuid4().hex
            guard = ReadGuard(args.domain, request)
            revoked = {}
            stream = reader.watch(proof_interval=args.proof_interval, request_id=request)
            streams.append(stream)
            try:
                async for frame in stream:
                    if "mesh" not in frame:
                        raise RuntimeError("fleet_terminal_error")
                    mesh, counters = frame["mesh"], frames[index]
                    guard.accept(frame)
                    current = guard.current(boottime_ms(), clock_domain())
                    counters["total"] += 1
                    for key, value in (("kinds", mesh["kind"]), ("statuses", mesh["status"])):
                        counters[key][value] = counters[key].get(value, 0) + 1
                    counters["maxRows"] = max(counters["maxRows"], len(frame["sessions"]))
                    if mesh["status"] == "complete" and counters["firstCompleteMs"] is None:
                        counters["firstCompleteMs"] = round((time.monotonic() - started) * 1000, 3)
                    for host in mesh["hosts"]:
                        identity, delivery = host["hostId"], host["delivery"]
                        if (delivery.get("error") or {}).get("code") == "channel_rotation_required":
                            if any(row_host(args.domain, row) == identity for row in current):
                                raise RuntimeError("rotation_retained_current_rows")
                            if revoked.get(identity) != delivery["epoch"]:
                                counters["rotationRevocations"] += 1
                                rotations = counters["hostRotations"]
                                rotations[identity] = rotations.get(identity, 0) + 1
                                revoked[identity] = delivery["epoch"]
                        elif identity in revoked and delivery["status"] == "ready":
                            if delivery["epoch"] <= revoked[identity] or mesh["kind"] != "resync":
                                raise RuntimeError("rotation_missing_fresh_resync")
                            recovered = counters["hostRecoveries"]
                            recovered[identity] = recovered.get(identity, 0) + 1
                            del revoked[identity]
            finally:
                await stream.aclose()

        tasks = [asyncio.create_task(consume(i, reader)) for i, reader in enumerate(readers)]
        while time.monotonic() - started < args.seconds:
            for task in tasks:
                if task.done():
                    await task
                    raise RuntimeError("fleet_watch_ended")
            tree = process_tree()
            peak_rss = max(peak_rss, sum(row["rssBytes"] for row in tree.values()))
            peak_processes = max(peak_processes, len(tree))
            latest = sum(row["cpuTicks"] for row in tree.values())
            if args.progress_report and time.monotonic() >= next_progress:
                args.progress_report.write_text(json.dumps({"state": "running", "frames": frames,
                                                            "elapsedSeconds": round(time.monotonic() - started, 3),
                                                            "readerMetrics": [reader.inspect() for reader in readers]},
                                                           indent=2) + "\n")
                next_progress += 60
            await asyncio.sleep(0.1)
    except Exception as error:
        failure = type(error).__name__
    finally:
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        if any(isinstance(result, Exception) for result in results):
            failure = failure or "ConsumerFailure"
        if server is not None:
            await server.close()
        for owned in authorities:
            try:
                owned.close()
            except Exception as error:
                failure = failure or type(error).__name__
        temporary.cleanup()
    elapsed = time.monotonic() - started
    metrics = [reader.inspect() for reader in readers]
    accepted = (failure is None and all(frame["firstCompleteMs"] is not None for frame in frames)
                and all(not m["partial"] and not m["activeConnections"] and not m["cleanupFailures"] for m in metrics))
    if args.minimum_host_rotations:
        accepted = accepted and all(
            set(frame["hostRotations"]) == {endpoint.host for endpoint in reader.endpoints} and
            all(count >= args.minimum_host_rotations and frame["hostRecoveries"].get(host, 0) == count
                for host, count in frame["hostRotations"].items())
            for frame, reader in zip(frames, readers, strict=True))
    package = Path(mesh_plus.__file__).parent
    return {
        "format": "mesh-plus.operational-profile.v1", "state": "passed" if accepted else "failed",
        "failureType": failure, "meshVersion": mesh_plus.__version__, "python": sys.version.split()[0],
        "domain": args.domain, "scope": args.scope, "readers": args.readers,
        "ownedLocalBridge": args.native_socket,
        "proofIntervalSeconds": args.proof_interval or (3 if args.domain == "tmux" else 10),
        "minimumHostRotations": args.minimum_host_rotations,
        "elapsedSeconds": round(elapsed, 3), "frames": frames, "readerMetrics": metrics,
        "ownedCpuPercent": round(max(0, latest - initial) / os.sysconf("SC_CLK_TCK") / elapsed * 100, 3),
        "sampledPeakRssBytes": peak_rss, "sampledPeakProcesses": peak_processes,
        "runtimeDigests": {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(package.rglob("*")) if p.suffix in {".py", ".json"}},
        "domainContractSha256": hashlib.sha256(Path(__import__(
            "agent_observer.contract" if args.domain == "agent" else "tmux_observer.delivery",
            fromlist=["__file__"]).__file__).read_bytes()).hexdigest(),
        "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limits": ["Actual cached native fleet; profiling readers are additional owned consumers",
                   "Local reader descendants only; remote bridge and existing publishers excluded from resources",
                   "100ms RSS/process samples can miss peaks and short lived children",
                   "CPU includes consumer and reaped children; sampling races can distort resource totals",
                   "Framed bytes are application traffic, not encrypted NIC traffic",
                   "No independent provider truth, GUI, physical suspend or collector-cost acceptance",
                   "Rotation is accepted only when explicitly observed; elapsed time alone does not establish it"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=("tmux", "agent"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--native-socket", action="store_true", help="wrap a cached native service in an owned local bridge")
    parser.add_argument("--scope", choices=("local", "fleet"), default="fleet")
    parser.add_argument("--readers", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--proof-interval", type=float, help="additional Reader only; default is domain cadence")
    parser.add_argument("--minimum-host-rotations", type=int, default=0,
                        help="require observed revocation and fresh resync per rotating host")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--progress-report", type=Path, help="optional redacted 60-second counters")
    args = parser.parse_args()
    if not 10 <= args.seconds <= 86400:
        parser.error("seconds must be 10..86400")
    if args.proof_interval is not None and not .1 <= args.proof_interval <= 60:
        parser.error("proof interval must be .1..60 seconds")
    if not 0 <= args.minimum_host_rotations <= 100:
        parser.error("minimum host rotations must be 0..100")
    report = asyncio.run(profile(args))
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("state", "meshVersion", "domain", "elapsedSeconds",
                                                 "ownedCpuPercent", "sampledPeakRssBytes")}))
    return 0 if report["state"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
