import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_reader import ROOT

from mesh_plus.catalog import Catalog
from mesh_plus.remote import SetupError, connect_catalog_host
from mesh_plus.transport import ssh_argv


class QuotingTests(unittest.TestCase):
    def test_remote_posix_wrapper_executes_only_fixed_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "mesh-plus"
            command.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\n')
            command.chmod(0o700)
            nonce = "a" * 32
            argv = ssh_argv("host", "agent_default", nonce=nonce)
            result = subprocess.run(["/bin/sh", "-c", argv[-1]], env={**os.environ, "PATH": directory + ":/usr/bin:/bin"},
                                    capture_output=True, check=True)
            self.assertEqual(result.stdout, b"bridge\n--source\nagent_default\n--stdio\n")
            self.assertEqual(result.stderr, ("\x1eROFI_PLUS_REACHED_V1:" + nonce + "\x1f\n").encode())


class RouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import json
        self.catalog = Catalog(json.loads((ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/fixtures/valid/list-multi-route.json").read_text()))
        self.host = self.catalog.hosts[1]

    async def test_transport_failure_can_try_second_route(self):
        calls = []
        channels = []

        async def connector(destination, *_args, **_kwargs):
            calls.append(destination)
            channel = AsyncMock()
            channel.reached = False
            channel.stderr_tail = bytearray(b"Connection refused")
            channels.append(channel)
            return channel

        client = AsyncMock()
        with patch("mesh_plus.remote.Client.connect", side_effect=[EOFError(), client]):
            result = await connect_catalog_host(self.catalog, self.host, "tmux", "default", connector=connector)
        self.assertIs(result, client)
        self.assertEqual(calls, [r["destination"] for r in self.host["routes"]])
        self.assertEqual(client.route_token, self.catalog.route_token("beta", self.host["routes"][1]))

    async def test_policy_and_reached_failures_do_not_fallback(self):
        for reached, diagnostic, code in [(False, b"Permission denied", "setup_policy_failure"),
                                          (True, b"tool missing", "source_unavailable")]:
            calls = []
            async def connector(destination, *_args, **_kwargs):
                calls.append(destination)
                channel = AsyncMock()
                channel.reached = reached
                channel.stderr_tail = bytearray(diagnostic)
                return channel
            with patch("mesh_plus.remote.Client.connect", side_effect=EOFError()), self.assertRaises(SetupError) as raised:
                await connect_catalog_host(self.catalog, self.host, "tmux", "default", connector=connector)
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(len(calls), 1)
