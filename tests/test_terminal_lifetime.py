import asyncio
import gc
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

from test_protocol import example
from test_reader import CachedClient

from mesh_plus.bridge import Bridge, Publication, _Connection
from mesh_plus.client import Client, DeliveryError
from mesh_plus.protocol import ProtocolError
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import IPCServer, LineChannel, _finish_owned_tasks, connect_ipc, finish_owned


class _Source:
    host = "fixture-host"
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot", "proof", "subscribe")

    def __init__(self):
        self.value = 0
        self.watchers = set()
        self.snapshot_started = asyncio.Event()
        self.snapshot_release = asyncio.Event()
        self.watch_started = asyncio.Event()
        self.watch_release = asyncio.Event()
        self.watch_release.set()

    def validate(self, payload):
        if type(payload) is not dict or type(payload.get("value")) is not int:
            raise ValueError("synthetic_payload")

    async def snapshot(self, parameters):
        self.snapshot_started.set()
        if parameters.get("block"):
            await self.snapshot_release.wait()
        return {"value": self.value}

    async def proof(self, parameters):
        return await self.snapshot(parameters)

    async def watch(self):
        self.watch_started.set()
        await self.watch_release.wait()
        queue = asyncio.Queue(maxsize=1)
        self.watchers.add(queue)
        try:
            yield Publication({"value": self.value}, "epoch_1", {"value": self.value})
            while True:
                yield await queue.get()
        finally:
            self.watchers.discard(queue)


class _ObserverBridgeAdapter:
    """Use the existing synthetic Observer response fixture through real IPC."""

    def __init__(self):
        self.cached = CachedClient("agent", "local")
        self.codec = self.cached.adapter
        self.host = "local"
        self.source = "default"
        self.profile = self.codec.profile
        self.capabilities = ("snapshot", "proof", "subscribe")
        self.watch_started = asyncio.Event()
        self.release_watch = asyncio.Event()

    def validate(self, payload):
        return self.codec.validate(payload)

    async def snapshot(self, parameters):
        return await self.cached.request("snapshot", parameters)

    async def proof(self, parameters):
        return await self.cached.request("proof", parameters)

    async def watch(self):
        self.watch_started.set()
        payload = await self.snapshot({})
        yield Publication(payload, self.codec.epoch(self.cached.frame), {"viewRevision": 1})
        await self.release_watch.wait()


class _BridgeLifetimeSource:
    host = "fixture-host"
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot", "proof", "subscribe")

    def __init__(self, *, block_snapshot=False):
        self.block_snapshot = block_snapshot
        self.snapshot_started = asyncio.Event()
        self.snapshot_release = asyncio.Event()
        self.snapshot_finished = asyncio.Event()
        self.snapshot_tasks = []

    def validate(self, payload):
        if type(payload) is not dict or type(payload.get("value")) is not int:
            raise ValueError("synthetic_payload")

    async def snapshot(self, _parameters):
        self.snapshot_tasks.append(weakref.ref(asyncio.current_task()))
        self.snapshot_started.set()
        try:
            if self.block_snapshot:
                await self.snapshot_release.wait()
            return {"value": 1}
        finally:
            self.snapshot_finished.set()

    async def proof(self, parameters):
        return await self.snapshot(parameters)

    async def watch(self):
        yield Publication({"value": 1}, "epoch_1", {"value": 1})
        await asyncio.Event().wait()


