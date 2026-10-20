"""Explicit disposable Observer working-set IPC/stdio composition (no provider).

Requires a supplied owning source checkout with its synthetic Runtime fixture.
This is not installed/native fleet, performance, RSS or deployment acceptance.
"""

import argparse
import asyncio
import copy
import gc
import hashlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from mesh_plus.api import Endpoint, Reader, reconstructed, validate_response
from mesh_plus.evidence import digest
from mesh_plus.transport import IPCServer, connect_ipc, subprocess_channel
from mesh_plus.view_feed import ViewFeedBridge, ViewFeedClient


async def scenario(observer, mode, count):
    fixtures = importlib.import_module("test_working_set_registered_sdk")
    profile_module = importlib.import_module("agent_observer.mesh_working_set_profile")
    publisher_module = importlib.import_module("agent_observer.mesh_working_set_publisher")
    window = 60_000
    state, sample = fixtures.state_with_rows(window=window, count=count)
    profile = profile_module.WorkingSetAgentProfile(window)
    with fixtures.Running(state=state, collect=False) as native, tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        publisher = publisher_module.make_working_set_publisher("fixture", "working", native.path,
                                                                window_ms=window)
        expected = await publisher.native.snapshot()
        expected_rows = expected["projection"]["sessions"]
        server = None
        path = root / "mesh.sock"
        if mode == "ipc":
            server = await IPCServer(path, ViewFeedBridge(publisher, profile=profile).serve).start()
        else:
            config = root / "sources.toml"
            config.write_text(f'version=1\nhost="fixture"\n[sources.working]\ndomain="agent"\nsocket={json.dumps(str(native.path))}\n')
            config.chmod(0o600)
            launcher = root / "launcher.py"
            launcher.write_text(
                f"import sys;sys.path.insert(0,{str(observer)!r})\n"
                "from agent_observer.mesh_working_set_publisher import make_working_set_publisher\n"
                "from mesh_plus.cli import main\n"
                "def factory(host,source,socket):\n"
                f" return make_working_set_publisher(host,source,socket,window_ms={window})\n"
                "raise SystemExit(main(publisher_factories={'agent':factory}))\n")

        clients = []

        async def connect():
            channel = (await connect_ipc(path) if mode == "ipc" else
                       await subprocess_channel([sys.executable, "-I", str(launcher), "view-feed-bridge",
                                                 "--source", "working", "--stdio", "--config", str(config)]))
            client = await ViewFeedClient.connect(channel, host="fixture", source="working", profile=profile)
            clients.append(client)
            return client

        # Exercise actual replacement -> changed published view, independently
        # of Reader's full snapshot/proof floor. No private source state edits.
        change_client = await connect()
        changes = change_client.changes()

        async def next_change():
            from mesh_plus.view_feed import ViewFeedChange
            for _ in range(20):
                event = await asyncio.wait_for(anext(changes), 5)
                if isinstance(event, ViewFeedChange):
                    return event
            raise AssertionError("change_event_missing")

        try:
            first = await next_change()
            assert first.kind == "replacement"
            first_revision = first.revision
            first.close()
            if count:
                sample["sessions"][0]["runtime"]["value"] = "parked"
                sample["sessions"][0]["phase"] = None
                sample["sessions"][0]["blockedReasons"] = []
                state.attempt("codex", "runtime")
                assert state.accept("codex", "runtime", sample, sampled_ms=state.clock(),
                                    ttl_ms=120_000, accepted_boottime_ms=state.clock()) is True
                changed = await next_change()
                assert changed.revision > first_revision
                codec_for_change = profile.bind("fixture", "working")
                codec_for_change.inspect_native(copy.deepcopy(changed.candidate["ownerFrame"]))
                expected = await publisher.native.snapshot()
                expected_rows = expected["projection"]["sessions"]
                assert changed.candidate["ownerFrame"]["projection"]["sessions"] == expected_rows
                changed.close()
        finally:
            await changes.aclose()
            await change_client.close()

        revision = "sha256:" + "d" * 64

        async def catalog():
            return revision

        codec = profile.bind("fixture", "working")
        reader = Reader("agent", [Endpoint("fixture", False, revision, connect, codec)],
                        local_host="reader", profile=profile, catalog_revision=revision, catalog_check=catalog)
        stream = reader.watch_admitted(request_id="f" * 32, proof_interval=.1)
        facade = fixtures.PreparedWorkingSetAgentWatch("f" * 32, profile=profile, window_ms=window)
        nonces = set()
        try:
            for _ in range(60):
                facade.accept(await asyncio.wait_for(anext(stream), 5))
                response = facade.snapshot()
                if response is None:
                    continue
                host = response["mesh"]["hosts"][0]
                if host["delivery"]["status"] != "ready":
                    continue
                validate_response(response, profile=profile)
                restored = reconstructed(response, host, profile=profile)
                codec.inspect_native(restored)
                assert restored["projection"]["sessions"] == expected_rows
                current = facade.read(fixtures.reader_now(), fixtures.reader_clock())
                assert current.members == expected_rows
                assert current.context is not None
                proof = host["delivery"]["proof"]
                assert proof is not None
                nonces.add(proof["nonce"])
                if len(nonces) >= 2:
                    break
            else:
                raise AssertionError("two_fresh_native_proofs_not_reached")
            result = {"mode": mode, "sourceRows": count, "selectedRows": len(expected_rows),
                      "freshNonces": len(nonces), "nativeDigest": digest(restored),
                      "metrics": clients[-1].inspect()}
        finally:
            facade.disconnect()
            await stream.aclose()
            if server is not None:
                await server.close()
        assert reader.inspect()["activeConnections"] == 0
        for client in clients:
            assert client.closed
            # A retained caller result can still own admitted data credit;
            # these metrics deliberately report that, rather than refunding it.
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    observer = args.observer.resolve()
    sys.path[:0] = [str(observer), str(observer / "tests")]
    gc.disable()

    async def run():
        return [await scenario(observer, mode, count) for mode in ("ipc", "stdio") for count in (0, 3, 12)]

    results = asyncio.run(run())
    roots = [Path(__file__).resolve().parents[1], observer]
    loaded = {}
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file():
            path = Path(path).resolve()
            if any(path.is_relative_to(root) for root in roots) and path.suffix == ".py":
                loaded[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"python": sys.version, "gcEnabled": gc.isenabled(), "scenarios": results,
              "loadedInputs": loaded, "observer": str(observer), "uid": os.geteuid(),
              "scope": "synthetic accepted input, collect=False actual Runtime IPC, owned Mesh IPC/stdio, ordinary Reader+domain facade; separate ledgers; no provider/native fleet/installed/CPU/RSS acceptance"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"python": sys.version.split()[0], "scenarios": len(results),
                      "loadedInputs": len(loaded), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
