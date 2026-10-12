"""Explicit installed-owner performance harness; no native collection or deployment selection."""

import argparse
import asyncio
import cProfile
import hashlib
import importlib.metadata
import json
import os
import pstats
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.resolve() != path.parent or path.parent.stat().st_mode & 0o077:
        raise ValueError("private_parent_required")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")


def installed(args):
    home = Path.home()
    tmux = json.loads((home / ".local/share/chezmoi/deployments/tmux-observer.json").read_text())
    agent = json.loads((home / ".local/share/chezmoi/deployments/agent-observer.json").read_text())
    shared = tmux["sharedMesh"]
    roots = [home / shared["readerSdk"]["prefix"], home / tmux["core"]["prefix"],
             home / agent["readerPrefix"] / "lib/python3.14/site-packages"]
    roots.extend(home / p["prefix"] for p in shared["packages"] if p["name"] not in ("mesh-plus", "tmux-reader-sdk"))
    if getattr(args, "mesh_root", None):
        roots[0] = args.mesh_root
    if getattr(args, "agent_root", None):
        roots[2] = args.agent_root
    sys.path[:0] = [str(path) for path in roots]
    return tmux, agent, roots


def profile(domain):
    if domain == "tmux":
        from tmux_observer.mesh_profile import TmuxMeshProfile
        return TmuxMeshProfile()
    from agent_observer.mesh_profile import AgentProfile
    return AgentProfile()


def publisher(domain, host):
    runtime = Path("/run/user") / str(os.getuid())
    if domain == "tmux":
        from tmux_observer.mesh_publisher import make_publisher
        return make_publisher(host, "tmux_default", runtime / "tmux-observer/owner.sock")
    from agent_observer.mesh_publisher import make_publisher
    return make_publisher(host, "agent", runtime / "agent-observer/read.sock")


def run(argv):
    child = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    return child.stdout.strip() if child.returncode == 0 else {"error": "query_failed", "status": child.returncode}


def inventory(args, tmux, agent, roots):
    import agent_observer
    import tmux_observer

    import mesh_plus

    home = Path.home()
    units = {}
    for unit in (f"tmux-observer-owner@{args.host}.service", "agent-observer.service", "mesh-plus-agent.service"):
        value = run(["systemctl", "--user", "show", unit, "--property=ActiveState,MainPID,ExecMainStartTimestampMonotonic"])
        units[unit] = value
    controls = {}
    for relative in (".local/bin/mesh-plus", ".local/bin/agent-observer", ".config/systemd/user/agent-observer.service",
                     ".config/systemd/user/mesh-plus-agent.service", ".config/mesh-plus/sources.toml",
                     ".local/share/chezmoi/deployments/tmux-observer.json", ".local/share/chezmoi/deployments/agent-observer.json",
                     ".local/share/chezmoi/deployments/agent-observer-mesh.json"):
        path = home / relative
        if path.is_file():
            controls[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    runtime = {}
    for root, package in ((roots[0], "mesh_plus"), (roots[1], "tmux_observer"), (roots[2], "agent_observer")):
        runtime[package] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((root / package).rglob("*")) if p.suffix in (".py", ".json")}
    versions = {name: importlib.metadata.version(name) for name in
                ("mesh-plus", "tmux-observer", "agent-observer", "jsonschema", "attrs", "referencing", "rpds-py")}
    result = {"host": args.host, "hostname": socket.gethostname(), "python": sys.version.split()[0],
              "versions": versions, "collectorVersion": agent["version"], "units": units,
              "controls": controls, "runtime": runtime,
              "actualVersions": {"mesh": mesh_plus.__version__, "tmux": tmux_observer.__version__, "agent": agent_observer.__version__},
              "scope": "installed metadata/control inventory; no provider or source acquisition"}
    private_write(args.output, result)
    print(json.dumps({"host": args.host, "status": "captured", "versions": result["actualVersions"], "collector": agent["version"]}))


