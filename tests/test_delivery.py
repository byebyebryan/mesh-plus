import asyncio
import tempfile
import unittest
from pathlib import Path

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

    async def test_source_failure_is_typed_and_channel_survives(self):
        with self.assertRaises(DeliveryError) as raised:
            await self.client.request(parameters={"fail": True})
        self.assertEqual(raised.exception.code, "source_unavailable")
        self.assertNotIn("private", str(raised.exception))
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_deadline_cancels_only_its_handle(self):
        with self.assertRaises(TimeoutError):
            await self.client.request(parameters={"delay": .5}, timeout_ms=30)
        self.assertEqual((await self.client.request())["value"], 0)

    async def test_large_frame(self):
        result = await self.client.request(parameters={"bytes": 1024 * 1024}, timeout_ms=5000)
        self.assertEqual(len(result["padding"]), 1024 * 1024)

    async def test_unsupported_proof_does_not_poison_sequence(self):
        with self.assertRaisesRegex(ProtocolError, "unsupported_operation"):
            await self.client.request("proof")
        self.assertEqual((await self.client.request())["value"], 0)

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
