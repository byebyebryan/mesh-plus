"""Actual private Tmux owner over both full-proof study carriers; correctness only."""

import asyncio
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from check_carrier import CarrierTests  # noqa: E402
from identity import command, retire  # noqa: E402
from tcp_stream import ALPN, Listener, connect  # noqa: E402
from tmux_observer.mesh_publisher import make_publisher  # noqa: E402

from mesh_plus.api import Bridge, Client, DeliveryError  # noqa: E402
from mesh_plus.evidence import digest  # noqa: E402
from mesh_plus.wss import Listener as WSSListener  # noqa: E402
from mesh_plus.wss import connect as connect_wss  # noqa: E402


class NativeTests(CarrierTests):
    async def test_actual_owned_poll_push_change_loss_restart(self):
        await self.listener.close()
        with tempfile.TemporaryDirectory(prefix="mesh-carrier-native-") as name:
            root = Path(name)
            root.chmod(0o700)
            env = {**os.environ, "TMUX_TMPDIR": str(root)}
            env.pop("TMUX", None)
            env.pop("TMUX_PANE", None)
            owner = None

            async def start():
                return await asyncio.create_subprocess_exec(sys.executable, "-I", "-B", "-m", "tmux_observer", "owner",
                    "--host-id", "beta", "--socket", str(root / "owner.sock"), env=env,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)

            async def proof(client, expected):
                async with asyncio.timeout(8):
                    while True:
                        value = await client.request("proof", {"nonce": secrets.token_hex(16)})
                        frame = value["ownerFrame"]
                        self.assertEqual(value["ownerDigest"], digest(frame))
                        snapshot = frame["snapshot"]
                        if snapshot is not None and [row["name"] for row in snapshot["sessions"]] == expected:
                            return value
                        await asyncio.sleep(.05)

            try:
                await command(env, "tmux", "-L", "default", "-f", "/dev/null", "new-session", "-d", "-s", "carrier-fixture", "sleep 180")
                owner = await start()
                async with asyncio.timeout(5):
                    while not (root / "owner.sock").exists():
                        await asyncio.sleep(.02)
                source = make_publisher("beta", "controlled", root / "owner.sock")
                for carrier in ("wss", "tcp"):
                    selected = Listener if carrier == "tcp" else WSSListener
                    self.config.context.set_alpn_protocols([ALPN] if carrier == "tcp" else [])
                    self.listener = await selected(self.config.context, Bridge(source).serve, self.config.authorize,
                        (source.host, source.source, source.profile)).start()
                    channel = await connect(self.listener.port, self.context) if carrier == "tcp" else await connect_wss(
                        f"wss://127.0.0.1:{self.listener.port}/mesh/state", self.context, server_hostname="localhost")
                    self.channels.append(channel)
                    client = await Client.connect(channel, host=source.host, source=source.source,
                        profile=source.profile, codec=source.codec.validate_bridge)
                    self.clients.append(client)
                    initial = await proof(client, ["carrier-fixture"])
                    sub = await client.subscribe()
                    try:
                        publication = await asyncio.wait_for(anext(sub), 4)
                        self.assertEqual(publication["kind"], "data")
                        await command(env, "tmux", "-L", "default", "rename-session", "-t", "carrier-fixture", "carrier-changed")
                        async with asyncio.timeout(8):
                            while True:
                                publication = await anext(sub)
                                if publication["kind"] == "data" and publication["payload"]["ownerFrame"]["snapshot"]["sessions"][0]["name"] == "carrier-changed":
                                    break
                        await proof(client, ["carrier-changed"])
                    finally:
                        await sub.close()
                    await retire(owner)
                    with self.assertRaises((DeliveryError, OSError, EOFError, ValueError)):
                        await client.request("proof", {"nonce": secrets.token_hex(16)})
                    owner = await start()
                    async with asyncio.timeout(5):
                        while not (root / "owner.sock").exists():
                            await asyncio.sleep(.02)
                    restarted = await proof(client, ["carrier-changed"])
                    self.assertNotEqual(initial["ownerFrame"]["publisherId"], restarted["ownerFrame"]["publisherId"])
                    await command(env, "tmux", "-L", "default", "rename-session", "-t", "carrier-changed", "carrier-fixture")
                    await proof(client, ["carrier-fixture"])
                    await client.close()
                    await self.listener.close()
                    print(json.dumps({"actualNativeCarrier": carrier, "pollPushRenameSourceLossRestart": "passed"}), flush=True)
            finally:
                if owner is not None:
                    await retire(owner)
                child = await asyncio.create_subprocess_exec("tmux", "-L", "default", "kill-server", env=env,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await asyncio.wait_for(child.wait(), 5)


if __name__ == "__main__":
    import unittest
    os.umask(0o077)
    unittest.main(defaultTest="NativeTests.test_actual_owned_poll_push_change_loss_restart", verbosity=2)