async def capture(args):
    pub = publisher(args.domain, args.host)
    frame = await pub.native.snapshot()
    state = pub.codec.inspect_native(frame)
    private_write(args.output, frame)
    raw = Path(args.output).read_bytes()
    print(json.dumps({"host": args.host, "domain": args.domain, "rows": len(state.records),
                      "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "acquisition": "owned cached native source"}))


async def fleet(args):
    from mesh_plus.api import Bridge, ReadGuard, configured_reader
    from mesh_plus.evidence import clock_domain
    from mesh_plus.library_authority import LibraryMeshAuthority
    from mesh_plus.transport import IPCServer, boottime_ms

    reports = {}
    for domain in ("tmux", "agent"):
        pub, p = publisher(domain, args.host), profile(domain)
        authority = LibraryMeshAuthority()
        stream = None
        with tempfile.TemporaryDirectory(prefix="mesh-perf-baseline-") as name:
            endpoint = Path(name) / "read.sock"
            server = await IPCServer(endpoint, Bridge(pub).serve, max_clients=2).start()
            try:
                reader = await configured_reader(domain, source=pub.source, socket=endpoint,
                                                 scope="fleet", authority=authority, profile=p, report_routes=False)
                snap = await reader.snapshot(timeout_ms=15000)
                if snap["mesh"]["status"] != "complete":
                    raise ValueError("baseline_snapshot_incomplete")
                guard = ReadGuard(domain, "b" * 32, profile=p)
                stream = reader.watch(request_id="b" * 32)
                async with asyncio.timeout(20):
                    async for frame in stream:
                        guard.accept(frame)
                        if frame.get("mesh", {}).get("status") == "complete":
                            break
                    else:
                        raise ValueError("baseline_watch_ended")
                rows = guard.current(boottime_ms(), clock_domain())
                reports[domain] = {"snapshot": "complete", "watch": "complete", "rows": len(rows),
                    "hosts": [{"host": h["hostId"], "path": h["delivery"]["path"],
                               "ready": h["delivery"]["status"] == "ready",
                               "proof": h["delivery"]["proof"] is not None} for h in frame["mesh"]["hosts"]]}
                guard.disconnect()
            finally:
                if stream is not None:
                    await stream.aclose()
                await server.close()
                authority.close()
            metrics = reader.inspect()
            if metrics["activeConnections"] or metrics["cleanupFailures"]:
                raise ValueError("baseline_cleanup_failed")
            reports[domain]["cleanup"] = True
    report = {"host": args.host, "status": "passed", "domains": reports,
              "scope": "one complete cached poll/watch sample; no collection/actions/route writes/native oracle"}
    private_write(args.output, report)
    print(json.dumps(report))


async def serve(args):
    from mesh_plus.api import Bridge
    from mesh_plus.wss import Listener, ServerConfiguration
    pub = publisher(args.domain, args.host)
    directory = args.material
    configuration = ServerConfiguration.load(directory / "ca.pem", directory / "server.pem",
                                               directory / "server.key", directory / (args.domain + "-authorization.json"))
    listener = None
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for selected in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(selected, stopped.set)
    try:
        listener = await Listener(configuration.context, Bridge(pub).serve, configuration.authorize,
                                  (pub.host, pub.source, pub.profile)).start(args.port, address=args.address)
        ready = {"status": "ready", "host": args.host, "domain": args.domain, "pid": os.getpid(),
                 "port": listener.port, "source": pub.source, "profile": pub.profile}
        private_write(args.output, ready)
        print(json.dumps(ready), flush=True)
        await stopped.wait()
    finally:
        if listener is not None:
            await listener.close()
        configuration.close()
        for selected in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(selected)


async def wss_read(args):
    from mesh_plus.api import ReadGuard
    from mesh_plus.evidence import clock_domain
    from mesh_plus.transport import boottime_ms
    from mesh_plus.wss import Selection, configured_reader
    directory = args.material
    selection = Selection.load(directory / "catalog.json", directory / (args.domain + "-registry.json"),
                               directory / "ca.pem", directory / (args.domain + "-client.pem"),
                               directory / (args.domain + "-client.key"))
    p = profile(args.domain)
    source = "tmux_default" if args.domain == "tmux" else "agent"
    stream = None
    started = time.monotonic()
    try:
        reader = await configured_reader(args.domain, selection=selection, source=source,
                                         socket=Path("/unused"), scope="hosts", hosts=[args.peer], profile=p)
        snapshot = await reader.snapshot()
        if snapshot["mesh"]["status"] != "complete":
            print(json.dumps({"status": snapshot["mesh"]["status"], "errors": [h["delivery"]["error"] for h in snapshot["mesh"]["hosts"]]}), file=sys.stderr)
            raise ValueError("wss_snapshot_incomplete")
        snapshot_ms = (time.monotonic() - started) * 1000
        guard = ReadGuard(args.domain, "d" * 32, host_ids=[args.peer], profile=p)
        stream = reader.watch(request_id="d" * 32)
        async with asyncio.timeout(20):
            async for frame in stream:
                guard.accept(frame)
                if frame.get("mesh", {}).get("status") == "complete":
                    break
            else:
                raise ValueError("wss_watch_ended")
        rows = guard.current(boottime_ms(), clock_domain())
        outcome = frame["mesh"]["hosts"][0]
        if outcome["delivery"]["path"] != "wss" or not outcome["delivery"]["proof"]:
            raise ValueError("wss_binding_or_proof")
        report = {"host": args.host, "peer": args.peer, "domain": args.domain, "status": "passed",
                  "snapshot": "complete", "watch": "complete", "path": "wss", "proof": True,
                  "rows": len(rows), "snapshotMs": snapshot_ms, "scope": "real-host cached owner WSS; not native oracle"}
        guard.disconnect()
    finally:
        if stream is not None:
            await stream.aclose()
        selection.close()
    metrics = reader.inspect()
    if metrics["activeConnections"] or metrics["cleanupFailures"]:
        raise ValueError("wss_cleanup")
    report["cleanup"] = True
    private_write(args.output, report)
    print(json.dumps(report))


async def diagnostic(args):
    from mesh_plus.evidence import clock_domain
    from mesh_plus.transport import boottime_ms

    p = profile(args.domain)
    frame = json.loads(Path(args.frame).read_text())
    # Clock/chronology must remain genuine: diagnostic runs on its capturing host.
    state = p.bind(args.host, "tmux_default" if args.domain == "tmux" else "agent").inspect_native(frame)
    if state.clock != clock_domain():
        raise ValueError("captured_clock_context_changed")
    class Native:
        async def snapshot(self):
            return frame
        async def watch(self):
            raise RuntimeError("diagnostic watch is not selected")
            yield  # structural async-generator surface only
    from mesh_plus.api import CachedPublisher
    pub = CachedPublisher(args.domain, args.host, "tmux_default" if args.domain == "tmux" else "agent", Native(), profile=p)
    # Constructor requires watch capability; this diagnostic never publishes a subscription.
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.samples):
        payload = await pub.proof({"nonce": "a" * 32})
        pub.validate(payload)  # Bridge's compulsory result boundary.
    profiler.disable()
    statistics = pstats.Stats(profiler)
    functions = []
    for (filename, line, function), (primitive, calls, own, cumulative, callers) in statistics.stats.items():
        if "/mesh_plus/" in filename or "/agent_observer/" in filename or "/tmux_observer/" in filename or function in ("deepcopy", "dumps", "encode", "validate", "iter_errors"):
            functions.append({"module": Path(filename).name, "line": line, "function": function,
                              "calls": calls, "selfSeconds": own, "cumulativeSeconds": cumulative})
    functions.sort(key=lambda item: item["cumulativeSeconds"], reverse=True)
    report = {"host": args.host, "domain": args.domain, "samples": args.samples, "rows": len(state.records),
              "nativeBytes": len(Path(args.frame).read_bytes()), "functions": functions,
              "endedBoottimeMs": boottime_ms(), "scope": "instrumented frozen-frame proof plus Bridge validation; not CPU acceptance"}
    private_write(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "functions"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "capture", "diagnostic", "fleet", "serve", "wss-read"))
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--domain", choices=("tmux", "agent"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame", type=Path)
    parser.add_argument("--mesh-root", type=Path)
    parser.add_argument("--agent-root", type=Path)
    parser.add_argument("--material", type=Path)
    parser.add_argument("--address")
    parser.add_argument("--peer", choices=("snap", "starship"))
    parser.add_argument("--port", type=int)
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    if not args.output.is_absolute() or not 1 <= args.samples <= 100:
        parser.error("absolute output and samples 1..100 required")
    tmux, agent, roots = installed(args)
    if args.command == "inventory":
        inventory(args, tmux, agent, roots)
    elif args.command in ("serve", "wss-read"):
        if not args.domain or not args.material or (args.command == "serve" and (not args.address or args.port is None)):
            parser.error("domain/material and listener address/port required")
        asyncio.run(serve(args) if args.command == "serve" else wss_read(args))
    elif args.command == "fleet":
        asyncio.run(fleet(args))
    else:
        if not args.domain or (args.command == "diagnostic" and not args.frame):
            parser.error("domain and diagnostic frame required")
        asyncio.run(capture(args) if args.command == "capture" else diagnostic(args))


if __name__ == "__main__":
    main()
