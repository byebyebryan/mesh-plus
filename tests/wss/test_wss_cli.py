"""Installed CLI listener/read/watch/probe over disposable cached native IPC."""

import asyncio
import copy
import json
import signal
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from wss_fixtures import BroadcastPublisher, certificates, fingerprint, write_policy

from mesh_plus.testing.ssh_carrier import _stop
from mesh_plus.transport import IPCServer


class CLICase(unittest.IsolatedAsyncioTestCase):
    async def test_listener_and_all_client_commands_both_native_profiles(self):
        for domain in ("tmux", "agent"):
            with tempfile.TemporaryDirectory(prefix="mesh-wss-cli-") as name:
                root = Path(name)
                await asyncio.to_thread(certificates, root)
                publisher = BroadcastPublisher(domain)
                watchers = set()

                async def native(channel):
                    request = json.loads(await channel.reader.readuntil(b"\n"))
                    frame = copy.deepcopy(publisher.frame)
                    if domain == "tmux":
                        frame["requestId"] = request["requestId"]
                    channel.writer.write(json.dumps(frame).encode() + b"\n")
                    await channel.writer.drain()
                    if request["operation"] == "watch":
                        watchers.add(channel)
                        try:
                            await channel.reader.read()
                        finally:
                            watchers.discard(channel)

                owner = await IPCServer(root / "native.sock", native).start()
                config = root / "sources.toml"
                config.write_text(f'version = 1\nhost = "beta"\n[sources.default]\ndomain = "{domain}"\n'
                                  f'socket = "{root / "native.sock"}"\n')
                config.chmod(0o600)
                policy = root / "authorization.json"
                write_policy(policy, {fingerprint(root): ["beta", "default", publisher.profile]})
                server = watcher = None
                try:
                    common = [sys.executable, "-B", "-m", "mesh_plus.wss.cli"]
                    server = await asyncio.create_subprocess_exec(*common, "serve", "--config", str(config),
                        "--source", "default", "--authorization", str(policy), "--address", "127.0.0.1",
                        "--port", "0", "--ca", str(root / "ca.pem"), "--certificate", str(root / "server.pem"),
                        "--key", str(root / "server.key"), stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE)
                    ready = json.loads(await asyncio.wait_for(server.stdout.readline(), 5))
                    self.assertTrue(ready["ready"])
                    catalog = root / "catalog.json"
                    catalog.write_bytes(files("mesh_plus.testing").joinpath("catalog.json").read_bytes())
                    registry = root / "registry.json"
                    registry.write_text(json.dumps({"protocol": "mesh-plus.wss.v1", "endpoints": [
                        {"hostId": "beta", "sourceId": "default", "profile": publisher.profile,
                         "url": f'wss://localhost:{ready["port"]}/mesh/state', "product": "state",
                         "capabilities": ["snapshot", "proof", "subscribe"]}]}))
                    for path in (catalog, registry):
                        path.chmod(0o600)
                    options = ["--catalog", str(catalog), "--registry", str(registry), "--domain", domain,
                               "--source", "default", "--socket", str(root / "unused.sock"), "--scope", "hosts",
                               "--hosts", "beta", "--ca", str(root / "ca.pem"), "--certificate",
                               str(root / "client.pem"), "--key", str(root / "client.key")]
                    for command, extra in (("doctor", []), ("read", options),
                                           ("probe", [*options, "--mode", "subscribe"])):
                        process = await asyncio.create_subprocess_exec(*common, command, *extra,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        try:
                            out, err = await asyncio.wait_for(process.communicate(), 8)
                            self.assertEqual(process.returncode, 0, err.decode())
                            report = json.loads(out)
                            if command == "read":
                                self.assertEqual(report["mesh"]["status"], "complete", report)
                                self.assertEqual(report["mesh"]["hosts"][0]["delivery"]["path"], "wss")
                            else:
                                self.assertTrue(report["ok"], report)
                        finally:
                            await _stop(process)
                    watcher = await asyncio.create_subprocess_exec(*common, "watch", *options, "--metrics",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    for _ in range(10):
                        frame = json.loads(await asyncio.wait_for(watcher.stdout.readline(), 5))
                        if frame.get("mesh", {}).get("status") == "complete":
                            break
                    self.assertEqual(frame["mesh"]["status"], "complete")
                    watcher.send_signal(signal.SIGINT)
                    _, err = await asyncio.wait_for(watcher.communicate(), 5)
                    self.assertEqual(watcher.returncode, 130)
                    metrics = json.loads(err)
                    self.assertEqual(metrics["activeConnections"], 0)
                    self.assertEqual(metrics["cleanupFailures"], 0)
                    server.terminate()
                    _, err = await asyncio.wait_for(server.communicate(), 5)
                    self.assertEqual(server.returncode, 0, err.decode())
                    self.assertFalse(watchers)
                finally:
                    if watcher is not None:
                        await _stop(watcher)
                    if server is not None:
                        await _stop(server)
                    await owner.close()
