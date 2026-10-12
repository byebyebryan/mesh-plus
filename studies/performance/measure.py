"""Private, installed-owner carrier trials; no collection, selection writes or wire extensions."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import installed, private_write, profile  # noqa: E402

ROOT = Path("/tmp/mesh-perf-20261012")
HZ = os.sysconf("SC_CLK_TCK")


def stop_listener(case):
    if len(case) != 32 or any(c not in "0123456789abcdef" for c in case):
        raise ValueError("case_identity")
    ready = ROOT / "cases" / case / "wss.json"
    value = json.loads(ready.read_text())
    current = process(value["pid"], value["birth"], memory=False)
    if current.get("error") == "retired":
        return
    if "error" in current:
        raise ValueError("listener_incarnation_changed")
    command = Path(f"/proc/{value['pid']}/cmdline").read_bytes().split(b"\x00")
    if str(ready).encode() not in command or str(ROOT / "host.py").encode() not in command or b"serve" not in command:
        raise ValueError("listener_ownership")
    os.kill(value["pid"], signal.SIGTERM)


def process(pid, birth=None, *, memory=True):
    node = Path("/proc") / str(pid)
    try:
        fields = node.joinpath("stat").read_text().rsplit(")", 1)[1].split()
        if birth is not None and str(birth) != fields[19]:
            return {"pid": pid, "error": "incarnation_changed"}
        result = {"pid": pid, "birth": fields[19], "parent": int(fields[1]),
                  "ticks": int(fields[11]) + int(fields[12]), "rssKiB": int(fields[21]) * os.sysconf("SC_PAGE_SIZE") / 1024}
        if memory:
            try:
                values = node.joinpath("smaps_rollup").read_text().splitlines()
                result["pssKiB"] = int(next(line.split()[1] for line in values if line.startswith("Pss:")))
                result["fds"] = len(list(node.joinpath("fd").iterdir()))
            except (PermissionError, FileNotFoundError):
                result["pssKiB"] = result["fds"] = None
        return result
    except (FileNotFoundError, ProcessLookupError):
        return {"pid": pid, "error": "retired"}


def sample_server():
    # Dedicated sampler: self cost is reported separately; child CPU is never added.
    for raw in sys.stdin:
        request = json.loads(raw)
        if request.get("controls"):
            home = Path.home()
            controls = {}
            for name in (".local/bin/mesh-plus", ".local/bin/agent-observer", ".config/mesh-plus/sources.toml",
                         ".local/share/chezmoi/deployments/tmux-observer.json", ".local/share/chezmoi/deployments/agent-observer.json",
                         ".local/share/chezmoi/deployments/agent-observer-mesh.json",
                         ".config/systemd/user/agent-observer.service", ".config/systemd/user/mesh-plus-agent.service"):
                controls[name] = hashlib.sha256((home / name).read_bytes()).hexdigest()
            units = {}
            for name in (f"tmux-observer-owner@{request['host']}.service", "agent-observer.service", "mesh-plus-agent.service"):
                units[name] = subprocess.check_output(["systemctl", "--user", "show", name,
                    "--property=MainPID,ExecMainStartTimestampMonotonic,ActiveState"], text=True).strip()
            state = json.loads(subprocess.check_output(["tailscale", "status", "--json"], text=True))
            peer = next(value for value in state["Peer"].values() if {"snap": "100.70.82.105", "starship": "100.84.31.64"}[request["peer"]] in value["TailscaleIPs"])
            from types import SimpleNamespace
            _, _, roots = installed(SimpleNamespace(mesh_root=ROOT / "baseline/lib/python3.14/site-packages"))
            runtime = {}
            for root, package in zip(roots[:3], ("mesh_plus", "tmux_observer", "agent_observer")):
                hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((root / package).rglob("*")) if p.suffix in (".py", ".json")}
                runtime[package] = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
            for name in ("measure.py", "host.py", "bin/mesh-plus"):
                runtime[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            print(json.dumps({"controls": controls, "units": units,
                              "runtime": runtime,
                              "path": {"online": peer["Online"], "currentAddress": peer.get("CurAddr"),
                                       "relay": peer.get("Relay"), "kind": "direct" if peer.get("CurAddr") else "relay-or-idle"}}), flush=True)
            continue
        if request.get("discover"):
            case = request["discover"]
            if len(case) != 32 or any(c not in "0123456789abcdef" for c in case):
                raise ValueError("case_identity")
            if request["carrier"] == "ssh":
                files = list((ROOT / "cases" / case).glob("publisher-*.json"))
                if len(files) != 1:
                    raise ValueError("one_owned_publisher_required")
                pub = json.loads(files[0].read_text())
            else:
                pub = json.loads((ROOT / "cases" / case / "wss.json").read_text())
                if "birth" not in pub:
                    # Older first-start receipts: validate its exact live command before binding birth.
                    cmd = Path(f"/proc/{pub['pid']}/cmdline").read_bytes()
                    if b"host.py\x00serve" not in cmd or request["domain"].encode() not in cmd.split(b"\x00"):
                        raise ValueError("listener_ownership")
                    pub["birth"] = process(pub["pid"])["birth"]
            roles = [{"role": "publisher", "pid": pub["pid"], "birth": pub["birth"]}]
            if request["carrier"] == "ssh":
                parent = process(pub["pid"], pub["birth"])["parent"]
                for _ in range(2):
                    cmd = Path(f"/proc/{parent}/cmdline").read_bytes()
                    if b"sshd-session" not in cmd:
                        break
                    ancestor = process(parent)
                    roles.append({"role": "ssh-server-session", "pid": parent, "birth": ancestor["birth"]})
                    parent = ancestor["parent"]
            for unit in (f"tmux-observer-owner@{request['host']}.service", "agent-observer.service"):
                pid = int(subprocess.check_output(["systemctl", "--user", "show", unit, "--property=MainPID", "--value"], text=True))
                native = process(pid)
                roles.append({"role": unit, "pid": pid, "birth": native["birth"]})
            print(json.dumps({"discovered": roles}), flush=True)
            continue
        roles = request["roles"]
        if request.get("tree"):
            root = roles[0]
            children = Path(f"/proc/{root['pid']}/task/{root['pid']}/children")
            try:
                for pid in children.read_text().split():
                    roles.append({"role": "ssh-client", "pid": int(pid)})
            except FileNotFoundError:
                pass
        result = {"time": time.monotonic(), "roles": [{"role": role["role"], **process(role["pid"], role.get("birth"))} for role in roles],
                  "sampler": process(os.getpid(), memory=False), "load": os.getloadavg()}
        cpu = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
        result["systemBusyTicks"] = sum(cpu) - cpu[3] - cpu[4]
        print(json.dumps(result, separators=(",", ":")), flush=True)


def bridge(args):
    from mesh_plus.cli import main
    case = os.environ.get("MESH_PERF_CASE", "")
    if len(case) != 32 or any(c not in "0123456789abcdef" for c in case):
        raise ValueError("private_case_required")
    own = process(os.getpid())
    directory = ROOT / "cases" / case
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_write(directory / f"publisher-{os.getpid()}.json", own)
    def tmux(host, source, socket):
        from tmux_observer.mesh_publisher import make_publisher
        return make_publisher(host, source, socket)

    def agent(host, source, socket):
        from agent_observer.mesh_publisher import make_publisher
        return make_publisher(host, source, socket)

    factories = {"tmux": tmux, "agent": agent}
    # Same fixed SDK command/config and both lazy owner factories as installed selection.
    sys.argv = ["mesh-plus", *args.bridge_arguments]
    raise SystemExit(main(publisher_factories=factories))


async def reader(args):
    from mesh_plus.api import Endpoint, Reader, ReadGuard
    from mesh_plus.catalog import Catalog
    from mesh_plus.evidence import clock_domain
    from mesh_plus.remote import connect_catalog_host
    from mesh_plus.transport import boottime_ms, ssh_argv, subprocess_channel
    from mesh_plus.wss import Selection, configured_reader

    directory = args.material
    p = profile(args.domain)
    source = "tmux_default" if args.domain == "tmux" else "agent"
    selection = None
    if args.carrier == "wss":
        selection = Selection.load(directory / "catalog.json", directory / (args.domain + "-registry.json"),
                                   directory / "ca.pem", directory / (args.domain + "-client.pem"), directory / (args.domain + "-client.key"))
        owner = await configured_reader(args.domain, selection=selection, source=source, socket=Path("/unused"),
                                        scope="hosts", hosts=[args.peer], profile=p)
    else:
        catalog = Catalog(json.loads((directory / "catalog.json").read_text()))
        host = catalog.select("hosts", [args.peer])[0]
        codec = p.bind(args.peer, source)

        async def connector(destination, source, **kwargs):
            nonce = secrets.token_hex(16)
            argv = ssh_argv(destination, source, nonce=nonce, **kwargs)
            argv[-1] = "env " + shlex.join([f"PATH={ROOT}/bin:/usr/bin", f"MESH_PERF_CASE={args.case}"]) + " " + argv[-1]
            return await subprocess_channel(argv, reached_nonce=nonce)

        async def connect():
            return await connect_catalog_host(catalog, host, args.domain, source, connector=connector, profile=p, codec=codec)

        async def check():
            # Captured catalog is fixed for the trial; detecting file edits still revokes it.
            current = Catalog(json.loads((directory / "catalog.json").read_text()))
            if current.revision != catalog.revision:
                raise ValueError("catalog_changed")
            return current.revision

        owner = Reader(args.domain, [Endpoint(args.peer, False, catalog.route_token(args.peer, host["routes"][0]), connect, codec)],
                       local_host=args.host, catalog_revision=catalog.revision, catalog_check=check, profile=p)
    frames, inventories, first, failures = 0, {}, asyncio.Event(), []
    request_id = secrets.token_hex(16)
    guard = ReadGuard(args.domain, request_id, host_ids=[args.peer], profile=p)
    start = time.monotonic()
    stream = None

    async def consume():
        nonlocal frames, stream
        stream = owner.watch(request_id=request_id)
        async for frame in stream:
            guard.accept(frame)
            if "mesh" not in frame:
                failures.append("terminal")
                first.set()
                return
            frames += 1
            if frame["mesh"]["status"] == "complete":
                rows = guard.current(boottime_ms(), clock_domain())
                identities = sorted(repr(p.record_identity(row)) for row in rows)
                key = hashlib.sha256(json.dumps(identities).encode()).hexdigest()
                inventories[key] = {"rows": len(rows), "frames": inventories.get(key, {}).get("frames", 0) + 1}
                if not first.is_set():
                    print(json.dumps({"ready": process(os.getpid()), "coldMs": (time.monotonic() - start) * 1000}), flush=True)
                    first.set()
            elif first.is_set():
                failures.append("incomplete")

    task = asyncio.create_task(consume())
    try:
        async with asyncio.timeout(25):
            await first.wait()
        if failures:
            raise ValueError("no_healthy_baseline")
        # Coordinator owns warmup/measurement timing and samples before requesting retirement.
        while True:
            command = (await asyncio.to_thread(sys.stdin.readline)).strip()
            if command == "stop":
                break
            if command != "mark":
                raise ValueError("coordinator_disconnected")
            print(json.dumps({"mark": owner.inspect(), "inventories": inventories.copy(), "frames": frames}), flush=True)
    finally:
        if task.done() and not task.cancelled():
            failure = task.exception()
            if failure is not None:
                failures.append("consumer_" + type(failure).__name__)
            elif not failures:
                failures.append("watch_ended")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if stream is not None:
            await stream.aclose()
        guard.disconnect()
        if selection:
            selection.close()
    result = {"host": args.host, "peer": args.peer, "domain": args.domain, "carrier": args.carrier,
              "frames": frames, "inventories": inventories, "failures": failures, "metrics": owner.inspect(),
              "proofInterval": 3 if args.domain == "tmux" else 10}
    if result["metrics"]["activeConnections"] or result["metrics"]["cleanupFailures"]:
        raise ValueError("reader_cleanup")
    print(json.dumps({"result": result}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sample", "reader", "bridge", "stop-listener"))
    parser.add_argument("--host", choices=("snap", "starship"))
    parser.add_argument("--peer", choices=("snap", "starship"))
    parser.add_argument("--domain", choices=("tmux", "agent"))
    parser.add_argument("--carrier", choices=("ssh", "wss"))
    parser.add_argument("--case")
    parser.add_argument("--material", type=Path)
    parser.add_argument("--mesh-root", type=Path)
    parser.add_argument("--agent-root", type=Path)
    args, args.bridge_arguments = parser.parse_known_args()
    if args.bridge_arguments and args.bridge_arguments[0] == "--":
        args.bridge_arguments.pop(0)
    if args.command != "bridge" and args.bridge_arguments:
        parser.error("unexpected arguments")
    if args.command == "sample":
        sample_server()
    elif args.command == "stop-listener":
        stop_listener(args.case)
        print(json.dumps({"stopRequested": True}))
    else:
        installed(args)
        if args.command == "bridge":
            bridge(args)
        else:
            asyncio.run(reader(args))


if __name__ == "__main__":
    main()
