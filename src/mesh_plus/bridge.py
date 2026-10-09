"""Fixed-source cached-read bridge. Publisher scheduling stays with the owner."""

import asyncio
import contextlib
import uuid
from dataclasses import dataclass

from .protocol import PROTOCOL, Lifecycle, ProtocolError, check, encode
from .transport import boottime_ms


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

    def __init__(self, adapter):
        self.adapter = adapter

    async def serve(self, channel):
        connection = _Connection(channel, self.adapter)
        try:
            await connection.run()
        finally:
            await connection.close()


class _Connection:
    def __init__(self, channel, adapter):
        self.channel, self.adapter = channel, adapter
        self.guard = None
        self.tasks = {}
        self.emit_lock = asyncio.Lock()
        self.changed = asyncio.Condition()

    async def emit(self, kind, *, credited=False, **fields):
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
            write = asyncio.create_task(self.channel.send(frame))
            try:
                await asyncio.shield(write)
            except asyncio.CancelledError:
                # Finish a frame already admitted to the wire before the ended barrier.
                await write
                raise
            return True

    async def run(self):
        hello, _ = await asyncio.wait_for(self.channel.receive(), 3)
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
            self.guard.sent(frame, boottime_ms())
            kind = frame["kind"]
            if kind == "close":
                return
            if kind in {"request", "subscribe"}:
                key = frame["requestId"] if kind == "request" else frame["subscriptionId"]
                coroutine = self.request(frame) if kind == "request" else self.subscription(frame)
                task = asyncio.create_task(coroutine)
                self.tasks[key] = task
                task.add_done_callback(lambda done, k=key: self.finished(k, done))
            elif kind == "cancel":
                key = frame["handleId"]
                task = self.tasks.get(key)
                if task:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                if self.guard.handles[key]["phase"] != "done":
                    await self.emit("ended", handleId=key, handleType=frame["handleType"], reason="cancelled", cursor=None)
            elif kind == "credit":
                async with self.changed:
                    self.changed.notify_all()

    def finished(self, key, task):
        self.tasks.pop(key, None)
        if not task.cancelled() and task.exception() is not None:
            # A transport/protocol failure cannot leave a half-live connection.
            asyncio.create_task(self.channel.close())

    async def request(self, frame):
        deadline = boottime_ms() + frame["timeoutMs"]
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

    async def subscription(self, frame):
        key = frame["subscriptionId"]
        iterator = self.adapter.watch().__aiter__()
        producer = None
        latest = None
        skipped = False
        finished = False
        wake = asyncio.Event()
        try:
            first = await asyncio.wait_for(anext(iterator), 3)
            self.adapter.validate(first.payload)
            await self.emit("subscribed", subscriptionId=key, start=frame["start"],
                            publisherEpoch=first.epoch, barrier=first.barrier)
            latest = first

            async def collect():
                nonlocal latest, skipped, finished
                try:
                    async for publication in iterator:
                        self.adapter.validate(publication.payload)
                        check(publication.epoch == first.epoch, "publisher_restart")
                        skipped = skipped or latest is not None
                        latest = publication
                        wake.set()
                finally:
                    finished = True
                    wake.set()

            producer = asyncio.create_task(collect())
            while True:
                if latest is not None:
                    publication = latest
                    if skipped and not self.guard.handles[key]["resync"]:
                        stream = self.guard.handles[key]["stream"] + 1
                        await self.emit("control", subscriptionId=key, streamSequence=stream,
                                        control="gap", payload={"reason": "state_coalesced"})
                        skipped = False
                    handle = self.guard.handles[key]
                    sent = await self.emit("data", credited=True, subscriptionId=key,
                                           streamSequence=handle["stream"] + 1, publisherEpoch=publication.epoch,
                                           deliveryKind="resync" if handle["resync"] else "view",
                                           cursor=None, payload=publication.payload)
                    if sent:
                        # A newer publication may have arrived during the bounded write.
                        if latest is publication:
                            latest = None
                        continue
                if finished:
                    if producer.done() and producer.exception():
                        raise producer.exception()
                    if latest is None:
                        await self.emit("ended", handleId=key, handleType="subscription", reason="completed", cursor=None)
                        return
                wake.clear()
                # Credit updates and source updates share bounded wake latency.
                async with self.changed:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self.changed.wait(), .05)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            reason = "publisher_restart" if isinstance(error, ProtocolError) and error.code == "publisher_restart" else "gap"
            if self.guard.handles[key]["phase"] != "done":
                await self.emit("ended", handleId=key, handleType="subscription", reason=reason, cursor=None)
        finally:
            if producer:
                producer.cancel()
                await asyncio.gather(producer, return_exceptions=True)
            if hasattr(iterator, "aclose"):
                await iterator.aclose()

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.channel.close()
