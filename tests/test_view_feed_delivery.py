"""Real Delivery IPC/stdio composition of the explicitly negotiated view feed."""

import asyncio
import copy
import gc
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from publisher_fixture import Source
from sdk_fixture import Profile

from mesh_plus.api import Bridge, CachedPublisher, Client, Endpoint, Reader
from mesh_plus.client import Subscription
from mesh_plus.evidence import digest
from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import IPCServer, connect_ipc, subprocess_channel
from mesh_plus.view_feed import (
    FeedLimits,
    ViewFeedBridge,
    ViewFeedChange,
    ViewFeedClient,
    ViewFeedSubscription,
    configured_reader,
)


class ViewFeedDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.was_gc_enabled = gc.isenabled()
        gc.disable()
        self.addCleanup(lambda: gc.enable() if self.was_gc_enabled else None)

    async def start(self, *, domain="tmux", legacy=False, selector=None, **options):
        root = tempfile.TemporaryDirectory(prefix="vf-")
        self.addCleanup(root.cleanup)
        self.path = Path(root.name) / "feed.sock"
        self.source = Source(domain, "local")
        self.profile = Profile(domain)
        self.publisher = CachedPublisher(domain, "local", "default", self.source, profile=self.profile)
        bridge = (Bridge(self.publisher) if legacy else
                  ViewFeedBridge(self.publisher, profile=self.profile, selector=selector,
                                 heartbeat_interval=.05, **options))
        self.server_channels = []

        async def serve(channel):
            self.server_channels.append(channel)
            await bridge.serve(channel)

        server = await IPCServer(self.path, serve).start()
        self.addAsyncCleanup(server.close)
        return server

    async def connect(self, *, selector=None):
        client = await ViewFeedClient.connect(await connect_ipc(self.path), host="local", source="default",
                                            profile=self.profile, selector=selector)
        self.addAsyncCleanup(client.close)
        return client

    async def data(self, subscription):
        while True:
            frame = await asyncio.wait_for(anext(subscription), 3)
            if frame["kind"] == "data":
                return frame

    def update(self, *, rows=True):
        frame = self.source.fixture.frame
        frame["viewRevision"] += 1
        if rows:
            sessions = frame["snapshot"]["sessions"]
            sessions[0]["name"] += "!"
        self.source.fixture.changes.put_nowait(None)

    async def test_setup_is_explicit_and_per_connection_without_native_read(self):
        await self.start()
        a, b = await self.connect(), await self.connect()
        self.assertEqual(self.source.reads, 0)
        self.assertNotEqual(a.guard.channel, b.guard.channel)
        sub = await a.subscribe()
        frame = await self.data(sub)
        self.assertEqual(frame["payload"]["ownerFrame"], self.source.fixture.frame)
        await sub.close()
        self.assertFalse(b.closed)
        self.assertEqual((await b.request())["kind"], "candidate")

    async def test_receiver_constructor_refusal_retires_raw_subscription_and_preserves_sibling(self):
        await self.start()
        client, sibling = await self.connect(), await self.connect()
        other = await client.subscribe()
        first = await self.data(other)
        with patch("mesh_plus.view_feed.delivery.FeedReceiver",
                   side_effect=ProtocolError("view_feed_capacity")):
            with self.assertRaisesRegex(ProtocolError, "view_feed_capacity"):
                await client.subscribe()
        self.assertEqual(list(client.client.subscriptions), [other.subscription.key])
        self.assertEqual(client._subscriptions, {other})
        self.assertEqual(self.source.fixture.watchers, 1)
        self.update()
        self.assertEqual((await self.data(other))["payload"]["ownerFrame"], self.source.fixture.frame)
        self.assertTrue(first["payload"]["ownerFrame"]["snapshot"]["sessions"])
        await other.close()
        self.assertEqual(self.source.fixture.watchers, 0)
        self.assertEqual((await sibling.request())["kind"], "candidate")

    async def test_legacy_endpoint_refuses_negotiation_without_fallback(self):
        await self.start(legacy=True)
        with self.assertRaises(Exception):
            await self.connect()
        self.assertEqual(self.source.reads, 0)

    async def test_existing_callable_codec_with_incidental_method_keeps_validation_behavior(self):
        await self.start(legacy=True)
        calls = []

        class Validator:
            def __call__(self, payload):
                calls.append(payload["kind"])

            def admit_payload(self, *_args, **_kwargs):
                raise AssertionError("not an opted-in ownership adapter")

        client = await Client.connect(await connect_ipc(self.path), host="local", source="default",
                                      profile=self.profile.descriptor.profile_id, codec=Validator())
        self.addAsyncCleanup(client.close)
        self.assertEqual((await client.request())["kind"], "candidate")
        self.assertEqual(calls, ["candidate"])

    async def test_wrong_selector_refuses_before_native_io(self):
        await self.start(selector={"windowMs": 72})
        with self.assertRaises(Exception):
            await self.connect(selector={"windowMs": 24})
        self.assertEqual(self.source.reads, 0)

    async def test_selector_binding_distinguishes_bool_float_and_integer_before_io(self):
        await self.start(selector={"windowMs": 1, "options": {"a": 1, "b": False}})
        for bad in (True, 1.0):
            with self.subTest(value=bad), self.assertRaises(Exception):
                await self.connect(selector={"windowMs": bad, "options": {"a": 1, "b": False}})
        client = await self.connect(selector={"options": {"b": False, "a": 1}, "windowMs": 1})
        self.assertFalse(client.closed)
        self.assertEqual(self.source.reads, 0)

    async def test_plain_client_cannot_subscribe_without_feed_setup(self):
        await self.start()
        client = await Client.connect(await connect_ipc(self.path), host="local", source="default",
                                      profile=self.profile.descriptor.profile_id, codec=lambda p: None)
        self.addAsyncCleanup(client.close)
        with self.assertRaises(Exception):
            sub = await client.subscribe()
            await self.data(sub)
        self.assertEqual(self.source.fixture.watchers, 0)

    async def test_original_snapshot_and_fresh_nonce_proof_are_unchanged(self):
        await self.start()
        client = await self.connect()
        first = await client.request()
        proof = await client.request("proof", {"nonce": "a" * 32})
        self.assertEqual(self.source.reads, 2)
        self.assertEqual(first["kind"], "candidate")
        self.assertEqual(proof["kind"], "proof")
        self.assertEqual(proof["nonce"], "a" * 32)
        self.assertEqual(proof["ownerDigest"], digest(self.source.fixture.frame))

    async def test_baseline_updates_and_metadata_reconstruct_exact_original(self):
        await self.start()
        client = await self.connect()
        sub = await client.subscribe()
        first = await self.data(sub)
        saved = copy.deepcopy(first["payload"])
        self.update()
        second = await self.data(sub)
        self.assertEqual(second["payload"]["ownerFrame"], self.source.fixture.frame)
        self.assertEqual(first["payload"], saved)
        self.update(rows=False)
        third = await self.data(sub)
        self.assertEqual(third["payload"]["ownerFrame"], self.source.fixture.frame)
        self.assertEqual(len(third.applied.upserts), 0)
        await sub.close()

    async def test_change_only_api_retains_validated_view_and_exposes_reset(self):
        await self.start()
        client = await self.connect()
        changes = client.changes()
        first = await asyncio.wait_for(anext(changes), 3)
        self.assertIsInstance(first, ViewFeedChange)
        self.assertEqual(first.kind, "replacement")
        self.update()
        event = await asyncio.wait_for(anext(changes), 3)
        while not isinstance(event, ViewFeedChange):
            event = await asyncio.wait_for(anext(changes), 3)
        self.assertEqual(event.candidate["ownerFrame"], self.source.fixture.frame)
        self.assertGreater(event.revision, first.revision)
        first.close()
        event.close()
        await changes.aclose()

    async def test_ordinary_reader_local_path_retains_legacy_result_and_proof_rules(self):
        await self.start()

        async def connect():
            return await ViewFeedClient.connect(await connect_ipc(self.path), host="local", source="default",
                                               profile=self.profile)

        reader = Reader("tmux", [Endpoint("local", True, None, connect,
                                          self.profile.bind("local", "default"))],
                        local_host="local", profile=self.profile)
        result = await reader.snapshot(mode="local")
        self.assertEqual(result["sessions"], self.source.fixture.frame["snapshot"]["sessions"])
        watch = reader.watch(mode="local", proof_interval=.1)
        try:
            for _ in range(8):
                result = await asyncio.wait_for(anext(watch), 3)
                if result["sessions"]:
                    break
            self.assertEqual(result["sessions"], self.source.fixture.frame["snapshot"]["sessions"])
        finally:
            await watch.aclose()
        self.assertEqual(reader.inspect()["activeConnections"], 0)

    async def test_two_subscriptions_share_budget_and_one_close_preserves_sibling(self):
        await self.start()
        client = await self.connect()
        a, b = await client.subscribe(), await client.subscribe()
        first_a, first_b = await self.data(a), await self.data(b)
        self.assertIs(a.receiver.budget, b.receiver.budget)
        await a.close()
        self.assertFalse(b.closed)
        self.update()
        self.assertEqual((await self.data(b))["payload"]["ownerFrame"], self.source.fixture.frame)
        del first_a, first_b
        await b.close()

    async def test_zero_credit_coalescing_requires_gap_then_exact_replacement(self):
        await self.start()
        client = await self.connect()
        raw = Subscription(client.client, "zero-credit")
        client.client.subscriptions[raw.key] = raw
        await client.client._send("subscribe", subscriptionId=raw.key,
                                  start={"mode": "baseline", "cursor": None},
                                  credit={"frames": 0, "bytes": 0})
        await asyncio.wait_for(raw.ready, 3)
        sub = ViewFeedSubscription(client, raw)
        client._subscriptions.add(sub)
        for _ in range(3):
            self.update()
            await asyncio.sleep(.03)
        await client.client._send("credit", subscriptionId=raw.key,
                                  credit={"frames": 1, "bytes": 1_000_000})
        gap = False
        for _ in range(15):
            frame = await asyncio.wait_for(anext(sub), 3)
            if frame["kind"] == "control":
                gap |= frame["control"] == "gap"
                continue
            self.assertTrue(gap)
            self.assertEqual(frame["deliveryKind"], "resync")
            self.assertEqual(frame.applied.kind, "replacement")
            self.assertEqual(frame["payload"]["ownerFrame"], self.source.fixture.frame)
            break
        else:
            self.fail("coalesced replacement missing")
        await sub.close()

    async def test_legacy_resync_ignores_incidental_reset_method(self):
        await self.start(legacy=True)

        def incidental(_publication):
            raise AssertionError("legacy publisher did not opt in to feed reset")

        self.publisher.reset_publication = incidental
        client = await Client.connect(await connect_ipc(self.path), host="local", source="default",
                                      profile=self.profile.descriptor.profile_id,
                                      codec=self.profile.bind("local", "default").validate_bridge)
        self.addAsyncCleanup(client.close)
        sub = Subscription(client, "legacy-zero-credit")
        client.subscriptions[sub.key] = sub
        await client._send("subscribe", subscriptionId=sub.key,
                           start={"mode": "baseline", "cursor": None}, credit={"frames": 0, "bytes": 0})
        await asyncio.wait_for(sub.ready, 3)
        for _ in range(2):
            self.update()
            await asyncio.sleep(.03)
        await client._send("credit", subscriptionId=sub.key, credit={"frames": 1, "bytes": 1_000_000})
        frame = await self.data(sub)
        self.assertEqual(frame["deliveryKind"], "resync")
        self.assertEqual(frame["payload"]["ownerFrame"], self.source.fixture.frame)
        await sub.close()

    async def test_retained_output_stays_funded_after_client_close_and_retires_without_gc(self):
        server = await self.start()
        client = await self.connect()
        sub = await client.subscribe()
        frame = await self.data(sub)
        borrowed = frame["payload"]["ownerFrame"]["snapshot"]["sessions"]
        await client.close()
        await server.close()
        self.assertGreater(client.budget.inspect()["heapBytes"], 0)
        self.assertEqual(len(borrowed), 1)
        del frame, borrowed, sub
        self.assertEqual(client.budget.inspect()["heapBytes"], 0)
        self.assertEqual(client.budget.inspect()["encodedBytes"], 0)
        for channel in self.server_channels:
            self.assertEqual(channel.codec.budget.inspect()["heapBytes"], 0)
            self.assertEqual(channel.codec.budget.inspect()["encodedBytes"], 0)

    async def test_server_close_joins_admitted_held_drain_without_early_refund(self):
        server = await self.start()
        client = await self.connect()
        channel = self.server_channels[0]
        original = channel.writer.drain
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def held_drain():
            nonlocal calls
            calls += 1
            if calls >= 2:  # subscribed drains; the actual first data write waits
                entered.set()
                await release.wait()
            await original()

        channel.writer.drain = held_drain
        subscribe = asyncio.create_task(client.subscribe())
        try:
            await asyncio.wait_for(entered.wait(), 3)
            closing = asyncio.create_task(server.close())
            await asyncio.sleep(.02)
            self.assertFalse(closing.done())
            self.assertGreater(channel.codec.budget.inspect()["encodedBytes"], 0)
            release.set()
            await asyncio.wait_for(closing, 3)
            try:
                await subscribe
            except (EOFError, ProtocolError, Exception):
                pass
        finally:
            release.set()
            channel.writer.drain = original
            await client.close()
        self.assertEqual(channel.codec.budget.inspect()["heapBytes"], 0)

    async def test_configured_reader_explicit_local_route_uses_feed_client(self):
        await self.start()
        reader = await configured_reader("tmux", source="default", socket=self.path,
                                         scope="local", local_host="local", profile=self.profile)
        view = await reader.snapshot(mode="local")
        self.assertEqual(view["sessions"], self.source.fixture.frame["snapshot"]["sessions"])
        self.assertEqual(reader.inspect()["activeConnections"], 0)

    async def test_repeated_cancel_and_close_retires_watch_without_sibling_close(self):
        await self.start()
        a, b = await self.connect(), await self.connect()
        sub = await a.subscribe()
        frame = await self.data(sub)
        pending = asyncio.create_task(anext(sub))
        await asyncio.sleep(0)
        pending.cancel()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        await sub.close()
        await sub.close()
        await a.close()
        await a.close()
        self.assertEqual((await b.request())["kind"], "candidate")
        del frame
        self.assertEqual(self.source.fixture.watchers, 0)

    async def test_concurrent_close_joins_one_cleanup_despite_repeated_cancellation(self):
        await self.start()
        client, sibling = await self.connect(), await self.connect()
        sub = await client.subscribe()
        frame = await self.data(sub)
        original = client.client._send
        entered, release = asyncio.Event(), asyncio.Event()

        async def held_send(kind, **fields):
            if kind == "cancel" and fields.get("handleId") == sub.subscription.key:
                entered.set()
                await release.wait()
            return await original(kind, **fields)

        client.client._send = held_send
        first = asyncio.create_task(sub.close())
        await asyncio.wait_for(entered.wait(), 3)
        second = asyncio.create_task(sub.close())
        try:
            await asyncio.sleep(.02)
            self.assertFalse(second.done())
            first.cancel()
            first.cancel()
            self.assertEqual((await sibling.request())["kind"], "candidate")
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await first
            await asyncio.wait_for(second, 3)
            await sub.close()
            self.assertNotIn(sub, client._subscriptions)
            self.assertTrue(frame["payload"]["ownerFrame"]["snapshot"]["sessions"])
        finally:
            release.set()
            await asyncio.gather(first, second, return_exceptions=True)
            client.client._send = original

    async def test_limits_reject_enlargement_and_non_integer_values(self):
        for values in ({"max_records": True}, {"heap_bytes": 64 * 1024 * 1024 + 1},
                       {"encoded_bytes": 0}):
            with self.subTest(values=values), self.assertRaises((ProtocolError, ValueError, TypeError)):
                FeedLimits(**values)

    async def test_actual_stdio_entrypoint_negotiates_and_closes_owned_child(self):
        with tempfile.TemporaryDirectory(prefix="vf-stdio-") as directory:
            root = Path(directory)
            config = root / "sources.toml"
            config.write_text('version=1\nhost="local"\n[sources.default]\ndomain="tmux"\nsocket="/unused"\n')
            config.chmod(0o600)
            launcher = root / "launch.py"
            launcher.write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
                "from publisher_fixture import factory\n"
                "from mesh_plus.cli import main\n"
                "raise SystemExit(main(publisher_factories={'tmux':factory('tmux')}))\n")
            channel = await subprocess_channel([sys.executable, "-I", str(launcher), "view-feed-bridge",
                                                "--source", "default", "--stdio", "--config", str(config)])
            client = await ViewFeedClient.connect(channel, host="local", source="default", profile=Profile("tmux"))
            try:
                sub = await client.subscribe()
                frame = await self.data(sub)
                self.assertEqual(frame["payload"]["kind"], "candidate")
                await sub.close()
            finally:
                await client.close()
            self.assertIsNotNone(channel.process.returncode)
            self.assertTrue(channel.closed)


if __name__ == "__main__":
    unittest.main()
