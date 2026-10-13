"""Owned actual Tmux factory/IPC fleet admission and source-loss acceptance."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from tmux_observer.mesh_profile import TmuxMeshProfile
from tmux_observer.mesh_publisher import make_publisher

from mesh_plus.api import Bridge, Client, Endpoint, Reader, ReadGuard, current_sessions
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc


async def main():
    with tempfile.TemporaryDirectory(prefix="mesh-simplification-native-") as directory:
        root = Path(directory)
        env = {**os.environ, "TMUX_TMPDIR": str(root)}
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        owner = server = None
        watch = None

        async def command(*args):
            child = await asyncio.create_subprocess_exec("tmux", "-f", "/dev/null", "-L", "default", *args,
                env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(child.wait(), 3)
            return child.returncode

        async def retire():
            if owner is not None and owner.returncode is None:
                owner.terminate()
                await asyncio.wait_for(owner.wait(), 3)

        try:
            assert await command("new-session", "-d", "-s", "simplification-owned", "sleep 120") == 0
            owner = await asyncio.create_subprocess_exec(sys.executable, "-I", "-B", "-m", "tmux_observer", "owner",
                "--host-id", "beta", "--socket", str(root / "owner.sock"), env=env,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            publisher = make_publisher("beta", "default", root / "owner.sock")
            async with asyncio.timeout(8):
                while True:
                    try:
                        value = await publisher.snapshot({})
                        if value["ownerFrame"]["snapshot"] is not None:
                            break
                    except OSError:
                        pass
                    await asyncio.sleep(.025)
            server = await IPCServer(root / "mesh.sock", Bridge(publisher).serve).start()
            async def connect():
                return await Client.connect(await connect_ipc(root / "mesh.sock"), host="beta", source="default",
                    profile=publisher.profile, codec=publisher.validate)
            profile = TmuxMeshProfile()
            revision = "sha256:" + "a" * 64
            async def catalog():
                return revision
            # Remote proof binding is exercised over private IPC, not claimed as
            # an ordinary network path or production remote route selection.
            reader = Reader("tmux", [Endpoint("beta", False, revision, connect, profile.bind("beta", "default"))],
                local_host="alpha", catalog_revision=revision, catalog_check=catalog, profile=profile)
            response = await reader.snapshot()
            assert [r["name"] for r in current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"], profile=profile)] == ["simplification-owned"]
            guard = ReadGuard("tmux", "a" * 32, profile=profile)
            watch = reader.watch(request_id="a" * 32)
            async with asyncio.timeout(5):
                while True:
                    frame = await anext(watch)
                    guard.accept(frame)
                    if guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]):
                        break
            assert await command("rename-session", "-t", "simplification-owned", "simplification-changed") == 0
            async with asyncio.timeout(8):
                while True:
                    frame = await anext(watch)
                    guard.accept(frame)
                    rows = guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"])
                    if rows and rows[0]["name"] == "simplification-changed":
                        break
            await watch.aclose()
            watch = None
            guard.disconnect()
            assert not guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"])
            await retire()
            failed = await reader.snapshot()
            assert failed["mesh"]["status"] == "unavailable"
            assert not current_sessions(failed, boottime_ms(), failed["mesh"]["reader"]["clock"], profile=profile)
            assert reader.inspect()["activeConnections"] == 0
            print("actual owned Tmux factory: snapshot, proof, push, rename, source loss and disconnect passed")
        finally:
            if watch is not None:
                await watch.aclose()
            if server is not None:
                await server.close()
            await retire()
            await command("kill-server")


if __name__ == "__main__":
    asyncio.run(main())
