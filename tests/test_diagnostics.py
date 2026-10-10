import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_delivery import Source

from mesh_plus.bridge import Bridge
from mesh_plus.cli import configured_descriptor
from mesh_plus.client import Client
from mesh_plus.diagnostics import doctor, probe
from mesh_plus.transport import IPCServer, connect_ipc


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_and_push_are_redacted_and_cleanup_owned(self):
        with tempfile.TemporaryDirectory() as name:
            source = Source()
            path = Path(name) / "probe.sock"
            server = await IPCServer(path, Bridge(source).serve).start()
            clients = []
            async def connect():
                client = await Client.connect(await connect_ipc(path), host=source.host,
                    source=source.source, profile=source.profile, codec=source.validate)
                clients.append(client)
                return client
            try:
                for mode in ("snapshot", "subscribe"):
                    report = await probe(connect, mode=mode)
                    self.assertTrue(report["ok"])
                    self.assertNotIn("payload", json.dumps(report))
                    self.assertTrue(clients[-1].channel.closed)
                    metrics = clients[-1].inspect()
                    self.assertEqual(metrics["bufferedBytes"], 0)
                    self.assertGreater(metrics["channel"]["receivedBytes"], 0)
                    copy = clients[-1].channel.inspect()
                    copy["receivedBytes"] = -1
                    self.assertGreater(clients[-1].channel.inspect()["receivedBytes"], 0)
            finally:
                await server.close()
            self.assertFalse(source.watchers)

    async def test_setup_deadline_and_errors_are_redacted(self):
        async def stalled():
            await asyncio.sleep(1)
        self.assertEqual((await probe(stalled, timeout_ms=10))["error"], "deadline")
        async def rejected():
            raise ValueError("private home path and credentials")
        report = await probe(rejected)
        self.assertEqual(report["error"], "rejected")
        self.assertNotIn("private", json.dumps(report))

    async def test_cancellation_propagates(self):
        async def stalled():
            await asyncio.sleep(1)
        task = asyncio.create_task(probe(stalled))
        await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_doctor_without_native_packages_or_network(self):
        self.assertTrue(doctor()["checks"]["observerPackagesOptional"])
        child = subprocess.run([sys.executable, "-m", "mesh_plus.cli", "doctor"],
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)["operation"], "doctor")

    async def test_invalid_probe_budget(self):
        for timeout in (0, 60001, True):
            with self.assertRaises(ValueError):
                await probe(None, timeout_ms=timeout)

    async def test_descriptor_rejects_symlink_and_public_config(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "sources.toml"
            path.write_text('version = 1\nhost = "fixture-host"\n[sources.synthetic]\ndomain = "tmux"\nsocket = "/private/native.sock"\n')
            path.chmod(0o600)
            self.assertEqual(configured_descriptor(path, "synthetic")[1], "tmux")
            link = Path(name) / "link"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                configured_descriptor(link, "synthetic")
            path.chmod(0o644)
            with self.assertRaises(Exception):
                configured_descriptor(path, "synthetic")
