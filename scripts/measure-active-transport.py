"""Exact-work full/active owned IPC watch with actual pure Observer facades.

Fixture creation/projection is outside transport timing. Collector, service and
real provider costs remain independent owner gates. No normal endpoint is read.
Run serial ABBA in separate installed-wheel processes; --memory is a separate,
instrumented allocation run whose CPU must not be used for timing acceptance.
"""

import argparse
import asyncio
import copy
import hashlib
import importlib.metadata
import json
import resource
import sys
import tempfile
import time
import tracemalloc
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from active_fixture import ActiveSource  # noqa: E402

from mesh_plus.api import Bridge, CachedPublisher, Client, Endpoint, Reader  # noqa: E402
from mesh_plus.evidence import clock_domain  # noqa: E402
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc  # noqa: E402


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def fixtures(args):
    base = json.loads((ROOT / "tests/fixtures/active-baseline-full-service4.json").read_text())
    active_source = ActiveSource()
    active = active_source.frame
    base["sources"] = copy.deepcopy(active["sources"])
    base["snapshot"]["sources"] = base["snapshot"]["sources"][:1]
    # Synthetic original receipts have a declared two-minute horizon. This is
    # fixture evidence; status/proof/watch never renew it during measurement.
    now = boottime_ms()
    for value in (base, active):
        value.update(bootId=active["bootId"], clockDomain=active["clockDomain"], emittedBoottimeMs=now)
        for component in value["sources"][0]["components"]:
            component.update(sampledBoottimeMs=now - 1000, expiresBoottimeMs=now + 120000)
    base["snapshot"]["sources"][0]["runtime"]["bootId"] = active["bootId"]
    template = copy.deepcopy(base["snapshot"]["sessions"][0])
    rows = []
    for index in range(args.active + args.dormant):
        row = copy.deepcopy(template)
        identity = str(uuid.UUID(int=index + 1000))
        row["identity"]["nativeId"] = identity
        row["nativeIds"].update(threadId=identity, sessionTreeRootId=identity)
        row["title"] = "Synthetic selected" if index < args.active else "Synthetic parked " + str(index)
        if index >= args.active:
            row.update(phase=None, blockedReasons=[], inventory="saved", hasSavedHistory=True)
            row["runtime"].update(value="parked", reason="native_not_loaded")
        rows.append(row)
    base["snapshot"]["sources"][0]["capabilities"]["runtime"] = ["running", "parked"]
    base["snapshot"]["sessions"] = rows
    active["projection"]["sessions"] = copy.deepcopy(rows[:args.active])
    scope = active["projection"]["scopes"][0]
    supports = []
    for component in active["sources"][0]["components"]:
        supports.append({"serviceId": active["serviceId"], "provider": "codex", "namespace": scope["namespace"],
                         "contextGeneration": scope["contextGeneration"], "component": component["name"],
                         **{key: component[key] for key in
                            ("accepted", "sampledBoottimeMs", "expiresBoottimeMs")}})
    runtime = next(support for support in supports if support["component"] == "runtime")
    fields = copy.deepcopy(scope["members"][0]["fieldSupports"])
    fields.update(runtime=runtime, phase=runtime, kind=runtime, savedIdentity=runtime)
    scope["coverage"]["supports"] = supports
    scope["members"] = [{"identity": copy.deepcopy(row["identity"]), "fieldSupports": copy.deepcopy(fields)}
                        for row in active["projection"]["sessions"]]
    return base, active


