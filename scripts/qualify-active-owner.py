"""Independent owned Observer service -> native active wire -> IPC/SSH gate.

Actual installed producer classes and pure facades, with synthetic accepted
native input and collect=False. No provider command, normal socket, deployment
configuration or existing service is used. Wheel acceptance must run with
independently installed packages; --development allows an explicit source screen.
"""

import argparse
import asyncio
import importlib.metadata
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import agent_observer
from agent_observer.active_contract import SELECTOR_DIGEST
from agent_observer.contract import store_namespace
from agent_observer.mesh_active_profile import ACTIVE_PROFILE_ID, ActiveAgentProfile
from agent_observer.mesh_active_read import PreparedActiveAgentWatch
from agent_observer.mesh_profile import AgentProfile
from agent_observer.mesh_publisher import make_publisher
from agent_observer.service_runtime import Runtime
from agent_observer.service_state import ServiceState

import mesh_plus
from mesh_plus.api import Bridge, Client, Endpoint, Reader
from mesh_plus.testing.ssh_carrier import ssh_server
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc

ROOT = Path(__file__).resolve().parents[1]


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def state_fixture(empty):
    value = json.loads((ROOT / "tests/fixtures/active-baseline-full-service4.json").read_text())["snapshot"]
    value["sources"] = value["sources"][:1]
    value["sessions"] = value["sessions"][:1]
    value["host"]["uid"] = os.geteuid()
    source = value["sources"][0]
    namespace = store_namespace("codex", source["configHome"], source["configHomeKind"], os.geteuid())
    source["namespace"] = value["sessions"][0]["identity"]["namespace"] = namespace
    source["capabilities"]["runtime"] = ["running", "parked"]
    if empty:
        value["sessions"][0].update(phase=None, blockedReasons=[], inventory="saved", hasSavedHistory=True)
        value["sessions"][0]["runtime"].update(value="parked", reason="native_not_loaded")
    state = ServiceState(host_scope="fixture", configs={"codex": (source["configHome"], source["configHomeKind"])})
    state.native_hostname = value["host"]["nativeHostname"]
    state.attempt("codex", "history")
    require(state.accept("codex", "history", value, sampled_ms=boottime_ms(), ttl_ms=600000,
                         runtime_ttl_ms=600000), "synthetic native acceptance")
    return state


