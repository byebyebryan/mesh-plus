"""Explicit owned fixed-SSH projected member/empty proofs and reconnection."""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from active_fixture import PROFILE, ActiveProfile
from prepared_fixture import StaticPreparation

from mesh_plus.api import Client, Endpoint, PreparedReadGuard, Reader, reconstructed
from mesh_plus.testing.ssh_carrier import ssh_server
from mesh_plus.transport import boottime_ms


class ActiveSSHTests(unittest.IsolatedAsyncioTestCase):
    async def test_installed_capable_fixed_ssh_full_projected_proofs_empty_and_reconnect(self):
        profile = ActiveProfile()
        codec = profile.bind("remote", "active")
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory(prefix=".mesh-active-", dir=Path.home()) as name:
                command = [sys.executable, "-B", str(Path(__file__).with_name("active_publisher_cli.py"))]
                if empty:
                    command.append("--empty")
                async with ssh_server(Path(name), command, "active") as channel:
                    clients = []
                    async def connect():
                        client = await Client.connect(await channel(), host="remote", source="active", profile=PROFILE,
                                                      codec=codec.validate_bridge)
                        clients.append(client)
                        return client
                    async def revision():
                        return "sha256:" + "b" * 64
                    reader = Reader("agent", [Endpoint("remote", False, "sha256:" + "a" * 64, connect, codec)],
                                    local_host="local", catalog_revision=await revision(), catalog_check=revision,
                                    profile=profile)
                    for _ in range(2):
                        response = await reader.snapshot()
                        self.assertEqual(response["mesh"]["status"], "complete")
                        self.assertEqual(len(response["sessions"]), 0 if empty else 1)
                        host = response["mesh"]["hosts"][0]
                        self.assertIsNotNone(host["delivery"]["proof"])
                        self.assertIn("selectorDigest", reconstructed(response, host, profile=profile))
                        guard = PreparedReadGuard("agent", "c" * 32, profile=profile,
                                                  preparation=StaticPreparation(profile))
                        stream = reader.watch_admitted(request_id="c" * 32, proof_interval=.1)
                        try:
                            for _ in range(10):
                                guard.accept(await asyncio.wait_for(anext(stream), 3))
                                context = guard.context()
                                if context and context["mesh"]["status"] == "complete":
                                    break
                            self.assertEqual(context["mesh"]["status"], "complete")
                            rows = guard.current(boottime_ms(), context["mesh"]["reader"]["clock"])
                            self.assertEqual(len(rows), 0 if empty else 1)
                            self.assertEqual(guard.context()["mesh"]["hosts"][0]["owner"]["metadata"]
                                             ["scopes"][0]["coverage"]["status"], "complete")
                        finally:
                            guard.disconnect()
                            await stream.aclose()
                    self.assertTrue(all(client.channel.closed for client in clients))
                    self.assertEqual(reader.inspect()["activeConnections"], 0)
                    self.assertEqual(reader.inspect()["cleanupFailures"], 0)
