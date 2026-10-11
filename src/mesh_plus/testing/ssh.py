"""Separately requested actual SSH wheel conformance with disposable fixtures."""

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from ..api import Client, Endpoint, Reader, ReadGuard
from ..transport import boottime_ms
from .ssh_carrier import ssh_server


class _SSHTest(unittest.IsolatedAsyncioTestCase):
    def __init__(self, methodName="runTest"):
        super().__init__(methodName)
        self.case_id = "ssh-" + self.domain + "-poll-watch-reconnect-retirement"

    async def test_poll_watch_reconnect_and_retirement(self):
        profile = self.factory(self.domain)
        codec = profile.bind("remote", "configured_source")
        with tempfile.TemporaryDirectory(prefix=".mesh-conformance-", dir=Path.home()) as name:
            command = [sys.executable, "-B", "-m", "mesh_plus.testing.publisher_cli", "--domain", self.domain]
            async with ssh_server(Path(name), command, "configured_source") as channel:
                clients = []
                async def connect():
                    client = await Client.connect(await channel(), host="remote", source="configured_source",
                                                  profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
                    clients.append(client)
                    return client
                async def revision():
                    return "sha256:" + "b" * 64
                reader = Reader(self.domain, [Endpoint("remote", False, "sha256:" + "a" * 64, connect, codec)],
                                local_host="local", catalog_revision=await revision(), catalog_check=revision,
                                profile=profile)
                for _ in range(2):
                    response = await reader.snapshot()
                    self.assertEqual(response["mesh"]["status"], "complete")
                    self.assertIsNotNone(response["mesh"]["hosts"][0]["delivery"]["proof"])
                    guard = ReadGuard(self.domain, "c" * 32, profile=profile)
                    stream = reader.watch(request_id="c" * 32, proof_interval=.1)
                    try:
                        for _ in range(10):
                            frame = await asyncio.wait_for(anext(stream), 3)
                            guard.accept(frame)
                            if guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]):
                                break
                        self.assertTrue(guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]))
                    finally:
                        guard.disconnect()
                        await stream.aclose()
                self.assertTrue(all(c.channel.closed for c in clients))
                self.assertEqual(reader.inspect()["activeConnections"], 0)
                self.assertEqual(reader.inspect()["cleanupFailures"], 0)


def ssh_suite(profile_factory, *, domain):
    """Explicit Linux/OpenSSH gate. Missing tools are an error, never a pass."""
    if domain not in {"tmux", "agent"}:
        raise ValueError("conformance_domain")
    if not all(shutil.which(tool) for tool in ("ssh", "sshd", "ssh-keygen")):
        raise ValueError("conformance_ssh_tools")
    cls = type("OwnerSSHTests", (_SSHTest,), {"domain": domain, "factory": staticmethod(profile_factory)})
    return unittest.defaultTestLoader.loadTestsFromTestCase(cls)