async def measure(args):
    from agent_observer.active_contract import validate_frame as validate_active
    from agent_observer.mesh_active_profile import ActiveAgentProfile
    from agent_observer.mesh_active_read import PreparedActiveAgentWatch
    from agent_observer.mesh_profile import AgentProfile
    from agent_observer.mesh_read import PreparedAgentWatch
    from agent_observer.mesh_selection import AgentSelection
    from agent_observer.service_contract import validate_frame as validate_full

    full, active = fixtures(args)
    validate_full(full, expected_host="fixture")
    validate_active(active, expected_host="fixture")
    active_bytes = len(json.dumps(active, separators=(",", ":")).encode())
    full_bytes = len(json.dumps(full, separators=(",", ":")).encode())
    require(full_bytes < 8404992, "full fixture outside per-host frame capacity")
    selected_ids = [row["identity"]["nativeId"] for row in active["projection"]["sessions"]]
    source = ActiveSource()
    source.frame = full if args.mode == "full" else active
    profile = AgentProfile() if args.mode == "full" else ActiveAgentProfile()
    publisher = CachedPublisher("agent", "fixture", "active", source, profile=profile)
    if args.mode == "full":
        facade = PreparedAgentWatch("a" * 32, profile=profile, selection=AgentSelection(
            frozenset({"codex"}), frozenset({"user", "unknown"}),
            frozenset({"running"}), frozenset({"current"})))
    else:
        facade = PreparedActiveAgentWatch("a" * 32, profile=profile)
    clients = []
    clock = clock_domain()
    with tempfile.TemporaryDirectory(prefix="mesh-active-cost-") as directory:
        path = Path(directory) / "mesh.sock"
        server = await IPCServer(path, Bridge(publisher).serve).start()
        codec = profile.bind("fixture", "active")
        async def connect():
            client = await Client.connect(await connect_ipc(path), host="fixture", source="active",
                                          profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
            clients.append(client)
            return client
        reader = Reader("agent", [Endpoint("fixture", True, None, connect, codec)], local_host="fixture", profile=profile)
        stream = reader.watch_admitted(request_id="a" * 32, proof_interval=60)

        async def until_title(title):
            async with asyncio.timeout(15):
                async for frame in stream:
                    facade.accept(frame)
                    result = facade.read(boottime_ms(), clock)
                    if len(result.sessions) == args.active and result.sessions[0]["title"] == title:
                        return result
            raise AssertionError("watch ended before replacement")

        signatures, latencies = [], []
        selected_count = summary_count = 0
        try:
            await until_title("Synthetic selected")
            # Let the initial pushed baseline settle before the timed updates.
            await asyncio.sleep(.02)
            before_wire = clients[0].inspect()["channel"]["receivedBytes"]
            before_reads = source.reads
            if args.memory:
                tracemalloc.start()
            cpu, started = time.process_time(), time.perf_counter()
            for generation in range(args.generations):
                before = time.perf_counter()
                body = source.frame["snapshot" if args.mode == "full" else "projection"]
                body["sessions"][0]["title"] = "Generation " + str(generation)
                source.frame["viewRevision"] += 1
                source.frame["sequence"] += 1
                await source.changes.put(None)
                result = await until_title(body["sessions"][0]["title"])
                for _ in range(args.reads):
                    result = facade.read(boottime_ms(), clock)
                    require([row["identity"]["nativeId"] for row in result.sessions] == selected_ids,
                            "selected membership mismatch")
                    if args.mode == "full":
                        require(len(result.summaries) == args.active + args.dormant, "full summary coverage mismatch")
                        summary_count += len(result.summaries)
                    else:
                        require(len(result.scopes) == 1 and result.scopes[0]["coverage"]["status"] == "complete",
                                "projected completeness mismatch")
                    selected_count += len(result.sessions)
                    signatures.append(hashlib.sha256(json.dumps(result.sessions, sort_keys=True).encode()).hexdigest())
                latencies.append((time.perf_counter() - before) * 1000)
            timing = {"cpuMs": (time.process_time() - cpu) * 1000, "wallMs": (time.perf_counter() - started) * 1000}
            peak = tracemalloc.get_traced_memory()[1] if args.memory else None
            if args.memory:
                tracemalloc.stop()
                timing = {"cpuMs": None, "wallMs": None}
            wire = clients[0].inspect()["channel"]["receivedBytes"] - before_wire
            reads = source.reads - before_reads
        finally:
            facade.disconnect()
            await stream.aclose()
            await server.close()
        require(reader.inspect()["activeConnections"] == 0 and source.watchers == 0, "owned cleanup failed")
    return {"status": "passed", "mode": args.mode, "active": args.active, "dormant": args.dormant,
            "generations": args.generations, "readsPerGeneration": args.reads, **timing,
            "wireReceivedBytes": wire, "nativeCachedReads": reads, "selectedBodiesRead": selected_count,
            "fullSummariesRead": summary_count, "fullNativeBytes": full_bytes, "projectedNativeBytes": active_bytes,
            "maxReplacementLatencyMs": max(latencies), "postSetupPeakAllocatedBytes": peak,
            "workerPeakRssKiBIncludingSetup": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "semanticSignature": hashlib.sha256(json.dumps(signatures).encode()).hexdigest(), "cleanup": True,
            "versions": {name: importlib.metadata.version(name) for name in ("mesh-plus", "agent-observer")},
            "limits": ["Owned synthetic local IPC watch; total publisher+Reader+facade CPU, not RLCD/live percent",
                       "Full fixture, projection/collection and service hosting costs outside timed section",
                       "Synthetic original two-minute leases never renew during read/proof/watch",
                       "Separate --memory run is instrumented; CPU/wall timing intentionally omitted",
                       "Peak RSS includes setup/full-fixture creation; post-setup allocations are a separate measure"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "active"), required=True)
    parser.add_argument("--dormant", type=int, choices=(100, 500, 2000), required=True)
    parser.add_argument("--active", type=int, default=5)
    parser.add_argument("--generations", type=int, default=6)
    parser.add_argument("--reads", type=int, default=3)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(1 <= args.active <= 32 and 1 <= args.generations <= 100 and 1 <= args.reads <= 10, "bounded work")
    result = asyncio.run(measure(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "mode", "dormant", "cpuMs", "wireReceivedBytes",
                                                  "semanticSignature", "cleanup")}))


if __name__ == "__main__":
    main()