async def exercise(connect, profile, *, remote, empty):
    codec = profile.bind("fixture", "active")
    clients = []
    async def open_client():
        client = await Client.connect(await connect(), host="fixture", source="active",
                                      profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
        clients.append(client)
        return client
    async def revision():
        return "sha256:" + "b" * 64
    reader = Reader("agent", [Endpoint("fixture", not remote, "sha256:" + "a" * 64 if remote else None,
                                       open_client, codec)],
                    local_host="local" if remote else "fixture", profile=profile,
                    catalog_revision=await revision() if remote else None,
                    catalog_check=revision if remote else None)
    snapshots = []
    for _ in range(2):
        value = await reader.snapshot()
        require(value["mesh"]["status"] == "complete", "installed source snapshot unavailable: " + str(value))
        require(len(value["sessions"]) == (0 if empty else 1), "native active member selection")
        host = value["mesh"]["hosts"][0]
        require(bool(host["delivery"]["proof"]) == remote, "proof binding")
        require(host["owner"]["service"]["selectorDigest"] == SELECTOR_DIGEST, "selector binding")
        snapshots.append(value)
    facade = PreparedActiveAgentWatch("c" * 32, profile=profile)
    stream = reader.watch_admitted(request_id="c" * 32, proof_interval=.1)
    try:
        for _ in range(10):
            facade.accept(await asyncio.wait_for(anext(stream), 3))
            result = facade.read(boottime_ms(), snapshots[-1]["mesh"]["reader"]["clock"])
            if result.scopes and result.scopes[0]["coverage"]["status"] == "complete":
                break
        require(len(result.members) == (0 if empty else 1), "installed facade member mismatch")
        require(result.scopes[0]["coverage"]["status"] == "complete", "complete-empty authority missing")
        # Each remote proof has its own conservative RTT translation. Test the
        # current watch generation's exact deadlines, not a prior snapshot's.
        watch_clock = result.context["reader"]["clock"]
        now = max(r["expiresAtMs"] or 0 for r in result.context["hosts"][0]["receipts"])
        expired = facade.read(now, watch_clock)
        require(not expired.members and all(s["coverage"]["status"] != "complete" for s in expired.scopes),
                "native metadata authority survived original translated expiry")
        # Returned bodies/headers are detached; the owned cache never borrows exports.
        result.members.clear()
        facade.disconnect()
        require(facade.read(now, watch_clock).context is None, "disconnect retained authority")
    finally:
        facade.disconnect()
        await stream.aclose()
    require(all(client.channel.closed for client in clients), "client channel leak")
    require(reader.inspect()["activeConnections"] == 0 and reader.inspect()["cleanupFailures"] == 0,
            "reader cleanup failure")
    return {"path": "fixed-ssh" if remote else "ipc", "empty": empty, "snapshots": len(snapshots),
            "watch": True, "originalExpiryChecked": True, "cleanup": True}


async def qualify(args):
    if not args.development:
        require(not Path(mesh_plus.__file__).resolve().is_relative_to(ROOT), "installed Mesh wheel required")
        require("site-packages" in str(Path(agent_observer.__file__).resolve()), "installed Observer wheel required")
    reports = []
    for empty in (False, True):
        state = state_fixture(empty)
        generations = state.active_projector.generations
        with tempfile.TemporaryDirectory(prefix="mesh-active-native-") as directory:
            root = Path(directory)
            read_socket = root / "private/read.sock"
            runtime = Runtime(state, read_socket, collect=False, heartbeat_ms=200, io_timeout_ms=2000)
            stop, errors = threading.Event(), []
            def serve():
                try:
                    runtime.run(stop)
                except BaseException as error:
                    errors.append(repr(error))
            thread = threading.Thread(target=serve, name="owned-agent-service")
            thread.start()
            deadline = time.monotonic() + 3
            while not read_socket.exists() and not errors and time.monotonic() < deadline:
                await asyncio.sleep(.01)
            server = None
            try:
                require(read_socket.exists() and not errors, "owned native service startup: " + str(errors))
                profile = ActiveAgentProfile()
                publisher = make_publisher("fixture", "active", str(read_socket), profile_id=ACTIVE_PROFILE_ID)
                mesh_socket = root / "mesh.sock"
                server = await IPCServer(mesh_socket, Bridge(publisher).serve).start()
                reports.append(await exercise(lambda: connect_ipc(mesh_socket), profile, remote=False, empty=empty))
                # The ordinary three-argument factory still produces unchanged full Agent v3.
                full = make_publisher("fixture", "full", str(read_socket))
                payload = await full.snapshot({})
                require(full.profile == AgentProfile().descriptor.profile_id and
                        payload["ownerFrame"]["serviceProtocol"] == 4 and
                        len(payload["ownerFrame"]["snapshot"]["sessions"]) == 1,
                        "full source fallback/default changed")
                with tempfile.TemporaryDirectory(prefix=".mesh-native-ssh-", dir=Path.home()) as ssh_directory:
                    command = [sys.executable, "-B", str(ROOT / "tests/active_publisher_cli.py"),
                               "--owner-socket", str(read_socket)]
                    if args.development:
                        # sshd deliberately does not inherit the caller's source
                        # import path. Only an explicit development screen adds
                        # these known local checkouts to the forced fixture argv.
                        roots = [str(Path(module.__file__).resolve().parent.parent)
                                 for module in (agent_observer, mesh_plus)]
                        command = ["/usr/bin/env", "PYTHONPATH=" + os.pathsep.join(roots), *command]
                    async with ssh_server(Path(ssh_directory), command, "active") as connector:
                        reports.append(await exercise(connector, profile, remote=True, empty=empty))
                require(state.active_projector.generations == generations, "reads/proofs reprojected native generation")
                require(runtime.counts["workerStarts"] == 0, "unexpected provider worker")
            finally:
                if server is not None:
                    await server.close()
                stop.set()
                thread.join(4)
                require(not thread.is_alive() and not errors, "owned native service cleanup: " + str(errors))
                require(not read_socket.exists(), "owned native socket retained")
    return {"status": "passed", "reports": reports, "providerWorkerStarts": 0,
            "projectionCacheReused": True, "fullDefaultPreserved": True,
            "versions": {name: importlib.metadata.version(name) for name in ("mesh-plus", "agent-observer")},
            "modules": {"mesh": str(Path(mesh_plus.__file__).resolve()),
                        "observer": str(Path(agent_observer.__file__).resolve())},
            "development": args.development,
            "limits": ["Synthetic accepted native input in owned collect=False service, not real provider census",
                       "Local machine and disposable localhost SSH; no operational fleet/device selection"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(qualify(args))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