class _ScriptedBridgeChannel:
    def __init__(self, source, frames, *, fail_result=False, end_after_frames=False, block_close=False):
        self.source = source
        self.frames = list(frames)
        self.fail_result = fail_result
        self.end_after_frames = end_after_frames
        self.closed = asyncio.Event()
        self.close_started = asyncio.Event()
        self.close_release = asyncio.Event()
        if not block_close:
            self.close_release.set()
        self.maximum = 1 << 20
        self.sent_kinds = []
        self.send_task_refs = []
        self.failure_sent = False
        self.send_failure = ConnectionResetError("fixture_send_failure")

    async def receive(self):
        if self.frames:
            frame = self.frames.pop(0)
            if frame["kind"] == "cancel":
                await self.source.snapshot_started.wait()
            return frame, 0
        if self.end_after_frames:
            raise EOFError("script_finished")
        await self.closed.wait()
        raise EOFError("channel_closed")

    async def send(self, frame):
        self.sent_kinds.append(frame["kind"])
        if frame["kind"] == "hello":
            for incoming in self.frames:
                incoming["channelId"] = frame["channelId"]
        if frame["kind"] in {"result", "ended"}:
            self.send_task_refs.append(weakref.ref(asyncio.current_task()))
        if self.fail_result and frame["kind"] == "result":
            self.failure_sent = True
            raise self.send_failure
        return 0

    async def close(self):
        self.close_started.set()
        await self.close_release.wait()
        self.closed.set()


class _GatedBridgeIterator:
    def __init__(self):
        self.first = True
        self.next_cleanup_started = asyncio.Event()
        self.next_cleanup_release = asyncio.Event()
        self.close_started = asyncio.Event()
        self.close_release = asyncio.Event()
        self.closed = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.first:
            self.first = False
            return Publication({"value": 1}, "epoch_1", {})
        try:
            await asyncio.Event().wait()
        finally:
            self.next_cleanup_started.set()
            await self.next_cleanup_release.wait()

    async def aclose(self):
        self.close_started.set()
        await self.close_release.wait()
        self.closed.set()


class ClientTerminalLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "mesh.sock"
        self.source = _Source()
        self.server = await IPCServer(self.path, Bridge(self.source).serve).start()
        self.clients = []

    async def asyncTearDown(self):
        for client in tuple(self.clients):
            try:
                await client.close()
            except Exception:
                pass
        self.clients.clear()
        await self.server.close()
        self.directory.cleanup()
        self.assertFalse(self.source.watchers)

    async def connect_client(self):
        client = await Client.connect(await connect_ipc(self.path), host=self.source.host,
                                      source=self.source.source, profile=self.source.profile,
                                      codec=self.source.validate)
        self.clients.append(client)
        return client

    async def test_terminal_failure_wakes_callers_and_clears_only_client_registries(self):
        client = await self.connect_client()
        waiting_sub = await client.subscribe()
        await anext(waiting_sub)
        waiting_next = asyncio.create_task(anext(waiting_sub))
        await asyncio.sleep(0)

        waiting_request = asyncio.create_task(
            client.request(parameters={"block": True}, timeout_ms=30000))
        await asyncio.wait_for(self.source.snapshot_started.wait(), 1)
        self.assertTrue(client.requests)

        buffered_sub = await client.subscribe()
        await self._wait_for(lambda: not buffered_sub.queue.empty())
        control_size = 7
        buffered_sub.queue.put_nowait(({"kind": "control"}, control_size))
        client.buffered_bytes += control_size
        client.buffered_control_bytes += control_size
        self.assertGreater(client.buffered_bytes, 0)
        self.assertEqual(client.buffered_control_bytes, control_size)

        error = DeliveryError("fixture_channel_failure")
        retained_handles = set(client.guard.handles)
        client._fail(error)
        failure_template = client.failure
        self.assertIsNot(failure_template, error)
        self.assertEqual((failure_template.kind, failure_template.code, failure_template.message),
                         ("delivery", "fixture_channel_failure", "fixture_channel_failure"))

        self.assertFalse(client.requests)
        self.assertFalse(client.operations)
        self.assertFalse(client.subscriptions)
        self.assertEqual(set(client.guard.handles), retained_handles)
        self.assertEqual(client.inspect()["retainedHandles"], len(retained_handles))
        self.assertEqual(client.buffered_bytes, 0)
        self.assertEqual(client.buffered_control_bytes, 0)
        self.assertIs(waiting_sub.client, client)
        self.assertIs(buffered_sub.client, client)
        self.assertEqual(buffered_sub.queue.qsize(), 1)
        self.assertIs(buffered_sub.queue._queue[0], error)

        try:
            await waiting_next
        except DeliveryError as raised_next:
            self.assertIs(raised_next, error)
        else:
            self.fail("terminal iterator did not receive the original failure")
        try:
            await waiting_request
        except DeliveryError as raised_request:
            self.assertIs(raised_request, error)
        else:
            self.fail("terminal request did not receive the original failure")
        self.assertEqual(error.code, "fixture_channel_failure")
        client._fail(DeliveryError("later_failure"))
        self.assertIs(client.failure, failure_template)
        caller_traceback = error.__traceback__
        self.assertIsNotNone(caller_traceback)

        await client.close()
        self.assertIs(error.__traceback__, caller_traceback)
        await client.close()
        self.assertEqual(buffered_sub.queue.qsize(), 1)
        self.assertIs(buffered_sub.queue._queue[0], error)

    async def test_caller_held_subscription_keeps_client_until_released(self):
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            client = await self.connect_client()
            sub = await client.subscribe()
            await anext(sub)
            error = DeliveryError("channel_closed")
            client._fail(error)
            await client.close()
            self.assertIsNone(error.__traceback__)
            self.assertFalse(client.subscriptions)
            self.assertIs(sub.client, client)

            client_ref = weakref.ref(client)
            self.clients.remove(client)
            del client
            await asyncio.sleep(0)
            self.assertIsNotNone(client_ref())

            # The caller-owned iterator intentionally retains its Client.
            del sub
            del error
            await asyncio.sleep(0)
            self.assertIsNone(client_ref())
        finally:
            if was_enabled:
                gc.enable()

    async def test_terminal_client_does_not_close_an_unrelated_sibling(self):
        first = await self.connect_client()
        second = await self.connect_client()
        first._fail(DeliveryError("first_channel_failed"))
        await first.close()
        self.assertEqual(await second.request(), {"value": 0})
        self.assertIsNone(second.failure)
        await second.close()

    async def test_terminal_failure_keeps_only_a_safe_template_and_raises_fresh_errors(self):
        cases = (
            (DeliveryError("delivery_code", "delivery message"), DeliveryError,
             "delivery", "delivery_code", "delivery message"),
            (ProtocolError("protocol_code"), ProtocolError, "protocol", "protocol_code", "protocol_code"),
        )
        for original, error_type, kind, code, message in cases:
            client = await self.connect_client()
            client_ref = weakref.ref(client)
            client._fail(original)
            template = client.failure
            self.assertIsNot(template, original)
            self.assertEqual((template.kind, template.code, template.message), (kind, code, message))
            await client.close()

            with self.assertRaises(error_type) as first:
                await client.request()
            with self.assertRaises(error_type) as second:
                await client.request()
            self.assertIsNot(first.exception, original)
            self.assertIsNot(second.exception, original)
            self.assertIsNot(first.exception, second.exception)
            self.assertEqual(first.exception.code, code)
            self.assertEqual(first.exception.args, (message,))
            self.assertEqual(second.exception.code, code)
            self.assertEqual(second.exception.args, (message,))
            self.assertIsNone(original.__traceback__)

            self.clients.remove(client)
            del first, second, template, original, client
            await asyncio.sleep(0)
            self.assertIsNone(client_ref())

    async def test_mutated_error_metadata_uses_finite_fallback(self):
        class Marker:
            pass

        invalid = []
        bad_code = DeliveryError("unused")
        bad_code.code = Marker()
        invalid.append(bad_code)

        bad_args = DeliveryError("args_code", "args_message")
        marker = Marker()
        marker_ref = weakref.ref(marker)
        bad_args.args = (marker,)
        invalid.append(bad_args)
        del marker

        bad_protocol_code = ProtocolError("protocol_code")
        bad_protocol_code.code = Marker()
        invalid.append(bad_protocol_code)
        bad_protocol_args = ProtocolError("protocol_args")
        bad_protocol_args.args = ()
        invalid.append(bad_protocol_args)
        for error_type in (DeliveryError, ProtocolError):
            missing_code = error_type("deleted_code")
            del missing_code.code
            invalid.append(missing_code)

        for original in invalid:
            client = await self.connect_client()
            client._fail(original)
            self.assertEqual((client.failure.kind, client.failure.code, client.failure.message),
                             ("delivery", "channel_failed", "channel_failed"))
            with self.assertRaises(DeliveryError) as raised:
                await client.request()
            self.assertEqual(raised.exception.code, "channel_failed")
            await client.close()
        del invalid, original, bad_code, bad_args, bad_protocol_code, bad_protocol_args, client
        await asyncio.sleep(0)
        self.assertIsNone(marker_ref())

    async def test_terminal_templates_enforce_protocol_string_bounds(self):
        cases = (
            (DeliveryError("c" * 128, "m" * 4096),
             ("delivery", "c" * 128, "m" * 4096)),
            (DeliveryError("c" * 129, "bounded message"),
             ("delivery", "channel_failed", "channel_failed")),
            (DeliveryError("bounded_code", "m" * 4097),
             ("delivery", "channel_failed", "channel_failed")),
            (ProtocolError("p" * 129),
             ("delivery", "channel_failed", "channel_failed")),
        )
        for original, expected in cases:
            client = await self.connect_client()
            client._fail(original)
            self.assertEqual((client.failure.kind, client.failure.code, client.failure.message), expected)
            await client.close()

    async def test_unknown_failure_still_reaches_pending_caller_as_original(self):
        class OpaqueError(Exception):
            def __str__(self):
                raise AssertionError("unknown exception stringified")

            def __copy__(self):
                raise AssertionError("unknown exception copied")

        client = await self.connect_client()
        pending = asyncio.create_task(client.request(parameters={"block": True}, timeout_ms=30000))
        await asyncio.wait_for(self.source.snapshot_started.wait(), 1)
        error = OpaqueError("private opaque detail")
        client._fail(error)
        self.assertEqual((client.failure.kind, client.failure.code, client.failure.message),
                         ("delivery", "channel_failed", "channel_failed"))
        try:
            await pending
        except OpaqueError as raised:
            self.assertIs(raised, error)
        else:
            self.fail("pending request did not receive its original unknown error")

        with self.assertRaises(DeliveryError) as later:
            await client.request()
        self.assertEqual(later.exception.code, "channel_failed")
        self.assertNotIn("private opaque detail", later.exception.args)
        await client.close()
        self.source.snapshot_release.set()

    async def test_pending_request_error_owner_retires_without_cyclic_gc(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            client = await self.connect_client()
            client_ref = weakref.ref(client)
            pending = asyncio.create_task(client.request(parameters={"block": True}, timeout_ms=30000))
            await asyncio.wait_for(self.source.snapshot_started.wait(), 1)
            error = DeliveryError("pending_request_failed")
            client._fail(error)
            try:
                await pending
            except DeliveryError as raised:
                self.assertIs(raised, error)
            else:
                self.fail("pending request did not receive its original error")
            self.assertIsNot(client.failure, error)
            traceback = error.__traceback__
            self.assertIsNotNone(traceback)
            await client.close()
            self.assertIs(error.__traceback__, traceback)
            self.assertIsNotNone(client_ref())

            self.source.snapshot_release.set()
            self.clients.remove(client)
            del traceback, error, pending, client
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(client_ref())
        finally:
            if enabled:
                gc.enable()

    async def test_failed_subscribe_admission_retires_local_handle_without_cyclic_gc(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            self.source.watch_release.clear()
            client = await self.connect_client()
            client_ref = weakref.ref(client)
            pending = asyncio.create_task(client.subscribe())
            await asyncio.wait_for(self.source.watch_started.wait(), 1)
            self.assertEqual(len(client.subscriptions), 1)
            sub = next(iter(client.subscriptions.values()))
            self.assertFalse(sub.ready.done())
            sub_ref = weakref.ref(sub)

            error = DeliveryError("subscribe_admission_failed")
            client._fail(error)
            try:
                await pending
            except DeliveryError as raised:
                self.assertIs(raised, error)
            else:
                self.fail("failed subscribe did not preserve its original error")
            self.assertIsNot(client.failure, error)
            traceback = error.__traceback__
            self.assertIsNotNone(traceback)
            await client.close()
            self.assertIs(error.__traceback__, traceback)
            self.assertIsNotNone(client_ref())
            self.assertIsNotNone(sub_ref())

            self.source.watch_release.set()
            self.clients.remove(client)
            del traceback, error, sub, pending, client
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(sub_ref())
            self.assertIsNone(client_ref())
        finally:
            self.source.watch_release.set()
            if enabled:
                gc.enable()

    async def test_terminal_iterator_error_retires_after_caller_releases_it(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            client = await self.connect_client()
            client_ref = weakref.ref(client)
            sub = await client.subscribe()
            sub_ref = weakref.ref(sub)
            await anext(sub)
            error = DeliveryError("iterator_terminal_failure")
            client._fail(error)
            try:
                await anext(sub)
            except DeliveryError as raised:
                self.assertIs(raised, error)
            else:
                self.fail("terminal iterator did not preserve its original error")
            traceback = error.__traceback__
            self.assertIsNotNone(traceback)
            self.assertEqual(sub.queue.qsize(), 0)
            await client.close()
            self.assertIs(error.__traceback__, traceback)
            self.assertIsNotNone(client_ref())
            self.assertIsNotNone(sub_ref())

            self.clients.remove(client)
            del traceback, error, sub, client
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(sub_ref())
            self.assertIsNone(client_ref())
        finally:
            if enabled:
                gc.enable()

    async def _wait_for(self, predicate):
        async def spin():
            while not predicate():
                await asyncio.sleep(0)
        await asyncio.wait_for(spin(), 1)


class OwnedTaskRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def _wait_for(self, predicate):
        async def spin():
            while not predicate():
                await asyncio.sleep(0)
        await asyncio.wait_for(spin(), 1)

    async def test_repeated_caller_cancel_joins_owned_child_and_retires_traceback(self):
        class Marker:
            pass

        was_enabled = gc.isenabled()
        gc.disable()
        marker = Marker()
        marker_ref = weakref.ref(marker)
        entered = asyncio.Event()
        cleanup_entered = asyncio.Event()
        finish_cleanup = asyncio.Event()

        async def child(held):
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                held.touched = True
                cleanup_entered.set()
                await finish_cleanup.wait()

        async def fail():
            raise ValueError("owned_child_failure")

        try:
            task = asyncio.create_task(child(marker))
            await entered.wait()
            task.cancel()
            await self._wait_for(cleanup_entered.is_set)
            joined = asyncio.create_task(_finish_owned_tasks((task,)))
            await asyncio.sleep(0)
            for _ in range(3):
                joined.cancel()
                await asyncio.sleep(0)
                self.assertFalse(joined.done())
            finish_cleanup.set()
            with self.assertRaises(asyncio.CancelledError):
                await joined
            self.assertTrue(task.done())
            self.assertTrue(task.cancelled())

            failed = asyncio.create_task(fail())
            result = await _finish_owned_tasks((failed,))
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], ValueError)
            self.assertEqual(str(result[0]), "owned_child_failure")

            del task, joined, failed, result, marker
            self.assertIsNone(marker_ref())
        finally:
            finish_cleanup.set()
            if was_enabled:
                gc.enable()

    async def test_finish_owned_preserves_success_and_inner_error_precedence(self):
        class Marker:
            pass

        was_enabled = gc.isenabled()
        gc.disable()
        try:
            value = Marker()
            task = asyncio.create_task(asyncio.sleep(0, result=value))
            self.assertIs(await finish_owned(task), value)

            release = asyncio.Event()
            returned = Marker()
            returned_ref = weakref.ref(returned)

            async def return_after_release(held):
                await release.wait()
                return held

            child = asyncio.create_task(return_after_release(returned))
            waiter = asyncio.create_task(finish_owned(child))
            await asyncio.sleep(0)
            waiter.cancel()
            await asyncio.sleep(0)
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            del child, waiter, returned
            self.assertIsNone(returned_ref())

            fail_release = asyncio.Event()
            original = ValueError("inner_owned_failure")

            async def fail_after_release(error=original):
                await fail_release.wait()
                raise error

            child = asyncio.create_task(fail_after_release())
            waiter = asyncio.create_task(finish_owned(child))
            await asyncio.sleep(0)
            waiter.cancel()
            await asyncio.sleep(0)
            fail_release.set()
            with self.assertRaises(ValueError) as raised:
                await waiter
            self.assertIs(raised.exception, original)
            self.assertEqual(str(raised.exception), "inner_owned_failure")
            del child, waiter, original, value, task
        finally:
            if was_enabled:
                gc.enable()

    async def test_finish_owned_rethrows_same_failure_without_retaining_task_cycle(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            async def fail():
                raise ValueError("owned_task_failure")

            child = asyncio.create_task(fail())
            child_ref = weakref.ref(child)
            await asyncio.sleep(0)
            original = child.exception()
            try:
                await finish_owned(child)
            except ValueError as failure:
                caught = failure
                self.assertIs(caught, original)
                self.assertEqual(str(caught), "owned_task_failure")
            else:
                self.fail("finish_owned did not propagate the child failure")

            del original, child
            await asyncio.sleep(0)
            self.assertIsNone(child_ref())
            del caught
        finally:
            if enabled:
                gc.enable()

    async def test_reader_bridge_and_client_retire_after_watch_cancellation(self):
        was_enabled = gc.isenabled()
        gc.disable()
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "mesh.sock"
        adapter = _ObserverBridgeAdapter()
        bridge = Bridge(adapter)
        bridge_ref = weakref.ref(bridge)

        async def serve(channel):
            current = bridge_ref()
            if current is not None:
                await current.serve(channel)

        server = await IPCServer(path, serve).start()
        client_refs = []

        async def connect(current_adapter=adapter):
            client = await Client.connect(await connect_ipc(path), host=current_adapter.host,
                                          source=current_adapter.source, profile=current_adapter.profile,
                                          codec=current_adapter.codec.validate)
            client_refs.append(weakref.ref(client))
            return client

        endpoint = Endpoint("local", True, None, connect)
        reader = Reader("agent", [endpoint], local_host="local")
        reader_ref = weakref.ref(reader)
        stream = reader.watch(request_id="a" * 32)
        try:
            try:
                baseline = await anext(stream)
                self.assertEqual(baseline["mesh"]["status"], "pending")
                try:
                    await asyncio.wait_for(adapter.watch_started.wait(), 2)
                except TimeoutError:
                    self.fail(f"Reader did not enter the source watch: {reader.inspect()!r}; clients={len(client_refs)}")
                await asyncio.wait_for(self._reader_connected(reader), 2)

                # Cancelling the public watch retires Reader's owned setup,
                # subscription-read, and Client reader tasks before the IPC
                # server itself is closed.
                await stream.aclose()
                self.assertEqual(reader.inspect()["activeConnections"], 0)
                self.assertEqual(reader.inspect()["connectionsOpened"],
                                 reader.inspect()["connectionsClosed"])
                await server.close()
                self.assertFalse(server.tasks)
            finally:
                adapter.release_watch.set()
                if not server.closed:
                    await server.close()
                await stream.aclose()
                await asyncio.sleep(0)
                del stream, reader, endpoint, connect, bridge, adapter
                await asyncio.sleep(0)
                directory.cleanup()

            self.assertIsNone(reader_ref())
            self.assertIsNone(bridge_ref())
            self.assertTrue(client_refs)
            self.assertTrue(all(reference() is None for reference in client_refs))
        finally:
            if was_enabled:
                gc.enable()

    async def _reader_connected(self, reader):
        while reader.inspect()["connectionsOpened"] == 0:
            await asyncio.sleep(0)


class BridgeChildTaskRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def _serve_recording_connection(self, bridge, channel):
        connection_refs = []
        original_close = _Connection.close

        async def capture_connection(connection, *, suppress_errors=False):
            connection_refs.append(weakref.ref(connection))
            await original_close(connection, suppress_errors=suppress_errors)

        caught_eof = False
        with patch.object(_Connection, "close", capture_connection):
            try:
                await bridge.serve(channel)
            except EOFError:
                caught_eof = True
            else:
                self.fail("scripted bridge input did not terminate")
        return caught_eof, tuple(connection_refs)

    @staticmethod
    def _frames(*, cancel=False, block_snapshot=False):
        hello = example("client-hello")
        request = example("client-request")
        if block_snapshot:
            request["parameters"] = {"block": True}
        frames = [hello, request]
        if cancel:
            cancellation = example("client-cancel")
            cancellation.update(sequence=3, handleId=request["requestId"], handleType="request")
            frames.append(cancellation)
        return frames

    async def test_failed_emit_releases_its_owned_send_task_without_clearing_error(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            source = _BridgeLifetimeSource()
            channel = _ScriptedBridgeChannel(source, self._frames(), fail_result=True)
            bridge = Bridge(source)
            bridge_ref = weakref.ref(bridge)
            channel_ref = weakref.ref(channel)

            caught_eof, connection_refs = await self._serve_recording_connection(bridge, channel)
            self.assertTrue(caught_eof)
            self.assertTrue(channel.failure_sent)
            self.assertIn("result", channel.sent_kinds)
            self.assertIsNotNone(bridge_ref())
            self.assertEqual(len(connection_refs), 1)
            self.assertIsNotNone(connection_refs[0]())

            send_error = channel.send_failure
            self.assertIs(type(send_error), ConnectionResetError)
            self.assertIsNotNone(send_error.__traceback__)
            send_tasks = tuple(channel.send_task_refs)
            self.assertEqual(len(send_tasks), 1)

            channel.send_failure = None
            del send_error, bridge, channel, source
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(bridge_ref())
            self.assertIsNone(channel_ref())
            self.assertIsNone(connection_refs[0]())
            self.assertTrue(all(reference() is None for reference in send_tasks))
        finally:
            if enabled:
                gc.enable()

    async def test_cancelled_request_and_connection_close_retire_owned_tasks(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            source = _BridgeLifetimeSource(block_snapshot=True)
            channel = _ScriptedBridgeChannel(
                source, self._frames(cancel=True, block_snapshot=True), end_after_frames=True
            )
            bridge = Bridge(source)
            bridge_ref = weakref.ref(bridge)
            channel_ref = weakref.ref(channel)

            caught_eof, connection_refs = await self._serve_recording_connection(bridge, channel)
            self.assertTrue(caught_eof)
            self.assertTrue(source.snapshot_started.is_set())
            self.assertTrue(source.snapshot_finished.is_set())
            self.assertIn("ended", channel.sent_kinds)
            self.assertIsNotNone(bridge_ref())
            self.assertEqual(len(connection_refs), 1)
            self.assertIsNone(connection_refs[0]())

            request_tasks = tuple(source.snapshot_tasks)
            send_tasks = tuple(channel.send_task_refs)
            self.assertEqual(len(request_tasks), 1)
            self.assertEqual(len(send_tasks), 1)

            del bridge, channel, source
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(bridge_ref())
            self.assertIsNone(channel_ref())
            self.assertIsNone(connection_refs[0]())
            self.assertTrue(all(reference() is None for reference in request_tasks))
            self.assertTrue(all(reference() is None for reference in send_tasks))
        finally:
            if enabled:
                gc.enable()

    async def test_repeated_close_cancellation_still_closes_channel_after_child_join(self):
        source = _BridgeLifetimeSource()
        channel = _ScriptedBridgeChannel(source, [], block_close=True)
        connection = _Connection(channel, source, .05, .1)
        child_started = asyncio.Event()
        child_finally = asyncio.Event()
        child_release = asyncio.Event()

        async def owned_child():
            child_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                child_finally.set()
                await child_release.wait()

        child = asyncio.create_task(owned_child())
        connection.tasks["owned"] = child
        await child_started.wait()
        closing = asyncio.create_task(connection.close())
        await child_finally.wait()

        closing.cancel()
        closing.cancel()
        child_release.set()
        await channel.close_started.wait()
        self.assertFalse(closing.done())
        closing.cancel()
        channel.close_release.set()
        try:
            await closing
        except asyncio.CancelledError:
            pass
        else:
            self.fail("caller cancellation was not reported after close")

        self.assertTrue(channel.closed.is_set())
        self.assertEqual(connection.tasks, {})
        self.assertTrue(child.done())

    async def test_channel_close_error_wins_over_repeated_caller_cancellation(self):
        source = _BridgeLifetimeSource()
        channel = _ScriptedBridgeChannel(source, [], block_close=True)
        failure = ConnectionResetError("fixture_close_failure")

        async def failing_close():
            channel.close_started.set()
            await channel.close_release.wait()
            raise failure

        channel.close = failing_close
        connection = _Connection(channel, source, .05, .1)
        closing = asyncio.create_task(connection.close())
        await channel.close_started.wait()
        closing.cancel()
        closing.cancel()
        channel.close_release.set()
        try:
            await closing
        except ConnectionResetError as error:
            self.assertIs(error, failure)
        else:
            self.fail("child close failure was replaced by caller cancellation")

    async def test_cleanup_failure_does_not_replace_bridge_run_failure(self):
        source = _BridgeLifetimeSource()
        channel = _ScriptedBridgeChannel(source, self._frames(), end_after_frames=True)
        cleanup_failure = ConnectionResetError("fixture_cleanup_failure")

        async def failing_close():
            channel.close_started.set()
            raise cleanup_failure

        channel.close = failing_close
        bridge = Bridge(source)
        caught_eof, _connection_refs = await self._serve_recording_connection(bridge, channel)
        self.assertTrue(caught_eof)

    async def test_subscription_aclose_runs_after_repeated_cancel_during_producer_join(self):
        from mesh_plus.protocol import Lifecycle, encode

        source = _BridgeLifetimeSource()
        iterator = _GatedBridgeIterator()
        source.watch = lambda: iterator
        channel = _ScriptedBridgeChannel(source, [])
        connection = _Connection(channel, source, .05, .1)
        client_hello = example("client-hello")
        server_hello = example("server-hello")
        connection.guard = Lifecycle(client_hello, source.host)
        connection.guard.received(server_hello, len(encode(server_hello)))
        subscribe = example("client-subscribe")
        subscribe.update(channelId=server_hello["channelId"], sequence=2, subscriptionId="gated")
        connection.guard.sent(subscribe, 0)

        subscription = asyncio.create_task(connection.subscription(subscribe))
        while "data" not in channel.sent_kinds:
            await asyncio.sleep(0)
        subscription.cancel()
        await iterator.next_cleanup_started.wait()
        subscription.cancel()
        iterator.next_cleanup_release.set()
        await iterator.close_started.wait()
        self.assertFalse(subscription.done())
        subscription.cancel()
        iterator.close_release.set()
        try:
            await subscription
        except asyncio.CancelledError:
            pass
        else:
            self.fail("subscription cancellation was not reported after iterator close")

        self.assertTrue(iterator.closed.is_set())
        self.assertNotIn("gated", connection.wakes)


class TransportReadTaskRetirementTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_receive_releases_owned_read_task_after_error_release(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            reader = asyncio.StreamReader()
            reader.feed_eof()
            channel = LineChannel(reader, None, "server")
            channel_ref = weakref.ref(channel)

            try:
                await channel.receive()
            except EOFError as error:
                caught = error
            else:
                self.fail("EOF input did not terminate the read")

            self.assertEqual(str(caught), "channel_closed")
            self.assertIsNotNone(caught.__traceback__)
            self.assertIsNone(channel.read_job)
            self.assertIsNotNone(channel_ref())

            del caught, channel, reader
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertIsNone(channel_ref())
        finally:
            if enabled:
                gc.enable()
