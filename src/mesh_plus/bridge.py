"""Fixed-source cached-read bridge. Publisher scheduling stays with the owner."""

import asyncio
import contextlib
import uuid
from dataclasses import dataclass

from .protocol import PROTOCOL, Lifecycle, ProtocolError, check, encode
from .transport import (
    _finish_owned_tasks,
    _observe_cancelled_task_errors,
    boottime_ms,
    finish_owned,
)


@dataclass(frozen=True)
class Publication:
    payload: dict
    epoch: str
    barrier: dict


class Bridge:
    """An adapter supplies snapshot(), watch() and validate(payload).

    watch is a native cached-state iterator, never an implicit polling fallback.
    Adapters expose explicit capabilities and a fixed host/source/profile.
    """

    def __init__(self, adapter, *, heartbeat_interval=5, credit_timeout=15):
        self.adapter = adapter
        check(.01 <= heartbeat_interval <= 5 and .01 <= credit_timeout <= 15, "delivery_timing")
        self.heartbeat_interval, self.credit_timeout = heartbeat_interval, credit_timeout

    async def serve(self, channel):
        connection = _Connection(channel, self.adapter, self.heartbeat_interval, self.credit_timeout)
        try:
            await connection.run()
        except BaseException:
            # Closing is still mandatory after a failed run, but cleanup must
            # not replace the original connection failure.
            try:
                await connection.close(suppress_errors=True)
            except BaseException:
                pass
            raise
        else:
            await connection.close()
        finally:
            # A stream can retain its original IO exception after close. Its
            # traceback must not keep these completed application owners alive.
            connection = channel = self = None


