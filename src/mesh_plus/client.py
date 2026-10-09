"""Concurrent cached reads and bounded state subscriptions on one channel."""

import asyncio
import contextlib
import secrets

from .protocol import MAX_MESSAGE, PROTOCOL, Lifecycle, ProtocolError, check
from .transport import boottime_ms


class DeliveryError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        super().__init__(message or code)


class Subscription:
    def __init__(self, client, key):
        self.client, self.key = client, key
        self.queue = asyncio.Queue(maxsize=34)
        self.ready = asyncio.get_running_loop().create_future()
        self.ended = asyncio.Event()
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        item = await self.queue.get()
        if isinstance(item, BaseException):
            raise item
        if item is None:
            raise StopAsyncIteration
        frame, size = item
        self.client.buffered_bytes -= size
        if frame["kind"] == "data" and not self.closed:
            handle = self.client.guard.handles[self.key]
            credit = handle["credit"].copy()
            credit["frames"] += 1
            credit["bytes"] += size
            await self.client._send("credit", subscriptionId=self.key, credit=credit)
        return frame

    async def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.client.guard.handles[self.key]["phase"] != "done":
                await self.client._send("cancel", handleId=self.key, handleType="subscription")
                try:
                    await asyncio.wait_for(self.ended.wait(), self.client.close_timeout)
                except TimeoutError:
                    await self.client.close()
                    raise
        finally:
            while not self.queue.empty():
                item = self.queue.get_nowait()
                if isinstance(item, tuple):
                    self.client.buffered_bytes -= item[1]
            self.client.subscriptions.pop(self.key, None)


class Client:
    def __init__(self, channel, guard, codec, *, close_timeout=3):
        self.channel, self.guard, self.codec = channel, guard, codec
        self.close_timeout = close_timeout
        self.send_lock = asyncio.Lock()
        self.requests = {}
        self.subscriptions = {}
        self.failure = None
        self.buffered_bytes = 0
        self.reader_task = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, channel, *, host, source, profile, codec, required=("snapshot", "subscribe"), timeout=3):
        hello = {"protocol": PROTOCOL, "version": 1, "kind": "hello", "sequence": 1,
                 "helloNonce": secrets.token_hex(16), "expectedHost": host, "sourceId": source,
                 "product": "state", "profile": profile, "requiredCapabilities": list(required),
                 "limits": {"maxMessageBytes": MAX_MESSAGE, "maxOutstanding": 8, "maxSubscriptions": 8}}
        guard = Lifecycle(hello, host)
        try:
            await channel.send(hello)
            frame, size = await asyncio.wait_for(channel.receive(), timeout)
            guard.received(frame, size)
            channel.maximum = guard.limits["maxMessageBytes"]
            return cls(channel, guard, codec)
        except BaseException:
            await channel.close()
            raise

    async def _send(self, kind, **fields):
        async with self.send_lock:
            if self.failure:
                raise self.failure
            frame = {"protocol": PROTOCOL, "version": 1, "channelId": self.guard.channel,
                     "sequence": self.guard.client_sequence + 1, "kind": kind, **fields}
            self.guard.sent(frame, boottime_ms(), allow_late_cancel=kind == "cancel")
            try:
                await self.channel.send(frame)
            except BaseException:
                await self.channel.close()
                raise

    async def request(self, operation="snapshot", parameters=None, *, timeout_ms=2000):
        key = secrets.token_hex(16)
        future = asyncio.get_running_loop().create_future()
        self.requests[key] = future
        deadline = boottime_ms() + timeout_ms
        try:
            await self._send("request", requestId=key, operation=operation, parameters=parameters or {},
                             timeoutMs=timeout_ms)
            while not future.done():
                remaining = deadline - boottime_ms()
                if remaining <= 0:
                    raise TimeoutError("request_deadline")
                # Short waits ensure BOOTTIME expiry is noticed promptly after suspend.
                await asyncio.wait({future}, timeout=min(remaining / 1000, .1))
            check(boottime_ms() < deadline, "request_deadline")
            return future.result()
        except (TimeoutError, asyncio.CancelledError):
            handle = self.guard.handles.get(key)
            if handle and handle["phase"] != "done":
                await self._send("cancel", handleId=key, handleType="request")
            raise
        finally:
            self.requests.pop(key, None)
            if not future.done():
                future.cancel()

    async def subscribe(self):
        key = secrets.token_hex(16)
        sub = Subscription(self, key)
        self.subscriptions[key] = sub
        try:
            await self._send("subscribe", subscriptionId=key, start={"mode": "baseline", "cursor": None},
                             credit={"frames": 32, "bytes": self.guard.limits["maxMessageBytes"]})
            await asyncio.wait_for(asyncio.shield(sub.ready), self.close_timeout)
            return sub
        except BaseException:
            if key in self.guard.handles:
                with contextlib.suppress(Exception):
                    await sub.close()
            self.subscriptions.pop(key, None)
            if sub.ready.done() and not sub.ready.cancelled():
                sub.ready.exception()
            else:
                sub.ready.cancel()
            raise

    async def _read(self):
        try:
            while True:
                frame, size = await self.channel.receive()
                self.guard.expire(boottime_ms())
                if frame["kind"] in {"data", "result"} and frame.get("payload") is not None:
                    self.codec(frame["payload"])
                outcome = self.guard.received(frame, size)
                if outcome == "error":
                    raise DeliveryError(frame["error"]["code"], frame["error"]["message"])
                if frame["kind"] == "result":
                    future = self.requests.get(frame["requestId"])
                    if future and not future.done() and outcome != "quarantined":
                        if frame["outcome"] == "ok":
                            future.set_result(frame["payload"])
                        else:
                            future.set_exception(DeliveryError(frame["error"]["code"], frame["error"]["message"]))
                key = frame.get("subscriptionId", frame.get("handleId"))
                sub = self.subscriptions.get(key)
                if sub:
                    if frame["kind"] == "ended":
                        sub.ended.set()
                        if not sub.ready.done():
                            sub.ready.set_exception(DeliveryError(frame["reason"]))
                        if not sub.closed:
                            terminal = None if frame["reason"] in {"completed", "cancelled"} else DeliveryError(frame["reason"])
                            sub.queue.put_nowait(terminal)
                    elif outcome != "quarantined":
                        if frame["kind"] == "subscribed":
                            sub.ready.set_result(frame)
                        else:
                            try:
                                check(self.buffered_bytes + size <= 96 * 1024 * 1024, "reader_byte_capacity")
                                sub.queue.put_nowait((frame, size))
                                self.buffered_bytes += size
                            except asyncio.QueueFull:
                                # Control congestion is a bounded channel failure, not unlimited buffering.
                                raise ProtocolError("reader_queue_capacity") from None
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(error)
        finally:
            await self.channel.close()

    def _fail(self, error):
        self.failure = error
        for future in self.requests.values():
            if not future.done():
                future.set_exception(error)
        for sub in self.subscriptions.values():
            if not sub.ready.done():
                sub.ready.set_exception(error)
            sub.ended.set()
            while not sub.queue.empty():
                item = sub.queue.get_nowait()
                if isinstance(item, tuple):
                    self.buffered_bytes -= item[1]
            sub.queue.put_nowait(error)

    async def close(self):
        if not self.channel.closed and not self.guard.closed:
            with contextlib.suppress(Exception):
                await self._send("close", reason="client_done")
        self._fail(self.failure or DeliveryError("channel_closed"))
        self.reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.reader_task
        await self.channel.close()
