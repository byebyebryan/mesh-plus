import asyncio
import tempfile
import unittest
from pathlib import Path

from test_protocol import example

from mesh_plus.bridge import Bridge, Publication
from mesh_plus.client import Client, DeliveryError
from mesh_plus.protocol import ProtocolError, check
from mesh_plus.transport import IPCServer, connect_ipc


class Source:
    host = "fixture-host"
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot", "subscribe")

    def __init__(self):
        self.value = 0
        self.watchers = set()

    def validate(self, value):
        check(isinstance(value, dict) and type(value.get("value")) is int, "synthetic_payload")

    async def snapshot(self, parameters):
        if parameters.get("delay"):
            await asyncio.sleep(parameters["delay"])
        if parameters.get("fail"):
            raise ValueError("private source detail")
        return {"value": self.value, "padding": "x" * parameters.get("bytes", 0)}

    async def watch(self):
        queue = asyncio.Queue(maxsize=1)
        self.watchers.add(queue)
        try:
            yield Publication({"value": self.value}, "epoch_1", {"value": self.value})
            while True:
                yield await queue.get()
        finally:
            self.watchers.discard(queue)

    async def publish(self, value):
        self.value = value
        for queue in self.watchers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(Publication({"value": value}, "epoch_1", {"value": value}))
        await asyncio.sleep(.01)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "mesh.sock"
        self.source = Source()
        self.server = await IPCServer(self.path, Bridge(self.source).serve).start()
        self.client = await Client.connect(await connect_ipc(self.path), host=self.source.host,
                                           source=self.source.source, profile=self.source.profile,
                                           codec=self.source.validate)

    async def asyncTearDown(self):
        await self.client.close()
        await self.server.close()
        self.directory.cleanup()
        self.assertFalse(self.source.watchers)

    async def test_requests_interleave_push_and_independent_cancel(self):
        one, two = await self.client.subscribe(), await self.client.subscribe()
        self.assertEqual((await anext(one))["payload"]["value"], 0)
        self.assertEqual((await anext(two))["payload"]["value"], 0)
        delayed = asyncio.create_task(self.client.request(parameters={"delay": .1}))
        await self.source.publish(1)
        self.assertEqual((await asyncio.wait_for(anext(one), 1))["payload"]["value"], 1)
        await one.close()
        await self.source.publish(2)
        self.assertEqual((await anext(two))["payload"]["value"], 1)
        self.assertEqual((await asyncio.wait_for(anext(two), 1))["payload"]["value"], 2)
        self.assertEqual((await delayed)["value"], 2)
        self.assertEqual((await self.client.request())["value"], 2)
        await two.close()

    async def test_terminal_arriving_while_credit_waits_for_send_lock(self):
        finish = asyncio.Event()
        async def finite():
            yield Publication({"value": 7}, "epoch_1", {"value": 7})
            await finish.wait()
        self.source.watch = finite
        sub = await self.client.subscribe()
        async def wait_for(predicate):
            while not predicate():
                await asyncio.sleep(.001)
        await asyncio.wait_for(wait_for(lambda: not sub.queue.empty()), 1)
        await self.client.send_lock.acquire()
        pending = asyncio.create_task(anext(sub))
        try:
            await asyncio.sleep(.01)
            self.assertFalse(pending.done())
            finish.set()
            await asyncio.wait_for(wait_for(lambda: self.client.guard.handles[sub.key]["phase"] == "done"), 1)
            sequence = self.client.guard.client_sequence
        finally:
            self.client.send_lock.release()
        self.assertEqual((await asyncio.wait_for(pending, 1))["payload"]["value"], 7)
        self.assertEqual(self.client.guard.client_sequence, sequence)
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_source_failure_is_typed_and_channel_survives(self):
        with self.assertRaises(DeliveryError) as raised:
            await self.client.request(parameters={"fail": True})
        self.assertEqual(raised.exception.code, "source_unavailable")
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_setup_rejections_are_nonce_bound_and_typed(self):
        for updates, code in [({"profile": "unsupported.v1"}, "unsupported_contract"),
                              ({"required": ("snapshot", "proof")}, "unsupported_capability"),
                              ({"host": "wrong-host"}, "scope_mismatch")]:
            parameters = {"host": self.source.host, "source": self.source.source,
                          "profile": self.source.profile, "codec": self.source.validate, **updates}
            channel = await connect_ipc(self.path)
            with self.subTest(code=code), self.assertRaises(DeliveryError) as raised:
                await Client.connect(channel, **parameters)
            self.assertEqual(raised.exception.code, code)
            self.assertTrue(channel.closed)
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_deadline_cancels_only_its_handle(self):
        with self.assertRaises(TimeoutError):
            await self.client.request(parameters={"delay": .5}, timeout_ms=30)
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_request_queue_time_counts_and_never_dispatches_expired_work(self):
        await self.client.send_lock.acquire()
        before = self.client.guard.client_sequence
        try:
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(self.client.request(timeout_ms=20), .2)
            self.assertEqual(self.client.guard.client_sequence, before)
            self.assertFalse(self.client.requests)
        finally:
            self.client.send_lock.release()
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_large_frame(self):
        result = await self.client.request(parameters={"bytes": 8 * 1024 * 1024}, timeout_ms=10000)
        self.assertEqual(len(result["padding"]), 8 * 1024 * 1024)

    async def test_close_wakes_pending_request_and_reader(self):
        sub = await self.client.subscribe()
        pending = asyncio.create_task(self.client.request(parameters={"delay": 1}))
        await asyncio.sleep(.02)
        await self.client.close()
        with self.assertRaises(DeliveryError):
            await asyncio.wait_for(pending, .2)
        with self.assertRaises(DeliveryError):
            await anext(sub)
        self.assertEqual(self.client.buffered_bytes, 0)

    async def test_cancel_crossing_completed_result_does_not_close_siblings(self):
        channel = await connect_ipc(self.path)
        try:
            await channel.send(example("client-hello"))
            hello, _ = await channel.receive()
            request = example("client-request")
            request.update(channelId=hello["channelId"], requestId="first", parameters={})
            await channel.send(request)
            # Allow the server to complete, but do not consume its terminal result.
            await asyncio.sleep(.05)
            cancel = example("client-cancel")
            cancel.update(channelId=hello["channelId"], sequence=3, handleId="first", handleType="request")
            await channel.send(cancel)
            request.update(sequence=4, requestId="second")
            await channel.send(request)
            first, _ = await asyncio.wait_for(channel.receive(), 1)
            second, _ = await asyncio.wait_for(channel.receive(), 1)
            self.assertEqual(first["requestId"], "first")
            self.assertEqual(second["requestId"], "second")
            self.assertEqual(second["outcome"], "ok")
        finally:
            await channel.close()

    async def test_unsupported_proof_does_not_poison_sequence(self):
        with self.assertRaisesRegex(ProtocolError, "unsupported_operation"):
            await self.client.request("proof")
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_terminal_subscription_drains_queued_data_without_new_credit(self):
        async def finite():
            yield Publication({"value": 17}, "epoch_1", {})
        self.source.watch = finite
        sub = await self.client.subscribe()
        await asyncio.wait_for(sub.ended.wait(), 1)
        self.assertEqual((await anext(sub))["payload"]["value"], 17)
        with self.assertRaises(StopAsyncIteration):
            await anext(sub)
        self.assertEqual((await self.client.request())["value"], 0)
        await sub.close()

    async def test_independent_subscription_close_wakes_waiting_consumer(self):
        sub = await self.client.subscribe()
        await anext(sub)
        pending = asyncio.create_task(anext(sub))
        await asyncio.sleep(.01)
        await sub.close()
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(pending, .2)
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_idle_heartbeat_and_credit_starvation_are_independent_of_siblings(self):
        from mesh_plus.client import Subscription
        path = Path(self.directory.name) / "timing.sock"
        server = await IPCServer(path, Bridge(self.source, heartbeat_interval=.02, credit_timeout=.08).serve).start()
        client = await Client.connect(await connect_ipc(path), host=self.source.host, source=self.source.source,
                                      profile=self.source.profile, codec=self.source.validate)
        try:
            normal = await client.subscribe()
            await anext(normal)
            heartbeat = await asyncio.wait_for(anext(normal), .3)
            self.assertEqual(heartbeat["control"], "heartbeat")
            self.assertEqual(heartbeat["payload"], {})
            slow = Subscription(client, "slow")
            client.subscriptions["slow"] = slow
            await client._send("subscribe", subscriptionId="slow", start={"mode": "baseline", "cursor": None},
                               credit={"frames": 0, "bytes": 0})
            await asyncio.wait_for(slow.ready, .3)
            await asyncio.wait_for(slow.ended.wait(), .3)
            self.assertEqual(client.guard.handles["slow"]["phase"], "done")
            self.assertEqual((await client.request())["value"], 0)
            await normal.close()
            await slow.close()
            self.assertEqual(client.buffered_control_bytes, 0)
        finally:
            await client.close()
            await server.close()

    async def test_credit_crossing_ended_does_not_close_siblings(self):
        async def finite():
            yield Publication({"value": 17}, "epoch_1", {})
        self.source.watch = finite
        channel = await connect_ipc(self.path)
        try:
            await channel.send(example("client-hello"))
            hello, _ = await channel.receive()
            subscribed = example("client-subscribe")
            subscribed.update(channelId=hello["channelId"], sequence=2, subscriptionId="finite",
                              start={"mode": "baseline", "cursor": None}, credit={"frames": 1, "bytes": 10000})
            await channel.send(subscribed)
            barrier, _ = await channel.receive()
            data, size = await channel.receive()
            self.assertEqual(barrier["kind"], "subscribed")
            self.assertEqual(data["kind"], "data")
            await asyncio.sleep(.05)
            credit = example("client-credit")
            credit.update(channelId=hello["channelId"], sequence=3, subscriptionId="finite",
                          credit={"frames": 2, "bytes": 10000 + size})
            await channel.send(credit)
            request = example("client-request")
            request.update(channelId=hello["channelId"], sequence=4, requestId="sibling", parameters={})
            await channel.send(request)
            ended, _ = await asyncio.wait_for(channel.receive(), 1)
            result, _ = await asyncio.wait_for(channel.receive(), 1)
            self.assertEqual(ended["kind"], "ended")
            self.assertEqual(result["requestId"], "sibling")
        finally:
            await channel.close()

    async def test_zero_credit_coalesces_then_resyncs(self):
        # Explicitly start without credit to exercise server buffering independent of SDK auto-credit.
        key = "slow"
        from mesh_plus.client import Subscription
        sub = Subscription(self.client, key)
        self.client.subscriptions[key] = sub
        await self.client._send("subscribe", subscriptionId=key, start={"mode": "baseline", "cursor": None},
                                credit={"frames": 0, "bytes": 0})
        await asyncio.wait_for(sub.ready, 1)
        for value in range(1, 5):
            await self.source.publish(value)
        await self.client._send("credit", subscriptionId=key, credit={"frames": 1, "bytes": 10000})
        data = None
        while data is None:
            frame = await asyncio.wait_for(anext(sub), 1)
            if frame["kind"] == "data":
                data = frame
        self.assertEqual(data["deliveryKind"], "resync")
        self.assertEqual(data["payload"]["value"], 4)
        await sub.close()
