import asyncio
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from ssh_fixture import ssh_channel

from mesh_plus.bridge import Bridge
from mesh_plus.client import Client
from mesh_plus.observer import ObserverAdapter, clock_domain
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import IPCServer, connect_ipc, subprocess_channel

ROOT = Path(__file__).resolve().parents[1]


def native_fixture(domain):
    if domain == "tmux":
        frame = json.loads((ROOT / "reference/tmux-observer/contracts/service-v1/fixtures/ready.json").read_text())
        frame["source"]["uid"] = os.getuid()
        frame["snapshot"]["source"]["uid"] = os.getuid()
        frame["clock"] = clock_domain()
        frame["snapshot"]["clock"] = clock_domain()
    else:
        frame = json.loads((ROOT / "contracts/mesh-read-v1/examples/bridge-candidate.json").read_text())["ownerFrame"]
        frame["uid"] = os.getuid()
        frame["snapshot"]["host"]["uid"] = os.getuid()
        frame["bootId"] = clock_domain()["bootId"]
        frame["clockDomain"] = clock_domain()["timeNamespace"].replace("time:", "time:[") + "]"
    return frame


class ObserverTests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_server_sigterm_removes_only_owned_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "sources.toml"
            config.write_text(f'version = 1\nhost = "test-host"\n[sources.default]\ndomain = "tmux"\nsocket = "{root / "absent-owner.sock"}"\n')
            config.chmod(0o600)
            path = root / "mesh.sock"
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "mesh_plus.cli", "serve", "--source", "default",
                "--config", str(config), "--socket", str(path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                for _ in range(200):
                    if path.is_socket() or process.returncode is not None:
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(path.is_socket())
                process.terminate()
                stdout, stderr = await asyncio.wait_for(process.communicate(), 3)
                self.assertEqual(process.returncode, 0, stderr.decode())
                self.assertEqual(stdout, b"")
                self.assertFalse(path.exists())
                self.assertFalse((root / "absent-owner.sock").exists())
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

    async def exercise(self, domain, subprocess=False, ssh=False):
        # OpenSSH StrictModes checks key-path ancestry; a venv can live under /tmp.
        with tempfile.TemporaryDirectory(dir=Path.home() if ssh else None, prefix=".mesh-runtime-test-") as directory:
            root = Path(directory)
            native = native_fixture(domain)
            host = native["source"]["hostId"] if domain == "tmux" else native["hostScope"]
            queues = set()
            operations = []

            async def native_handler(channel):
                request = json.loads(await channel.reader.readuntil(b"\n"))
                operations.append(request["operation"])
                frame = copy.deepcopy(native)
                if domain == "tmux":
                    frame["requestId"] = request["requestId"]
                    frame["sequence"] = 1
                channel.writer.write(json.dumps(frame, separators=(",", ":")).encode() + b"\n")
                await channel.writer.drain()
                if request["operation"] == "watch":
                    queue = asyncio.Queue()
                    queues.add(queue)
                    try:
                        while True:
                            await queue.get()
                            frame["sequence"] += 1
                            frame["viewRevision"] += 1
                            frame["kind"] = "view"
                            channel.writer.write(json.dumps(frame, separators=(",", ":")).encode() + b"\n")
                            await channel.writer.drain()
                    finally:
                        queues.discard(queue)

            owner = await IPCServer(root / "owner.sock", native_handler).start()
            adapter = ObserverAdapter(domain, host, "default", root / "owner.sock")
            mesh = None
            ssh_context = None
            if subprocess or ssh:
                config = root / "sources.toml"
                config.write_text(f'version = 1\nhost = "{host}"\n[sources.default]\ndomain = "{domain}"\nsocket = "{root / "owner.sock"}"\n')
                config.chmod(0o600)
                command = [sys.executable, "-m", "mesh_plus.cli", "bridge", "--source",
                           "default", "--stdio", "--config", str(config)]
                if ssh:
                    ssh_context = ssh_channel(root, command, "default")
                    channel = await ssh_context.__aenter__()
                else:
                    channel = await subprocess_channel(command)
            else:
                mesh = await IPCServer(root / "mesh.sock", Bridge(adapter).serve).start()
                channel = await connect_ipc(root / "mesh.sock")
            client = None
            try:
                client = await Client.connect(channel, host=host, source="default", profile=adapter.profile,
                                              codec=adapter.validate)
                candidate = await client.request()
                self.assertEqual(candidate["ownerFrame"]["snapshot"], native["snapshot"])
                self.assertEqual(candidate["remaining"], [])
                nonce = "a" * 32
                proof = await client.request("proof", {"nonce": nonce})
                self.assertEqual(proof["nonce"], nonce)
                self.assertTrue(proof["remaining"])
                if ssh:
                    self.assertTrue(channel.reached, repr(bytes(channel.stderr_tail)))
                sub = await client.subscribe()
                self.assertEqual((await anext(sub))["payload"]["kind"], "candidate")
                for queue in queues:
                    queue.put_nowait(True)
                pushed = await asyncio.wait_for(anext(sub), 2)
                self.assertEqual(pushed["payload"]["ownerFrame"]["viewRevision"], native["viewRevision"] + 1)
                await sub.close()
                self.assertEqual(operations, ["status", "status", "watch"])
                if not subprocess and not ssh:
                    async def connect():
                        return await Client.connect(await connect_ipc(root / "mesh.sock"), host=host,
                                                    source="default", profile=adapter.profile, codec=adapter.validate)
                    reader = Reader(domain, [Endpoint(host, True, None, connect)], local_host=host)
                    watch = reader.watch(proof_interval=.1)
                    try:
                        for _ in range(5):
                            view = await asyncio.wait_for(anext(watch), 2)
                            if view["mesh"]["status"] == "complete":
                                break
                        self.assertEqual(view["mesh"]["status"], "complete")
                        self.assertEqual(view["sessions"], native["snapshot"]["sessions"])
                    finally:
                        await watch.aclose()
                for forbidden in ("agent_observer.collection", "agent_observer.adapters", "agent_observer.service_runtime",
                                  "tmux_observer.core", "tmux_observer.owner"):
                    self.assertNotIn(forbidden, sys.modules)
            finally:
                if client:
                    await client.close()
                else:
                    await channel.close()
                if mesh:
                    await mesh.close()
                await owner.close()
                if ssh_context:
                    await ssh_context.__aexit__(None, None, None)
            if subprocess or ssh:
                self.assertIsNotNone(channel.process.returncode)

    async def test_tmux_native_cached_adapter(self):
        await self.exercise("tmux")

    async def test_agent_native_cached_adapter(self):
        await self.exercise("agent")

    async def test_owned_stdio_bridge(self):
        await self.exercise("agent", subprocess=True)

    @unittest.skipUnless(os.getuid() != 0 and all(shutil.which(tool) for tool in ("ssh", "sshd", "ssh-keygen")),
                         "disposable SSH requires non-root user and OpenSSH tools")
    async def test_owned_ssh_bridge(self):
        await self.exercise("agent", ssh=True)
