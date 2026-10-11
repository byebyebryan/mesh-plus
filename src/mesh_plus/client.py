"""Concurrent cached reads and bounded state subscriptions on one channel."""

import asyncio
import contextlib
import secrets

from .protocol import MAX_CONTROL, MAX_HANDLES, MAX_MESSAGE, PROTOCOL, Lifecycle, ProtocolError, check
from .transport import boottime_ms, within_deadline

# Retain the protocol's tombstones. Reserve room rather than weakening its
# no-reuse rule; the connection owner replaces channels, never this Client.
ROTATION_HANDLES = MAX_HANDLES - 16


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
        self.exhausted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed or self.exhausted:
            raise StopAsyncIteration
        item = await self.queue.get()
        if isinstance(item, BaseException):
            self.exhausted = True
            raise item
        if item is None:
            self.exhausted = True
            raise StopAsyncIteration
        frame, size = item
        self.client.buffered_bytes -= size
        if frame["kind"] == "control":
            self.client.buffered_control_bytes -= size
        if frame["kind"] == "data" and not self.closed and self.client.guard.handles[self.key]["phase"] != "done":
            handle = self.client.guard.handles[self.key]
            credit = handle["credit"].copy()
            credit["frames"] += 1
            credit["bytes"] += size
            await self.client._send("credit", subscriptionId=self.key, credit=credit)
        if self.closed:
            raise StopAsyncIteration
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
                    if item[0]["kind"] == "control":
                        self.client.buffered_control_bytes -= item[1]
            self.queue.put_nowait(None)
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
        self.buffered_control_bytes = 0
        self.peak_buffered_bytes = 0
        self.peak_buffered_control_bytes = 0
        self.peak_queue_frames = 0
        self.operations = {}
        self.metrics = {"snapshotRequests": 0, "proofRequests": 0,
                        "snapshotResultBytes": 0, "proofResultBytes": 0,
                        "otherResultBytes": 0, "requestTimeouts": 0,
                        "requestCancellations": 0, "rotationRejections": 0}
        self.reader_task = asyncio.create_task(self._read())

    def rotation_due(self):
        """Stop admitting handles while existing work can still drain/cancel."""
        return len(self.guard.handles) >= ROTATION_HANDLES

    def inspect(self):
        """Local diagnostic summary; no producer payloads or exception text."""
        channel = self.channel.inspect() if hasattr(self.channel, "inspect") else None
        operations = self.metrics.copy()
        if channel is not None and "byKind" in channel:
            received = channel["byKind"]["received"].get("result", {}).get("bytes", 0)
            attributed = sum(operations[key] for key in ("snapshotResultBytes", "proofResultBytes", "otherResultBytes"))
            # A decoded line may precede codec rejection or task cancellation.
            operations["unprocessedResultBytes"] = max(0, received - attributed)
        return {"closed": self.channel.closed, "failed": self.failure is not None,
                "capabilities": sorted(self.guard.capabilities),
                "activeHandles": sum(handle["phase"] != "done" for handle in self.guard.handles.values()),
                "pendingRequests": len(self.requests), "subscriptions": len(self.subscriptions),
                "retainedHandles": len(self.guard.handles), "bufferedBytes": self.buffered_bytes,
                "bufferedControlBytes": self.buffered_control_bytes,
                "rotationDue": self.rotation_due(), "rotationHandles": ROTATION_HANDLES,
                "peakBufferedBytes": self.peak_buffered_bytes,
                "peakBufferedControlBytes": self.peak_buffered_control_bytes,
                "peakQueueFrames": self.peak_queue_frames, "operations": operations,
                "channel": channel}

    @classmethod
    async def connect(cls, channel, *, host, source, profile, codec, required=("snapshot", "subscribe"), timeout=3):
        hello = {"protocol": PROTOCOL, "version": 1, "kind": "hello", "sequence": 1,
                 "helloNonce": secrets.token_hex(16), "expectedHost": host, "sourceId": source,
                 "product": "state", "profile": profile, "requiredCapabilities": list(required),
                 "limits": {"maxMessageBytes": MAX_MESSAGE, "maxOutstanding": 8, "maxSubscriptions": 8}}
        guard = Lifecycle(hello, host)
        try:
            async def handshake():
                await channel.send(hello)
                frame, size = await channel.receive()
                outcome = guard.received(frame, size)
                if outcome == "setup_error":
                    raise DeliveryError(frame["error"]["code"], frame["error"]["message"])
                return outcome
            await within_deadline(handshake(), boottime_ms() + int(timeout * 1000))
            channel.maximum = guard.limits["maxMessageBytes"]
            return cls(channel, guard, codec)
        except BaseException:
            await channel.close()
            raise

    async def _send(self, kind, *, deadline_ms=None, **fields):
        async with self.send_lock:
            if self.failure:
                raise self.failure
            if kind in {"request", "subscribe"} and self.rotation_due():
                self.metrics["rotationRejections"] += 1
                raise DeliveryError("channel_rotation_required")
            if kind == "credit" and self.guard.handles[fields["subscriptionId"]]["phase"] == "done":
                return
            if deadline_ms is not None:
                remaining = deadline_ms - boottime_ms()
                if remaining <= 0:
                    raise TimeoutError("request_deadline")
                fields["timeoutMs"] = min(fields["timeoutMs"], remaining)
            frame = {"protocol": PROTOCOL, "version": 1, "channelId": self.guard.channel,
                     "sequence": self.guard.client_sequence + 1, "kind": kind, **fields}
            self.guard.sent(frame, boottime_ms(), allow_late_cancel=kind == "cancel")
            if kind == "request":
                self.metrics[fields["operation"] + "Requests"] += 1
            try:
                await self.channel.send(frame)
            except BaseException:
                await self.channel.close()
                raise

    async def request(self, operation="snapshot", parameters=None, *, timeout_ms=2000):
        check(type(timeout_ms) is int and 1 <= timeout_ms <= 60000, "request_budget")
        check(len(self.requests) < self.guard.limits["maxOutstanding"], "handle_capacity")
        key = secrets.token_hex(16)
        future = asyncio.get_running_loop().create_future()
        self.requests[key] = future
        self.operations[key] = operation
        deadline = boottime_ms() + timeout_ms
        try:
            await within_deadline(self._send("request", requestId=key, operation=operation,
                                             parameters={} if parameters is None else parameters,
                                             timeoutMs=timeout_ms, deadline_ms=deadline), deadline)
            while not future.done():
                remaining = deadline - boottime_ms()
                if remaining <= 0:
                    raise TimeoutError("request_deadline")
                # Short waits ensure BOOTTIME expiry is noticed promptly after suspend.
                await asyncio.wait({future}, timeout=min(remaining / 1000, .1))
            if boottime_ms() >= deadline:
                raise TimeoutError("request_deadline")
            return future.result()
        except (TimeoutError, asyncio.CancelledError) as error:
            self.metrics["requestTimeouts" if isinstance(error, TimeoutError) else "requestCancellations"] += 1
            handle = self.guard.handles.get(key)
            if handle and handle["phase"] != "done" and not self.channel.closed:
                with contextlib.suppress(Exception):
                    await self._send("cancel", handleId=key, handleType="request")
            raise
        finally:
            self.requests.pop(key, None)
            self.operations.pop(key, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def subscribe(self):
        check(len(self.subscriptions) < self.guard.limits["maxSubscriptions"], "handle_capacity")
        key = secrets.token_hex(16)
        sub = Subscription(self, key)
        self.subscriptions[key] = sub
        try:
            async def admission():
                await self._send("subscribe", subscriptionId=key, start={"mode": "baseline", "cursor": None},
                                 credit={"frames": 32, "bytes": self.guard.limits["maxMessageBytes"]})
                # Cancellation retires admission through the except block below.
                # Wait without cancelling ready or creating a shield wrapper:
                # Python 3.14 reports a late ended error through that wrapper
                # even when cleanup subsequently observes ready's exception.
                await asyncio.wait({sub.ready})
                return sub.ready.result()
            await within_deadline(admission(), boottime_ms() + int(self.close_timeout * 1000))
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
                    operation = self.operations.get(frame["requestId"], "other")
                    self.metrics[operation + "ResultBytes"] += size + getattr(self.channel, "framing_bytes", 1)
                    future = self.requests.get(frame["requestId"])
                    if future and not future.done() and outcome != "quarantined":
                        if frame["outcome"] == "ok":
                            future.set_result(frame["payload"])
                        else:
                            future.set_exception(DeliveryError(frame["error"]["code"], frame["error"]["message"]))
                elif frame["kind"] == "ended" and frame["handleType"] == "request":
                    future = self.requests.get(frame["handleId"])
                    if future and not future.done() and outcome != "quarantined":
                        future.set_exception(DeliveryError(frame["reason"]))
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
                                if frame["kind"] == "control":
                                    check(self.buffered_control_bytes + size <= MAX_CONTROL, "control_reserve")
                                sub.queue.put_nowait((frame, size))
                                self.buffered_bytes += size
                                self.peak_buffered_bytes = max(self.peak_buffered_bytes, self.buffered_bytes)
                                self.peak_queue_frames = max(self.peak_queue_frames, sub.queue.qsize())
                                if frame["kind"] == "control":
                                    self.buffered_control_bytes += size
                                    self.peak_buffered_control_bytes = max(self.peak_buffered_control_bytes,
                                                                          self.buffered_control_bytes)
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
                    if item[0]["kind"] == "control":
                        self.buffered_control_bytes -= item[1]
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
