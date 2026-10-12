"""Owned installed-entrypoint publisher acceptance through the fixed SSH command."""

import asyncio
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from sdk_fixture import Profile
from ssh_fixture import ssh_server
from test_publisher import TESTS, config

from mesh_plus.api import Client


class PublisherSSHTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_ssh_command_both_domains_poll_push_and_cleanup(self):
        for domain in ("tmux", "agent"):
            # OpenSSH StrictModes requires fixtures under the same-user private home.
            with tempfile.TemporaryDirectory(prefix="mesh-publisher-ssh-", dir=Path.home()) as directory:
                root = Path(directory)
                path = config(root, domain, host="remote")
                executable = root / "mesh-plus"
                executable.write_text(f'''#!{sys.executable}
import sys
sys.path.insert(0, {str(TESTS)!r})
from publisher_fixture import factory
from mesh_plus.cli import main
sys.argv.extend(["--config", {str(path)!r}])
raise SystemExit(main(publisher_factories={{{domain!r}: factory({domain!r})}}))
''')
                executable.chmod(0o700)
                # Execute the actual fixed remote command in this private installed launcher namespace.
                command = ["/bin/sh", "-c", "PATH=" + shlex.quote(str(root) + ":" + os.environ["PATH"]) +
                           ' exec /bin/sh -c "$SSH_ORIGINAL_COMMAND"']
                async with ssh_server(root, command, "default", command_emits_marker=True) as connect:
                    channel = await connect()
                    client = None
                    try:
                        client = await Client.connect(channel, host="remote", source="default",
                                                      profile=Profile(domain).descriptor.profile_id, codec=lambda p: None)
                        self.assertTrue(channel.reached)
                        self.assertEqual((await client.request("snapshot", {}))["kind"], "candidate")
                        self.assertEqual((await client.request("proof", {"nonce": "a" * 32}))["nonce"], "a" * 32)
                        sub = await client.subscribe()
                        self.assertEqual((await asyncio.wait_for(anext(sub), 3))["kind"], "data")
                        await sub.close()
                    finally:
                        if client is not None:
                            await client.close()
                        else:
                            await channel.close()
                    self.assertTrue(channel.closed)
                    self.assertIsNotNone(channel.process.returncode)
