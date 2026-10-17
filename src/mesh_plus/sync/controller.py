"""Explicit R2+R3 relay control plane; no domain admission or route selection."""

import asyncio
from hashlib import sha256

from ..protocol import ProtocolError, check
from ..transport import boottime_ms, finish_owned, within_deadline
from ._boundary import _retire_error, async_admission_boundary
from ._constants import SYNC_PROTOCOL
from .canonical import canonical
from .control_carrier import SyncControlCarrier
from .model import NativeTag, hex_digest
from .relay import SyncRelay
from .wire import closed

_FIELDS = {
    "begin": "remainingMs", "baseline": "acquisition",
    "changes": "acquisition base target maxTransactions maxBytes",
    "head": "acquisition challenge remainingMs", "watch": "acquisition cursor",
    "stop-watch": "acquisition watch", "end": "acquisition", "cancel": "acquisition command",
}


class _Incoming:
    def __init__(self, value, floor, credit, size):
        self.value, self.floor, self.credit = value, floor, credit
        self.size = size

    def take(self):
        result = self.value, self.floor, self.credit
        self.value = self.credit = None
        return result

    def close(self):
        self.value = None
        if self.credit is not None:
            self.credit.close()
            self.credit = None


def _integer(value, minimum=1, maximum=2**64 - 1):
    check(type(value) is int and minimum <= value <= maximum, "sync_control_integer")


def _command(value, digest, sequence):
    check(type(value) is dict and type(value.get("operation")) is str and
          value["operation"] in _FIELDS, "sync_control_variant")
    operation = value["operation"]
    closed(value, "protocol kind request sequence operation " + _FIELDS[operation], "sync_control_variant")
    check(value["protocol"] == SYNC_PROTOCOL and value["kind"] == "command" and
          value["request"] == digest, "sync_control_request")
    _integer(value["sequence"])
    check(value["sequence"] == sequence, "sync_control_sequence")
    for name in ("acquisition", "watch", "command"):
        if name in value:
            _integer(value[name])
    if operation in ("begin", "head"):
        _integer(value["remainingMs"], maximum=2000 if operation == "head" else 15000)
    if operation == "changes":
        NativeTag.parse(value["base"])
        NativeTag.parse(value["target"])
        _integer(value["maxTransactions"], maximum=4)
        _integer(value["maxBytes"], maximum=8388608)
    if operation == "head":
        closed(value["challenge"], "nonce target request", "sync_challenge")
        for item in value["challenge"].values():
            hex_digest(item)
        check(value["challenge"]["request"] == digest, "sync_control_request")
    if operation == "watch":
        cursor = value["cursor"]
        check(type(cursor) is list and len(cursor) == 3 and type(cursor[0]) is str and
              0 < len(cursor[0]) <= 256, "sync_cursor")
        _integer(cursor[1], minimum=0)
        hex_digest(cursor[2])
    return operation


class _Record:
    def __init__(self, value, copied, deadline, capsule, ledger):
        self._credit = ledger.reserve(32768, encoded=8192)
        self.value, self._copied = value, copied
        self.command, self.operation = value["sequence"], value["operation"]
        self.deadline, self.capsule = deadline, capsule
        self.cap_deadline = deadline if capsule is None else capsule._deadline
        self.outcome, self.cleanup, self.intentional = None, False, False
        self.started, self.consumed, self.through = False, False, None

    def close(self):
        self.value = self.capsule = None
        if self._copied is not None:
            self._copied.close()
            self._copied = None
        self._credit.close()
        self._credit = None


