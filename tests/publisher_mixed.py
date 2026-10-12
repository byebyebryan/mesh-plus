"""Explicit installed a10 reference bridge compatibility fixture; no live service."""

import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path

from publisher_fixture import Source
from sdk_fixture import Profile
from ssh_fixture import ssh_server
from test_publisher import config

from mesh_plus.api import Client, Endpoint, Reader
from mesh_plus.transport import IPCServer


def mixed_suite(baseline_python):
    class MixedPublisherTests(unittest.IsolatedAsyncioTestCase):
        async def test_a15_explicit_reader_with_a10_reference_ssh_bridge(self):
            for domain in ("tmux", "agent"):
                with tempfile.TemporaryDirectory(prefix="mesh-publisher-mixed-", dir=Path.home()) as name:
                    root = Path(name)
                    source = Source(domain, "remote")
                    native_watchers = set()
                    async def native(channel):
                        request = json.loads(await channel.reader.readuntil(b"\n"))
                        frame = copy.deepcopy(source.fixture.frame)
                        if domain == "tmux":
                            frame["requestId"] = request["requestId"]
                        channel.writer.write(json.dumps(frame).encode() + b"\n")
                        await channel.writer.drain()
                        if request["operation"] == "watch":
                            native_watchers.add(channel)
                            try:
                                await channel.reader.read()
                            finally:
                                native_watchers.discard(channel)
                    owner = await IPCServer(root / "native.sock", native).start()
                    path = config(root, domain, "remote")
                    path.write_text(path.read_text().replace('/unused', str(root / "native.sock")))
                    command = [str(baseline_python), "-I", "-m", "mesh_plus.cli", "bridge", "--source", "default",
                               "--stdio", "--config", str(path)]
                    clients = []
                    try:
                        async with ssh_server(root, command, "default") as channel_connect:
                            profile = Profile(domain)
                            async def connect():
                                client = await Client.connect(await channel_connect(), host="remote", source="default",
                                                              profile=profile.descriptor.profile_id,
                                                              codec=profile.bind("remote", "default").validate_bridge)
                                clients.append(client)
                                return client
                            reader = Reader(domain, [Endpoint("remote", False, "sha256:" + "a" * 64, connect,
                                                              profile.bind("remote", "default"))], local_host="local",
                                            catalog_revision="sha256:" + "b" * 64,
                                            catalog_check=lambda: asyncio.sleep(0, result="sha256:" + "b" * 64),
                                            profile=profile)
                            response = await reader.snapshot()
                            self.assertEqual(response["mesh"]["status"], "complete", response)
                            self.assertEqual(response["mesh"]["hosts"][0]["delivery"]["path"], "ssh")
                            watch = reader.watch()
                            try:
                                for _ in range(10):
                                    response = await asyncio.wait_for(anext(watch), 3)
                                    if response["mesh"]["status"] == "complete":
                                        break
                                self.assertEqual(response["mesh"]["status"], "complete")
                            finally:
                                await watch.aclose()
                            self.assertEqual(reader.inspect()["activeConnections"], 0)
                            self.assertTrue(all(c.channel.process.returncode is not None for c in clients))
                    finally:
                        await owner.close()
                    self.assertFalse(native_watchers)
    return unittest.defaultTestLoader.loadTestsFromTestCase(MixedPublisherTests)