class _Connection:
    def __init__(self, channel, adapter, heartbeat_interval, credit_timeout):
        self.channel, self.adapter = channel, adapter
        self.guard = None
        self.tasks = {}
        self.emit_lock = asyncio.Lock()
        self.wakes = {}
        self.heartbeat_interval, self.credit_timeout = heartbeat_interval, credit_timeout

    async def emit(self, kind, *, credited=False, on_admit=None, **fields):
        async with self.emit_lock:
            frame = {"protocol": PROTOCOL, "version": 1, "channelId": self.guard.channel,
                     "sequence": self.guard.server_sequence + 1, "kind": kind, **fields}
            size = len(encode(frame))
            if credited:
                handle = self.guard.handles[fields["subscriptionId"]]
                if handle["phase"] != "active":
                    return False
                if handle["frames"] + 1 > handle["credit"]["frames"] or handle["bytes"] + size > handle["credit"]["bytes"]:
                    return False
            self.guard.received(frame, size)
            if on_admit:
                on_admit()
            write = None
            try:
                write = asyncio.create_task(self.channel.send(frame))
                # Finish an admitted frame before releasing the ended barrier lock.
                await finish_owned(write)
            finally:
                # A failed send task retains this frame through its exception
                # traceback. Do not leave the completed task in that frame.
                write = None
                frame = fields = on_admit = None
            return True

    async def run(self):
        hello, _ = await asyncio.wait_for(self.channel.receive(), 3)
        if hello["kind"] == "hello":
            code = None
            if hello["product"] != "state":
                code = "unsupported_product"
            elif hello["expectedHost"] != self.adapter.host:
                code = "scope_mismatch"
            elif hello["sourceId"] != self.adapter.source or hello["profile"] != self.adapter.profile:
                code = "unsupported_contract"
            elif not set(hello["requiredCapabilities"]) <= set(self.adapter.capabilities):
                code = "unsupported_capability"
            if code:
                await self.channel.send({"protocol": PROTOCOL, "version": 1, "sequence": 1,
                                         "kind": "setup-error", "helloNonce": hello["helloNonce"],
                                         "error": {"code": code, "message": "Configured source/profile unavailable"}})
                return
        self.guard = Lifecycle(hello, self.adapter.host)
        check(hello["expectedHost"] == self.adapter.host and hello["sourceId"] == self.adapter.source and
              hello["profile"] == self.adapter.profile, "source_binding")
        check(set(hello["requiredCapabilities"]) <= set(self.adapter.capabilities), "unsupported_capability")
        response = {"protocol": PROTOCOL, "version": 1, "sequence": 1, "kind": "hello",
                    "channelId": str(uuid.uuid4()), "helloNonce": hello["helloNonce"], "hostId": self.adapter.host,
                    "sourceId": self.adapter.source, "product": "state", "profile": self.adapter.profile,
                    "capabilities": list(self.adapter.capabilities), "limits": hello["limits"].copy()}
        self.guard.received(response, len(encode(response)))
        await self.channel.send(response)
        self.channel.maximum = self.guard.limits["maxMessageBytes"]
        while True:
            frame, _ = await self.channel.receive()
            self.guard.sent(frame, boottime_ms(), allow_late_cancel=True, allow_late_credit=True)
            kind = frame["kind"]
            if kind == "close":
                return
            if kind in {"request", "subscribe"}:
                key = frame["requestId"] if kind == "request" else frame["subscriptionId"]
                coroutine = self.request(frame) if kind == "request" else self.subscription(frame)
                task = None
                try:
                    task = asyncio.create_task(coroutine)
                    self.tasks[key] = task
                    task.add_done_callback(lambda done, k=key: self.finished(k, done))
                finally:
                    coroutine = None
                    task = None
            elif kind == "cancel":
                key = frame["handleId"]
                task = self.tasks.get(key)
                if task is not None:
                    task.cancel()
                    try:
                        await _finish_owned_tasks((task,))
                    finally:
                        if self.tasks.get(key) is task:
                            self.tasks.pop(key, None)
                        task = None
                if self.guard.handles[key]["phase"] != "done":
                    await self.emit("ended", handleId=key, handleType=frame["handleType"], reason="cancelled", cursor=None)
            elif kind == "credit":
                if frame["subscriptionId"] in self.wakes:
                    self.wakes[frame["subscriptionId"]].set()

    def finished(self, key, task):
        self.tasks.pop(key, None)
        if task.cancelled():
            _observe_cancelled_task_errors((task,))
        elif task.exception() is not None:
            # A transport/protocol failure cannot leave a half-live connection.
            asyncio.create_task(self.channel.close())

    async def request(self, frame):
        deadline = boottime_ms() + frame["timeoutMs"]
        method = payload = None
        try:
            try:
                method = self.adapter.snapshot if frame["operation"] == "snapshot" else self.adapter.proof
                payload = await asyncio.wait_for(method(frame["parameters"]), frame["timeoutMs"] / 1000)
                check(boottime_ms() < deadline, "request_deadline")
                self.adapter.validate(payload)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                code = "deadline" if isinstance(error, TimeoutError) else "source_unavailable"
                await self.emit("result", requestId=frame["requestId"], outcome="error", payload=None,
                                error={"code": code, "message": "Cached source request failed"})
            else:
                await self.emit("result", requestId=frame["requestId"], outcome="ok", payload=payload, error=None)
        finally:
            method = payload = None

    async def subscription(self, frame):
        key = frame["subscriptionId"]
        iterator = self.adapter.watch().__aiter__()
        producer = None
        latest = None
        skipped = False
        finished = False
        wake = asyncio.Event()
        self.wakes[key] = wake
        last_progress = boottime_ms()
        blocked_since = None
        primary_error = False
        first = publication = outgoing = admitted = collect = None
        try:
            first = await asyncio.wait_for(anext(iterator), 3)
            self.adapter.validate(first.payload)
            await self.emit("subscribed", subscriptionId=key, start=frame["start"],
                            publisherEpoch=first.epoch, barrier=first.barrier)
            latest = first
            publisher_epoch = first.epoch
            first = None

            async def collect():
                nonlocal latest, skipped, finished
                try:
                    async for publication in iterator:
                        self.adapter.validate(publication.payload)
                        check(publication.epoch == publisher_epoch, "publisher_restart")
                        skipped = skipped or latest is not None
                        latest = publication
                        wake.set()
                finally:
                    publication = None
                    finished = True
                    wake.set()

            producer = asyncio.create_task(collect())
            while True:
                wake.clear()
                if latest is not None:
                    publication = latest
                    if skipped and not self.guard.handles[key]["resync"]:
                        stream = self.guard.handles[key]["stream"] + 1
                        await self.emit("control", subscriptionId=key, streamSequence=stream,
                                        control="gap", payload={"gapKind": "delivery", "reason": "state_coalesced"})
                        last_progress = boottime_ms()
                        skipped = False
                    handle = self.guard.handles[key]
                    outgoing = publication
                    reset = getattr(self.adapter, "reset_publication", None)
                    reset_version = getattr(self.adapter, "_mesh_publication_reset", None)
                    if (handle["resync"] and type(reset_version) is int and
                            reset_version == 1 and callable(reset)):
                        outgoing = reset(publication)
                        check(isinstance(outgoing, Publication) and outgoing.epoch == publication.epoch,
                              "reset_publication")
                        self.adapter.validate(outgoing.payload)
                    def admitted():
                        nonlocal latest, skipped
                        if latest is publication:
                            latest = None
                            skipped = False
                    sent = await self.emit("data", credited=True, on_admit=admitted, subscriptionId=key,
                                           streamSequence=handle["stream"] + 1, publisherEpoch=publication.epoch,
                                           deliveryKind="resync" if handle["resync"] else "view",
                                           cursor=None, payload=outgoing.payload)
                    outgoing = None
                    if sent:
                        last_progress = boottime_ms()
                        blocked_since = None
                        continue
                    blocked_since = boottime_ms() if blocked_since is None else blocked_since
                    if boottime_ms() - blocked_since >= int(self.credit_timeout * 1000):
                        await self.emit("ended", handleId=key, handleType="subscription", reason="deadline", cursor=None)
                        return
                if finished:
                    if producer.done() and producer.exception():
                        raise producer.exception()
                    if latest is None:
                        await self.emit("ended", handleId=key, handleType="subscription", reason="completed", cursor=None)
                        return
                if boottime_ms() - last_progress >= int(self.heartbeat_interval * 1000):
                    await self.emit("control", subscriptionId=key,
                                    streamSequence=self.guard.handles[key]["stream"] + 1,
                                    control="heartbeat", payload={})
                    last_progress = boottime_ms()
                wait_ms = max(1, int(self.heartbeat_interval * 1000) - (boottime_ms() - last_progress))
                if blocked_since is not None:
                    wait_ms = min(wait_ms, max(1, int(self.credit_timeout * 1000) - (boottime_ms() - blocked_since)))
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(wake.wait(), wait_ms / 1000)
        except asyncio.CancelledError:
            primary_error = True
            raise
        except Exception as error:
            primary_error = True
            reason = "publisher_restart" if isinstance(error, ProtocolError) and error.code == "publisher_restart" else "gap"
            if self.guard.handles[key]["phase"] != "done":
                await self.emit("ended", handleId=key, handleType="subscription", reason=reason, cursor=None)
            primary_error = False
        except BaseException:
            primary_error = True
            raise
        finally:
            self.wakes.pop(key, None)
            cleanup_cancelled = False
            owned_producer = producer
            if owned_producer is not None:
                owned_producer.cancel()
                try:
                    await _finish_owned_tasks((owned_producer,))
                except asyncio.CancelledError:
                    cleanup_cancelled = True
                finally:
                    producer = None
                    owned_producer = None
            close_task = None
            try:
                if hasattr(iterator, "aclose"):
                    close_task = asyncio.ensure_future(iterator.aclose())
                    try:
                        await finish_owned(close_task)
                    except asyncio.CancelledError:
                        cleanup_cancelled = True
            except BaseException:
                if not primary_error:
                    raise
            finally:
                close_task = None
                iterator = None
                latest = None
            first = publication = outgoing = admitted = collect = None
            if cleanup_cancelled and not primary_error:
                raise asyncio.CancelledError

    async def close(self, *, suppress_errors=False):
        tasks = tuple(self.tasks.values())
        for task in tasks:
            task.cancel()
        cancelled = False
        try:
            await _finish_owned_tasks(tasks)
        except asyncio.CancelledError:
            cancelled = True
        finally:
            self.tasks.clear()
            tasks = ()
            task = None

        close_task = None
        try:
            close_task = asyncio.ensure_future(self.channel.close())
            try:
                await finish_owned(close_task)
            except asyncio.CancelledError:
                cancelled = True
        except BaseException:
            if not suppress_errors:
                raise
        finally:
            close_task = None
            # Requests and watch iterators have unwound before channel close.
            # An IO exception held by the closed stream may retain this frame,
            # but the completed connection no longer needs its adapter.
            self.adapter = None

        if cancelled and not suppress_errors:
            raise asyncio.CancelledError
