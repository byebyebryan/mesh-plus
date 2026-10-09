import asyncio
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mesh_plus.bridge import Bridge
from mesh_plus.client import Client
from mesh_plus.observer import ObserverAdapter, clock_domain
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
    async def exercise(self, domain, subprocess=False):
        with tempfile.TemporaryDirectory() as directory:
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
            if subprocess:
                config = root / "sources.toml"
                config.write_text(f'version = 1\nhost = "{host}"\n[sources.default]\ndomain = "{domain}"\nsocket = "{root / "owner.sock"}"\n')
                config.chmod(0o600)
                channel = await subprocess_channel([sys.executable, "-m", "mesh_plus.cli", "bridge", "--source",
                                                    "default", "--stdio", "--config", str(config)])
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
                sub = await client.subscribe()
                self.assertEqual((await anext(sub))["payload"]["kind"], "candidate")
                for queue in queues:
                    queue.put_nowait(True)
                pushed = await asyncio.wait_for(anext(sub), 2)
                self.assertEqual(pushed["payload"]["ownerFrame"]["viewRevision"], native["viewRevision"] + 1)
                await sub.close()
                self.assertEqual(operations, ["status", "status", "watch"])
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
            if subprocess:
                self.assertIsNotNone(channel.process.returncode)

    async def test_tmux_native_cached_adapter(self):
        await self.exercise("tmux")

    async def test_agent_native_cached_adapter(self):
        await self.exercise("agent")

    async def test_owned_stdio_bridge(self):
        await self.exercise("agent", subprocess=True)