class _Controller:
    def __init__(self, relay, carrier, credit):
        self.relay, self.carrier, self.credit = relay, carrier, credit
        self.channel = self.request = None
        self.sequence = 1
        self.capsule = self.capid = self.deadline = self.timer = None
        self.watch = self.watchid = self.watch_task = None
        self.active = self.active_task = self.read_task = None
        self.closed, self.close_task = False, None
        relay._controllers.add(self)
        relay._pending_controls.add(carrier.output_channel)

    def _check(self):
        check(not self.closed and not self.carrier._closed, "sync_control_retired")
        self.relay._check()

    async def receive(self, maximum, deadline):
        frame = copied = value = None
        try:
            frame = await self.carrier.receive_control(maximum_bytes=maximum, deadline_ms=deadline)
            copied = self.relay.ledger.reserve(frame.header.materialization_bytes)
            value = frame.header.materialize()
            self._check()
            floor = frame.first_byte_ms
            result = _Incoming(value, floor, copied, frame.stop - frame.start)
            value = copied = None
            return result
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            value = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            if frame is not None:
                frame.close()
            if copied is not None:
                copied.close()

    async def _initial(self, nonce, deadline):
        credit = self.relay.ledger.reserve(524288, encoded=131072)
        value = raw = None
        self._initial_started = False
        try:
            value = self.relay._offer("hello", nonce=nonce, bridgeId=self.relay.bridge_id)
            raw = canonical(value)
            check(len(raw) + 1 <= 65536, "sync_control_capacity")
            await within_deadline(self._initial_output(raw, deadline), deadline)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            if self._initial_started:
                self._begin_close()
            raw = value = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            raw = value = None
            credit.close()

    async def _initial_output(self, raw, deadline):
        line = self.carrier.output_channel
        part = None
        try:
            async with line.lock:
                for part in (raw, b"\n"):
                    self._check()
                    check(boottime_ms() < deadline, "sync_control_deadline")
                    self._initial_started = True
                    line.writer.write(part)
                    await line.writer.drain()
                    check(boottime_ms() < deadline, "sync_control_deadline")
                line._metrics["sentFrames"] += 1
                line._metrics["sentBytes"] += len(raw) + 1
                line._count_kind("sent", "hello", len(raw) + 1)
        finally:
            raw = part = None

    async def bootstrap(self, deadline):
        value = copied = None
        try:
            incoming = await self.receive(65536, deadline)
            value, _floor, copied = incoming.take()
            closed(value, "protocol kind nonce", "sync_control_hello")
            check(value["protocol"] == SYNC_PROTOCOL and value["kind"] == "hello", "sync_control_hello")
            hex_digest(value["nonce"])
            self.carrier._output._count_kind("received", "hello", incoming.size)
            await self._initial(value["nonce"], deadline)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            value = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            value = None
            if copied is not None:
                copied.close()
        copied = None
        try:
            incoming = await self.receive(8192, deadline)
            value, floor, copied = incoming.take()
            closed(value, "protocol kind controllerVersion requestBinding remainingMs", "sync_control_open")
            check(value["protocol"] == SYNC_PROTOCOL and value["kind"] == "open" and
                  type(value["controllerVersion"]) is int and value["controllerVersion"] == 1,
                  "sync_control_open")
            _integer(value["remainingMs"], maximum=15000)
            bound = min(deadline, floor + value["remainingMs"])
            check(boottime_ms() < bound, "sync_control_deadline")
            self.channel = await within_deadline(
                self.relay.open_channel(self.carrier.output_channel, value["requestBinding"], setup_deadline_ms=bound),
                bound)
            self.request = sha256(self.channel._request).hexdigest()
            self.carrier._output._count_kind("received", "open", incoming.size)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            value = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            value = None
            if copied is not None:
                copied.close()

    def _eligible(self, record):
        self._check()
        self.channel._check()
        check(not record.consumed and boottime_ms() < record.deadline, "sync_control_deadline")
        if record.outcome[0] == "failed":
            check(record.cleanup, "sync_control_receipt")
        elif record.outcome == ("ok", "none") and record.operation not in ("end", "cancel"):
            record.capsule._check()
            check(record.capsule is self.capsule, "sync_control_capsule")
        elif record.outcome[0] in ("cancelled",) or record.operation in ("end", "cancel"):
            check(record.intentional and record.cleanup, "sync_control_receipt")

    async def _emit(self, record):
        credit = self.relay.ledger.reserve(32768, encoded=8192)
        raw = value = part = None
        try:
            async with self.channel._output_lock, self.carrier.output_channel.lock:
                self._eligible(record)
                check(record.through is None, "sync_control_receipt")
                record.through = self.channel._sequence
                value = {"protocol": SYNC_PROTOCOL, "kind": "command-result", "request": self.request,
                         "command": record.command, "operation": record.operation,
                         "status": record.outcome[0], "code": record.outcome[1], "through": record.through}
                raw = canonical(value)
                check(len(raw) + 1 <= 8192, "sync_control_capacity")
                writer = self.carrier.output_channel.writer
                for part in (raw, b"\n"):
                    self._eligible(record)
                    record.started = True
                    writer.write(part)
                    await within_deadline(writer.drain(), record.deadline)
                    self._eligible(record)
                record.consumed = True
                line = self.carrier._output
                line._metrics["sentFrames"] += 1
                line._metrics["sentBytes"] += len(raw) + 1
                line._count_kind("sent", "command-result", len(raw) + 1)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            if record.started:
                self._begin_close()  # retire physical copies BEFORE their credit
            raw = value = part = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            raw = value = part = None
            credit.close()

    async def result(self, record):
        if self.closed or self.carrier._closed or boottime_ms() >= record.deadline:
            return
        try:
            await within_deadline(self._emit(record), record.deadline)
        except BaseException as error:
            _retire_error(error)
            if record.started or (not self.closed and boottime_ms() < record.deadline):
                self._begin_close()

    async def forget(self, capsule):
        if self.capsule is not capsule:
            return
        self.capsule = self.capid = self.deadline = None
        timer, self.timer = self.timer, None
        if timer is not None and timer is not asyncio.current_task():
            timer.cancel()
            await finish_owned(asyncio.gather(timer, return_exceptions=True))

    async def expire(self, capsule, deadline):
        try:
            try:
                await within_deadline(asyncio.Event().wait(), deadline)
            except TimeoutError:
                pass
            if self.closed or self.capsule is not capsule:
                return
            capsule._retire()
            if self.active is not None and self.active.capsule is capsule and self.active.outcome is None:
                self.active.outcome = "failed", "deadline"
                self.active_task.cancel()
            await capsule.aclose()
            await self.forget(capsule)
        except asyncio.CancelledError:
            pass
        except BaseException as error:
            _retire_error(error)
            self._begin_close()

    async def work(self, record):
        try:
            value, capsule, operation = record.value, record.capsule, record.operation
            if operation == "baseline":
                await capsule.baseline()
            elif operation == "changes":
                await capsule.changes(value["base"], target=value["target"],
                                      max_transactions=value["maxTransactions"], max_bytes=value["maxBytes"])
            elif operation == "head":
                await capsule.head_after_nonce(value["challenge"], not_after_ms=record.deadline)
            elif operation == "watch":
                self.watch = await self.channel.watch(value["cursor"], startup_deadline_ms=record.deadline)
                self.watchid = record.command
                self.watch_task = asyncio.create_task(self.watch.wait_closed())
            elif operation == "stop-watch":
                watch, stopped = self.watch, self.watch_task
                self.watch_task = None  # intentional stop is not a native EOF
                try:
                    await watch.aclose()
                finally:
                    await finish_owned(asyncio.gather(stopped, return_exceptions=True))
                    self.watch = self.watchid = None
            elif operation == "end":
                record.intentional = True
                capsule._retire()
                await capsule.aclose()
                await self.forget(capsule)
            if record.outcome is None:
                record.outcome = (("failed", "source") if operation in ("baseline", "changes") and
                                  capsule._last_ok is not True else ("ok", "none"))
        except BaseException as error:
            code, _signal, _ = _retire_error(error)
            if record.outcome is None:
                reason = "deadline" if "deadline" in code else "capacity" if "capacity" in code else "source"
                record.outcome = "failed", reason
        finally:
            value = None
        try:
            if record.outcome[0] != "ok":
                record.capsule._retire()
                await record.capsule.aclose()
                await self.forget(record.capsule)
            record.cleanup = True
            await self.result(record)
        finally:
            record.close()

    async def dispatch(self, incoming):
        value, floor, copied = incoming.take()
        record = None
        try:
            operation = _command(value, self.request, self.sequence)
            self.carrier._output._count_kind("received", "command", incoming.size)
            self.sequence += 1
            if operation == "begin":
                bound = floor + value["remainingMs"]
                if self.capsule is not None:
                    bound = min(bound, self.deadline)
                elif self.active is not None:
                    bound = min(bound, self.active.cap_deadline)
            else:
                check(self.capsule is not None and value["acquisition"] == self.capid, "sync_control_capsule")
                self.capsule._check()
                bound = self.deadline
                if operation == "head":
                    bound = min(bound, floor + value["remainingMs"], floor + 2000)
            check(boottime_ms() < bound, "sync_control_deadline")
            if operation == "stop-watch":
                check(self.watch is not None and value["watch"] == self.watchid, "sync_control_watch")
            if operation == "cancel":
                check(self.active is not None and self.active.command == value["command"] and
                      self.active.operation in ("baseline", "changes", "head") and self.active.outcome is None,
                      "sync_control_cancel")
            record = _Record(value, copied, bound, self.capsule, self.relay.ledger)
            value = copied = None
            if operation == "cancel":
                original = self.active
                record.intentional = original.intentional = True
                original.outcome = "cancelled", "none"
                record.capsule._retire()
                self.active_task.cancel()
                await finish_owned(asyncio.gather(self.active_task, return_exceptions=True))
                await record.capsule.aclose()
                await self.forget(record.capsule)
                record.outcome, record.cleanup = ("ok", "none"), True
                await self.result(record)
            elif self.active_task is not None or (operation == "begin" and self.capsule is not None) or (
                    self.watch is not None and operation in ("baseline", "changes", "watch")):
                record.outcome, record.cleanup = ("failed", "busy"), True
                await self.result(record)
            else:
                if operation == "begin":
                    self.capsule = record.capsule = self.channel.begin_acquisition(deadline_ms=bound)
                    self.capid, self.deadline = record.command, bound
                    self.timer = asyncio.create_task(self.expire(self.capsule, bound))
                self.active = record
                self.active_task = asyncio.create_task(self.work(record))
                record = None
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            value = None
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            value = None
            if copied is not None:
                copied.close()
            if record is not None:
                record.close()

    async def run(self, deadline):
        await self.bootstrap(deadline)
        while not self.closed:
            if self.read_task is None:
                self.read_task = asyncio.create_task(self.receive(8192, 2**64 - 1))
            tasks = {self.read_task}
            tasks.update(task for task in (self.active_task, self.watch_task) if task is not None)
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if self.active_task in done:
                self.active_task.result()
                self.active_task = self.active = None
            if self.watch_task in done:
                self.watch_task.result()
                raise ProtocolError("sync_control_watch")
            if self.read_task in done:
                incoming = self.read_task.result()
                self.read_task = None
                await self.dispatch(incoming)
                incoming = None

    def _begin_close(self):
        if self.closed:
            return
        self.closed = True
        self.carrier._begin_close()
        if self.channel is not None:
            self.channel._begin_close()
        for task in (self.read_task, self.active_task, self.timer, self.watch_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()

    async def aclose(self):
        self._begin_close()
        if self.close_task is None:
            self.close_task = asyncio.create_task(self._close())
        await finish_owned(self.close_task)

    async def _close(self):
        tasks = [task for task in (self.read_task, self.active_task, self.timer, self.watch_task) if task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # A completed receive may own a copy that the main loop never delivered.
        if self.read_task is not None and not self.read_task.cancelled() and self.read_task.exception() is None:
            self.read_task.result().close()
        if self.capsule is not None:
            await self.capsule.aclose()
        if self.channel is not None:
            await self.channel.aclose()
        await self.carrier.aclose()
        self.relay._controllers.discard(self)
        self.relay._pending_controls.discard(self.carrier._output)
        self.capsule = self.channel = self.watch = self.active = None
        self.read_task = self.active_task = self.timer = self.watch_task = None
        tasks.clear()
        self.credit.close()
        self.credit = self.relay = self.carrier = None


@async_admission_boundary
async def serve_sync_relay(relay, carrier, *, setup_deadline_ms):
    check(type(relay) is SyncRelay and type(carrier) is SyncControlCarrier and
          carrier._ledger is relay.ledger, "sync_control_owner")
    relay._check()
    carrier._check()
    now = boottime_ms()
    check(type(setup_deadline_ms) is int and now < setup_deadline_ms <= now + 15000,
          "sync_control_deadline")
    controller = credit = None
    try:
        check(len(relay._channels) + len(relay._pending_controls) < 16, "sync_relay_busy")
        credit = relay.ledger.reserve(131072, encoded=8192)
        controller = _Controller(relay, carrier, credit)
        credit = None
        await controller.run(setup_deadline_ms)
    finally:
        if controller is not None:
            await controller.aclose()
        else:
            await carrier.aclose()
            if credit is not None:
                credit.close()
