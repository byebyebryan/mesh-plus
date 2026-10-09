"""Owned local tmux acceptance; never targets the operational default server."""

import asyncio
import os
import shutil
import signal
import sys
import tempfile
import unittest
from pathlib import Path

from mesh_plus.bridge import Bridge
from mesh_plus.client import Client
from mesh_plus.observer import ObserverAdapter
from mesh_plus.transport import IPCServer, connect_ipc


@unittest.skipUnless(shutil.which("tmux"), "owned native acceptance requires tmux")
class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_tmux_passivity_and_collection_cadence(self):
        with tempfile.TemporaryDirectory(prefix="mesh-native-") as directory:
            root = Path(directory)
            env = {**os.environ, "TMUX_TMPDIR": directory}
            env.pop("TMUX", None)
            env.pop("TMUX_PANE", None)

            async def native(*arguments, allow_failure=False):
                process = await asyncio.create_subprocess_exec("tmux", "-f", "/dev/null", "-L", "default", *arguments,
                                                               env=env, stdout=asyncio.subprocess.PIPE,
                                                               stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await asyncio.wait_for(process.communicate(), 3)
                if not allow_failure:
                    self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
                return stdout

            owner = None
            server = None
            clients = []
            try:
                await native("new-session", "-d", "-s", "mesh-owned", "sleep 120")
                fields = "#{session_id}|#{session_created}|#{session_attached}|#{session_windows}"
                before = await native("list-sessions", "-F", fields)
                hooks = await native("show-hooks")
                owner = await asyncio.create_subprocess_exec(sys.executable, "-m", "tmux_observer", "owner",
                                                             "--host-id", "mesh-owned", "--socket", str(root / "owner.sock"),
                                                             env=env, stdout=asyncio.subprocess.DEVNULL,
                                                             stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
                adapter = ObserverAdapter("tmux", "mesh-owned", "default", root / "owner.sock")
                for _ in range(100):
                    if owner.returncode is not None:
                        self.fail("owned Observer exited before readiness")
                    try:
                        initial = await adapter.snapshot({})
                        if initial["ownerFrame"]["receipt"]["state"] == "ready":
                            break
                    except (OSError, ValueError):
                        pass
                    await asyncio.sleep(.025)
                else:
                    self.fail("owned Observer did not become ready")
                self.assertEqual(initial["ownerFrame"]["snapshot"]["sessions"][0]["name"], "mesh-owned")
                server = await IPCServer(root / "mesh.sock", Bridge(adapter).serve).start()
                for _ in range(3):
                    client = await Client.connect(await connect_ipc(root / "mesh.sock"), host="mesh-owned",
                                                  source="default", profile=adapter.profile, codec=adapter.validate)
                    clients.append(client)
                    sub = await client.subscribe()
                    await asyncio.wait_for(anext(sub), 2)
                snapshots = [await client.request() for _ in range(5) for client in clients]
                frame = snapshots[-1]["ownerFrame"]
                scheduled = (frame["encodedAt"] - initial["ownerFrame"]["receipt"]["lastAttemptAt"]) // 2000
                self.assertLessEqual(frame["receipt"]["attempted"] - initial["ownerFrame"]["receipt"]["attempted"], scheduled)
                self.assertEqual(await native("list-sessions", "-F", fields), before)
                self.assertEqual(await native("show-hooks"), hooks)
                self.assertEqual(await native("list-clients", "-F", "#{client_pid}"), b"")
                # Clients hold observation only: native server can disappear while watches remain.
                await native("kill-server")
                for _ in range(120):
                    empty = await clients[0].request()
                    snapshot = empty["ownerFrame"]["snapshot"]
                    if snapshot is not None and snapshot["serverGeneration"] is None:
                        break
                    await asyncio.sleep(.025)
                else:
                    self.fail("owner did not deliver complete-empty native absence")
                self.assertEqual(snapshot["sessions"], [])
                self.assertEqual(await native("list-sessions", allow_failure=True), b"")
            finally:
                for client in clients:
                    await client.close()
                if server:
                    await server.close()
                if owner and owner.returncode is None:
                    os.killpg(owner.pid, signal.SIGTERM)
                    try:
                        await asyncio.wait_for(owner.wait(), 3)
                    except TimeoutError:
                        os.killpg(owner.pid, signal.SIGKILL)
                        await owner.wait()
                await native("kill-server", allow_failure=True)
