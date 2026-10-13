"""Owned mTLS/framing/liveness/revocation checks for the experimental TCP carrier."""

import asyncio
import json
import ssl
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "controlled"))
from trace import Trace  # noqa: E402

sys.path.insert(0, str(ROOT.parents[1] / "tests/wss"))
from wss_fixtures import certificates, contexts, fingerprint  # noqa: E402

sys.path.insert(0, str(ROOT))
from tcp_stream import ALPN, DATA, Listener, connect  # noqa: E402

from mesh_plus.api import Bridge, CachedPublication, CachedPublisher, Client, DeliveryError  # noqa: E402
from mesh_plus.protocol import MAX_CONTROL, ProtocolError  # noqa: E402
from mesh_plus.wss import ServerConfiguration  # noqa: E402
from mesh_plus.wss.configuration import tls_context  # noqa: E402


class CarrierTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix=".mesh-tcp-check-", dir=Path.home())
        self.root = Path(self.directory.name)
        self.root.chmod(0o700)
        certificates(self.root)
        self.trace = Trace(4)
        self.reads = 0
        owner = self

        class Native:
            async def snapshot(self):
                owner.reads += 1
                return owner.trace.frame

            async def watch(self):
                yield CachedPublication(owner.trace.frame, owner.trace.frame["publisherId"], {"revision": 1})
                await asyncio.Event().wait()

        self.pub = CachedPublisher("tmux", "beta", "controlled", Native(), profile=self.trace.profile)
        self.policy = self.root / "policy.json"
        self.policy.write_text(json.dumps({fingerprint(self.root): ["beta", "controlled", self.pub.profile]}))
        self.policy.chmod(0o600)
        self.config = ServerConfiguration.load(self.root / "ca.pem", self.root / "server.pem", self.root / "server.key", self.policy)
        self.config.context.set_alpn_protocols([ALPN])
        self.listener = await Listener(self.config.context, Bridge(self.pub).serve, self.config.authorize,
                                       (self.pub.host, self.pub.source, self.pub.profile)).start()
        _, self.context = contexts(self.root)
        self.clients, self.channels = [], []

    async def client(self, context=None):
        channel = await connect(self.listener.port, self.context if context is None else context)
        self.channels.append(channel)
        client = await Client.connect(channel, host=self.pub.host, source=self.pub.source,
                                      profile=self.pub.profile, codec=self.pub.codec.validate_bridge)
        self.clients.append(client)
        return client

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        for channel in self.channels:
            await channel.close()
        await self.listener.close()
        self.config.close()
        self.assertFalse(self.listener.tasks)
        self.assertFalse(self.listener.channels)
        self.assertTrue(all(channel.pump.done() and channel.liveness.done() for channel in self.channels if hasattr(channel, "pump")))
        self.directory.cleanup()

    async def test_poll_push_reconnect_and_nonce_rejection(self):
        for _ in range(3):
            client = await self.client()
            proof = await client.request("proof", {"nonce": "a" * 32})
            self.assertEqual(proof["nonce"], "a" * 32)
            before = self.reads
            with self.assertRaises(DeliveryError):
                await client.request("proof", {"nonce": "invalid"})
            self.assertEqual(self.reads, before)
            sub = await client.subscribe()
            try:
                data = await asyncio.wait_for(anext(sub), 3)
                self.assertEqual(data["kind"], "data")
            finally:
                await sub.close()
            await client.close()

    async def test_four_active_clients_bound_fifth_and_keep_proofs(self):
        clients = [await self.client() for _ in range(4)]
        with self.assertRaises((TimeoutError, OSError, EOFError, ProtocolError)):
            await self.client()
        self.assertLessEqual(self.listener.peak_admitted, 4)
        for client in clients:
            self.assertEqual((await client.request("proof", {"nonce": "b" * 32}))["nonce"], "b" * 32)

    async def test_missing_wrong_and_expired_principals_do_not_read_native(self):
        missing = ssl.create_default_context(cafile=str(self.root / "ca.pem"))
        missing.minimum_version = ssl.TLSVersion.TLSv1_2
        contexts_to_reject = [missing,
            tls_context(self.root / "ca.pem", self.root / "unknown.pem", self.root / "unknown.key"),
            tls_context(self.root / "ca.pem", self.root / "expired.pem", self.root / "expired.key")]
        for context in contexts_to_reject:
            with self.assertRaises((OSError, EOFError, ProtocolError)):
                await self.client(context)
        self.assertEqual(self.reads, 0)
        self.assertEqual(self.listener.dispatched, 0)

    async def raw_rejected(self, payload, timeout=3):
        context = self.context
        context.set_alpn_protocols([ALPN])
        reader, writer = await asyncio.open_connection("127.0.0.1", self.listener.port, ssl=context,
                                                       server_hostname="localhost", ssl_shutdown_timeout=1)
        try:
            writer.write(payload)
            await writer.drain()
            try:
                received = await asyncio.wait_for(reader.read(), timeout)
                self.assertEqual(received, b"")
            except (ConnectionError, ssl.SSLError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ssl.SSLError):
                pass

    async def test_length_rejected_before_body_allocation(self):
        await self.raw_rejected(bytes([DATA]) + (MAX_CONTROL + 1).to_bytes(4, "big"))
        self.assertEqual(self.reads, 0)

    async def test_partial_prefix_and_duplicate_json_keys_fail_closed(self):
        await self.raw_rejected(bytes([DATA]) + b"\0")
        raw = b'{"kind":"hello","kind":"hello"}'
        await self.raw_rejected(bytes([DATA]) + len(raw).to_bytes(4, "big") + raw)
        self.assertEqual(self.reads, 0)

    async def test_wrong_alpn_does_not_dispatch(self):
        self.context.set_alpn_protocols(["not-mesh-study"])
        reader, writer = await asyncio.open_connection("127.0.0.1", self.listener.port, ssl=self.context,
                                                       server_hostname="localhost", ssl_shutdown_timeout=1)
        try:
            try:
                self.assertEqual(await asyncio.wait_for(reader.read(), 2), b"")
            except (OSError, ssl.SSLError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ssl.SSLError):
                pass
        self.assertEqual(self.listener.dispatched, 0)

    async def test_idle_ping_pong_does_not_acquire_or_renew_source(self):
        client = await self.client()
        await asyncio.sleep(11)
        self.assertFalse(client.channel.closed)
        self.assertEqual(self.reads, 0)
        proof = await client.request("proof", {"nonce": "c" * 32})
        self.assertTrue(all(receipt["remainingMs"] == 0 for receipt in proof["remaining"]))
        metrics = client.channel.inspect()
        self.assertGreater(metrics["framedReceivedBytes"], metrics["receivedBytes"] + 5 * metrics["receivedFrames"])

    async def test_missing_pong_closes_without_source_acquisition(self):
        client = await self.client()
        client.channel.pump.cancel()
        client.channel.liveness.cancel()
        await asyncio.gather(client.channel.pump, client.channel.liveness, return_exceptions=True)
        async with asyncio.timeout(12):
            while self.listener.channels:
                await asyncio.sleep(.02)
        self.assertEqual(self.reads, 0)

    async def test_unknown_tag_and_bad_control_length_reject(self):
        await self.raw_rejected(b"\xff" + (0).to_bytes(4, "big"))
        await self.raw_rejected(b"\x01" + (9).to_bytes(4, "big"))
        self.assertEqual(self.reads, 0)

    async def test_policy_change_revokes_admitted_channels(self):
        client = await self.client()
        self.policy.write_text("{}")
        async with asyncio.timeout(7):
            while not client.channel.closed:
                await asyncio.sleep(.02)
        self.assertEqual(self.reads, 0)
        with self.assertRaises((EOFError, ProtocolError, DeliveryError)):
            await client.request("proof", {"nonce": "d" * 32})


if __name__ == "__main__":
    unittest.main(verbosity=2)
