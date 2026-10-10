import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_protocol import example

from mesh_plus.bridge import Bridge, Publication, _Connection
from mesh_plus.client import Client, DeliveryError
from mesh_plus.protocol import MAX_HANDLES, ProtocolError, check
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

    async def test_rotation_admission_preserves_pending_work_and_subscription(self):
        sub = await self.client.subscribe()
        await anext(sub)
        pending = asyncio.create_task(self.client.request(parameters={"delay": .05}))
        while len(self.client.guard.handles) < 2:
            await asyncio.sleep(.001)
        with patch("mesh_plus.client.ROTATION_HANDLES", 2):
            self.assertTrue(self.client.rotation_due())
            sequence = self.client.guard.client_sequence
            for admission in (self.client.request(), self.client.subscribe()):
                with self.assertRaises(DeliveryError) as error:
                    await admission
                self.assertEqual(error.exception.code, "channel_rotation_required")
            self.assertEqual(self.client.guard.client_sequence, sequence)
            self.assertEqual((await pending)["value"], 0)
            await self.source.publish(1)
            self.assertEqual((await anext(sub))["payload"]["value"], 1)
            await sub.close()
        self.assertFalse(self.client.requests)
        self.assertFalse(self.client.operations)
        self.assertEqual(self.client.inspect()["operations"]["rotationRejections"], 2)

    async def test_rotation_check_is_serialized_with_queued_admissions(self):
        await self.client.send_lock.acquire()
        tasks = [asyncio.create_task(self.client.request()) for _ in range(3)]
        try:
            await asyncio.sleep(.01)
            with patch("mesh_plus.client.ROTATION_HANDLES", 2):
                self.client.send_lock.release()
                results = await asyncio.gather(*tasks, return_exceptions=True)
            self.assertEqual(sum(isinstance(result, dict) for result in results), 2)
            rejected = [result for result in results if isinstance(result, DeliveryError)]
            self.assertEqual([result.code for result in rejected], ["channel_rotation_required"])
            self.assertEqual(len(self.client.guard.handles), 2)
        finally:
            if self.client.send_lock.locked():
                self.client.send_lock.release()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_actual_production_handle_budget_with_a_live_subscription(self):
        from mesh_plus.client import ROTATION_HANDLES

        sub = await self.client.subscribe()
        await anext(sub)
        remaining = ROTATION_HANDLES - 1
        while remaining:
            count = min(8, remaining)
            await asyncio.gather(*(self.client.request() for _ in range(count)))
            remaining -= count
        self.assertEqual(len(self.client.guard.handles), MAX_HANDLES - 16)
        with self.assertRaises(DeliveryError) as error:
            await self.client.request()
        self.assertEqual(error.exception.code, "channel_rotation_required")
        self.assertFalse(self.client.failure)
        await self.source.publish(2)
        while True:
            pushed = await anext(sub)
            if pushed["kind"] == "data":
                break
        self.assertEqual(pushed["payload"]["value"], 2)
        await sub.close()

    async def test_operation_and_frame_metrics_include_lf_and_retain_queue_peaks(self):
        result = await self.client.request()
        sub = await self.client.subscribe()
        await anext(sub)
        await sub.close()
        metrics = self.client.inspect()
        self.assertEqual(result["value"], 0)
        self.assertEqual(metrics["operations"]["snapshotRequests"], 1)
        channel = metrics["channel"]
        self.assertEqual(metrics["operations"]["snapshotResultBytes"],
                         channel["byKind"]["received"]["result"]["bytes"])
        for direction in ("received", "sent"):
            for key, suffix in (("frames", "Frames"), ("bytes", "Bytes")):
                self.assertEqual(sum(count[key] for count in channel["byKind"][direction].values()),
                                 channel[direction + suffix])
        self.assertGreater(metrics["peakBufferedBytes"], 0)
        self.assertGreater(metrics["peakQueueFrames"], 0)
        self.assertEqual(metrics["bufferedBytes"], 0)
        channel["byKind"]["sent"]["request"]["bytes"] = -1
        self.assertGreater(self.client.inspect()["channel"]["byKind"]["sent"]["request"]["bytes"], 0)

    async def test_rejected_result_bytes_are_explicitly_unprocessed(self):
        def reject(_payload):
            raise ProtocolError("fixture_rejection")
        self.client.codec = reject
        try:
            await self.client.request()
        except ProtocolError as error:
            self.assertEqual(error.code, "fixture_rejection")
        else:
            self.fail("Rejected payload reached its caller")
        # Python 3.11 assertRaises clears traceback frames; do not clear the
        # shared failure's still-running reader coroutine during cleanup.
        await self.client.reader_task
        metrics = self.client.inspect()
        self.assertGreater(metrics["operations"]["unprocessedResultBytes"], 0)
        self.assertEqual(metrics["operations"]["snapshotResultBytes"], 0)
        self.assertEqual(metrics["operations"]["unprocessedResultBytes"],
                         metrics["channel"]["byKind"]["received"]["result"]["bytes"])

    async def test_request_terminal_wakes_caller_without_closing_siblings(self):
        original = _Connection.request

        async def end_request(connection, frame):
            if frame["parameters"].get("end"):
                await connection.emit("ended", handleId=frame["requestId"], handleType="request",
                                      reason="deadline", cursor=None)
            else:
                await original(connection, frame)

        with patch.object(_Connection, "request", end_request):
            with self.assertRaises(DeliveryError) as raised:
                await asyncio.wait_for(self.client.request(parameters={"end": True}), .5)
            self.assertEqual(raised.exception.code, "deadline")
            self.assertFalse(self.client.requests)
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
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(sub), .2)
        self.assertEqual((await self.client.request())["value"], 0)
        await sub.close()

    async def test_failed_subscription_stays_exhausted_after_error(self):
        fail = asyncio.Event()

        async def failing():
            yield Publication({"value": 17}, "epoch_1", {})
            await fail.wait()
            raise ValueError("private publisher detail")

        self.source.watch = failing
        sub = await self.client.subscribe()
        self.assertEqual((await anext(sub))["payload"]["value"], 17)
        fail.set()
        with self.assertRaises(DeliveryError) as raised:
            await asyncio.wait_for(anext(sub), .5)
        self.assertEqual(raised.exception.code, "gap")
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(sub), .2)
        self.assertEqual((await self.client.request())["value"], 0)
        await sub.close()
        self.assertNotIn(sub.key, self.client.subscriptions)
        self.assertEqual(self.client.buffered_bytes, 0)

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
