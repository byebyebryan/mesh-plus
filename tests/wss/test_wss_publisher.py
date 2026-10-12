"""Trusted installed WSS launcher selects the same owner factory as IPC/SSH."""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from publisher_fixture import factory
from wss_fixtures import certificates, contexts, fingerprint, write_policy

from mesh_plus.api import Client
from mesh_plus.testing.ssh_carrier import _stop
from mesh_plus.wss import connect

TESTS = Path(__file__).resolve().parents[1]


class WSSPublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_injected_wss_cli_both_domains_poll_push_and_cleanup(self):
        for domain in ("tmux", "agent"):
            with tempfile.TemporaryDirectory(prefix="mesh-publisher-wss-") as name:
                root = Path(name)
                await asyncio.to_thread(certificates, root)
                _, context = contexts(root)
                publisher = factory(domain)("beta", "default", "/unused")
                config = root / "sources.toml"
                config.write_text(f'version=1\nhost="beta"\n[sources.default]\ndomain="{domain}"\nsocket="/unused"\n')
                config.chmod(0o600)
                policy = root / "authorization.json"
                write_policy(policy, {fingerprint(root): ["beta", "default", publisher.profile]})
                script = root / "launcher.py"
                script.write_text(f'''import sys
sys.path.insert(0, {str(TESTS)!r})
from publisher_fixture import factory
from mesh_plus.wss.cli import main
raise SystemExit(main(publisher_factories={{{domain!r}: factory({domain!r})}}))
''')
                process = await asyncio.create_subprocess_exec(sys.executable, "-I", str(script), "serve",
                    "--config", str(config), "--source", "default", "--authorization", str(policy),
                    "--address", "127.0.0.1", "--port", "0", "--ca", str(root / "ca.pem"),
                    "--certificate", str(root / "server.pem"), "--key", str(root / "server.key"),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                client = None
                try:
                    ready = json.loads(await asyncio.wait_for(process.stdout.readline(), 5))
                    channel = await connect(f'wss://localhost:{ready["port"]}/mesh/state', context)
                    client = await Client.connect(channel, host="beta", source="default", profile=publisher.profile,
                                                  codec=publisher.validate)
                    self.assertEqual((await client.request())["kind"], "candidate")
                    self.assertEqual((await client.request("proof", {"nonce": "a" * 32}))["nonce"], "a" * 32)
                    sub = await client.subscribe()
                    self.assertEqual((await asyncio.wait_for(anext(sub), 2))["kind"], "data")
                    await sub.close()
                    await client.close()
                    client = None
                    process.terminate()
                    _, stderr = await asyncio.wait_for(process.communicate(), 5)
                    self.assertEqual(process.returncode, 0, stderr)
                finally:
                    if client is not None:
                        await client.close()
                    await _stop(process)
