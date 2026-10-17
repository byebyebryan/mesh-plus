"""Opt-in R4 byte relay. Structural claims never bypass Reader admission.

There is deliberately no CLI/source selection or operation-request dispatcher.
The trusted controller supplies an authenticated LineChannel and the complete
binding obtained after the reviewed hello exchange.
"""

import asyncio
import os
import re
import secrets
from collections.abc import Mapping
from contextlib import contextmanager
from hashlib import sha256

from ..evidence import clock_domain
from ..protocol import ProtocolError, check
from ..transport import LineChannel, boottime_ms, finish_owned, within_deadline
from ._boundary import _retire_error, admission_boundary, async_admission_boundary
from ._constants import SYNC_PROTOCOL
from .budget import AllocationLedger
from .cache import SyncBudgets
from .cache import source_binding as configured_source_binding
from .canonical import canonical, decode
from .commitment import binding_digest, source_root
from .model import NativeTag, SourceTag, SyncDescriptor, hex_digest
from .relay_inputs import RelayInputRef, mint_relay_inputs, relay_bytes
from .wire import MAX_HEAD, MAX_MESSAGE, MAX_NATIVE, MAX_PROOF, closed, cursor, entries, owner_clock

_MINT = object()
_ROLE = "transport-relay"
_FEATURES = ["baseline", "transactions", "watch", "head-after-nonce"]
_LIMITS = dict(zip(
    ("nativeFrameBytes", "messageBytes", "nativeHeadBytes", "proofBytes", "transactions",
     "transactionBytes", "heapBytes", "encodedBytes", "nativeClients", "subscriptionsPerChannel",
     "pendingPerChannel", "heartbeatMs", "blockedMs"),
    (MAX_NATIVE, MAX_MESSAGE, MAX_HEAD, MAX_PROOF, 4, 8388608, 67108864, 33554432, 16, 8, 8, 5000, 15000),
))


class _ScanLease:
    """Only close escapes a scanner call; no grow/ledger capability."""

    __slots__ = ("_credit",)

    def __init__(self, credit):
        self._credit = credit

    def close(self):
        credit, self._credit = self._credit, None
        if credit is not None:
            credit.close()


class _ScanBudget:
    """Callback-scoped reserve capability; ticket leases survive separately."""

    def __init__(self, ledger):
        self._ledger, self._leases = ledger, []

    def reserve(self, amount, *, encoded=0):
        check(self._ledger is not None, "sync_reference_retired")
        check(len(self._leases) < 64, "sync_input_slots")
        credit = self._ledger.reserve(amount, encoded=encoded)
        try:
            lease = _ScanLease(credit)
            self._leases.append(lease)
            return lease
        except BaseException:
            credit.close()
            raise

    def finish(self, *, failed=False):
        leases, self._leases = self._leases, []
        self._ledger = None
        if failed:
            for credit in leases:
                credit.close()


def _plain(value, depth=0, nodes=None):
    nodes = [0] if nodes is None else nodes
    nodes[0] += 1
    check(depth <= 8 and nodes[0] <= 512, "sync_relay_setup")
    if isinstance(value, Mapping):
        check(len(value) <= 32, "sync_relay_setup")
        return {key: _plain(child, depth + 1, nodes) for key, child in value.items()}
    if type(value) in (tuple, list):
        check(len(value) <= 32, "sync_relay_setup")
        return [_plain(child, depth + 1, nodes) for child in value]
    check(type(value) in (str, int, bool, type(None)), "sync_json_type")
    check(type(value) is not str or len(value) <= 4096, "sync_relay_setup")
    return value


def _deadline(value):
    now = boottime_ms()
    check(type(value) is int and now < value <= now + 15000, "sync_acquisition_deadline")
    return value


def _request(value, relay):
    value = _plain(value)
    closed(value, "readerEpoch requestId catalogRevision hosts route channelEpoch bridgeId role encodingDigest",
           "sync_relay_setup")
    for name in ("readerEpoch", "channelEpoch", "bridgeId"):
        check(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{32}", value[name]), "sync_relay_setup")
    for name, maximum in (("requestId", 128), ("catalogRevision", 256), ("route", 256)):
        check(type(value[name]) is str and 0 < len(value[name]) <= maximum, "sync_relay_setup")
    hosts = value["hosts"]
    check(type(hosts) is list and 0 < len(hosts) <= 16 and
          all(type(host) is str and 0 < len(host) <= 256 for host in hosts) and
          len(set(hosts)) == len(hosts), "sync_relay_setup")
    check(decode(relay._binding)["host"] in hosts, "sync_relay_setup")
    check(value["role"] == _ROLE and value["bridgeId"] == relay.bridge_id and
          value["encodingDigest"] == relay._encoding_digest, "sync_relay_role")
    raw = canonical(value)
    check(len(raw) <= 4096, "sync_relay_setup")
    return raw


def _native_tag(value):
    if type(value) is NativeTag:
        return value
    return NativeTag.parse(_plain(value))


def _source_tag(binding, native):
    return SourceTag(native, binding_digest(binding, native=False).hex(),
                     source_root(binding, bytes.fromhex(native.root)).hex()).wire()


class SyncRelay:
    """Configured factory with no domain profile, material cache or authority."""

    def __init__(self, source, descriptor, binding, codec, budgets, ledger, owns_source, credit, *, _mint=None):
        check(_mint is _MINT, "sync_relay_setup")
        self._source, self._descriptor, self._ledger = source, descriptor, ledger
        self._codec, self._owns_source, self._credit = codec, owns_source, credit
        self._binding = canonical(binding)
        self._encoding = canonical(_plain(codec.encoding))
        self._encoding_digest = sha256(self._encoding).hexdigest()
        self._callbacks = (codec.header, codec.head, source.open_session, source.aclose)
        self._bridge_id = secrets.token_hex(16)
        self._channels, self._closed, self._close_task = set(), False, None
        self._limits = {**_LIMITS, "heapBytes": budgets.decoded_bytes, "encodedBytes": budgets.encoded_bytes}

    @property
    def bridge_id(self):
        return self._bridge_id

    @property
    def source(self):
        return self._source

    @property
    def descriptor(self):
        return self._descriptor

    @property
    def ledger(self):
        return self._ledger

    def _check(self):
        check(not self._closed, "sync_input_retired")
        check(self._callbacks == (self._codec.header, self._codec.head, self.source.open_session, self.source.aclose) and
              canonical(_plain(self._codec.encoding)) == self._encoding, "sync_codec_identity")

    def _offer(self, kind, **fields):
        return {"protocol": SYNC_PROTOCOL, "kind": kind, "descriptor": self.descriptor.wire(),
                "sourceBinding": decode(self._binding), "role": _ROLE,
                "encoding": decode(self._encoding), "features": _FEATURES.copy(),
                "limits": self._limits.copy(), **fields}

    @async_admission_boundary
    async def open_channel(self, channel, request_binding, *, setup_deadline_ms):
        self._check()
        deadline = _deadline(setup_deadline_ms)
        check(type(channel) is LineChannel and not channel.closed, "sync_relay_setup")
        check(len(self._channels) < 16, "sync_relay_busy")
        # Prepay argument conversion and all bounded control state before copy.
        credit = self.ledger.reserve(262144, encoded=65536)
        owned = None
        try:
            request = _request(request_binding, self)
            owned = RelayChannel(self, channel, request, credit, _mint=_MINT)
            self._channels.add(owned)
        except BaseException:
            credit.close()  # argument failure has not transferred the channel
            raise
        try:
            owned._inputs = mint_relay_inputs(owned)
            owned._session = self.source.open_session(owned._inputs)
            check(all(callable(getattr(owned._session, name, None)) for name in
                      ("baseline", "changes", "head_after_nonce", "watch", "aclose")), "sync_relay_setup")
            owned._check()
            await owned._send_control(self._offer("setup", requestBinding=decode(request)), deadline)
            return owned
        except BaseException:
            await owned.aclose()
            raise

    async def aclose(self):
        if self._close_task is None:
            self._closed = True
            for channel in tuple(self._channels):
                channel._begin_close()
            self._close_task = asyncio.create_task(self._close())
        await finish_owned(self._close_task)

    async def _close(self):
        await asyncio.gather(*(channel.aclose() for channel in tuple(self._channels)))
        if self._owns_source:
            await self._callbacks[3]()
        self._callbacks = ()
        self._source = self._codec = None
        descriptor, self._descriptor = self._descriptor, None
        self.ledger.release(descriptor)
        descriptor = None
        self._credit.close()


@admission_boundary
def create_sync_relay(source, descriptor, source_binding, *, native_codec, budgets, ledger, owns_source=True):
    check(type(descriptor) is SyncDescriptor and type(budgets) is SyncBudgets and
          type(ledger) is AllocationLedger and type(owns_source) is bool, "sync_relay_setup")
    check(ledger.maximum <= budgets.decoded_bytes and ledger.encoded_maximum <= budgets.encoded_bytes,
          "sync_relay_setup")
    check(all(callable(getattr(source, name, None)) for name in ("open_session", "aclose")) and
          all(callable(getattr(native_codec, name, None)) for name in ("header", "head")), "sync_relay_setup")
    credit = ledger.reserve(262144, encoded=65536)
    retained = False
    try:
        binding, encoding = _plain(source_binding), _plain(native_codec.encoding)
        check(type(binding) is dict and binding == configured_source_binding(
              binding.get("host"), binding.get("source"), descriptor),
              "sync_source_binding")
        closed(encoding, "id schema nativeDescriptor", "sync_codec_identity")
        check(type(encoding["id"]) is str and 0 < len(encoding["id"]) <= 128 and
              encoding["id"].isascii() and all(ord(char) > 32 for char in encoding["id"]), "sync_codec_identity")
        hex_digest(encoding["schema"])
        check(encoding["nativeDescriptor"] == descriptor.native_descriptor_digest, "sync_codec_identity")
        check(len(canonical(binding)) <= 4096 and len(canonical(descriptor.wire())) <= 16384,
              "sync_relay_setup")
        ledger.retain(descriptor)
        retained = True
        return SyncRelay(source, descriptor, binding, native_codec, budgets, ledger, owns_source, credit, _mint=_MINT)
    except BaseException:
        credit.close()
        if retained:
            ledger.release(descriptor)
        raise


class RelayChannel:
    def __init__(self, relay, channel, request, credit, *, _mint=None):
        check(_mint is _MINT, "sync_relay_setup")
        self._relay, self._channel, self._request, self._credit = relay, channel, request, credit
        self._inputs = self._session = self._capsule = self._watch = None
        self._closed, self._close_task, self._busy = False, None, False
        self._sequence, self._binding_digest, self._last_clock = 0, None, None
        self._jobs = set()
        self._output_lock = asyncio.Lock()
        self._output_pin, self._io_failed = None, False

    def _check(self):
        check(not self._closed and not self._channel.closed, "sync_input_retired")
        self._relay._check()

    def input_owner(self):
        self._check()
        return self._inputs

    @admission_boundary
    def begin_acquisition(self, *, deadline_ms):
        self._check()
        deadline = _deadline(deadline_ms)
        check(self._capsule is None, "sync_relay_busy")
        credit = self._relay.ledger.reserve(8192)
        self._capsule = RelayAcquisition(self, deadline, credit, _mint=_MINT)
        return self._capsule

    @async_admission_boundary
    async def watch(self, cursor, *, startup_deadline_ms):
        self._check()
        deadline = _deadline(startup_deadline_ms)
        check(self._watch is None and not self._busy, "sync_relay_busy")
        credit = self._relay.ledger.reserve(16384)
        watch = self._watch = RelayWatch(self, credit, _mint=_MINT)
        try:
            watch._source = self._session.watch(cursor)
            await within_deadline(watch._source.__aenter__(), deadline)
            self._check()
            watch._job = asyncio.create_task(watch._run())
            return watch
        except BaseException:
            await watch.aclose()
            raise

    async def _write(self, prefix, raw, suffix, deadline, live, *, kind):
        # Force drain to mean physical userspace buffer retirement. A bounded
        # chunk/copy allowance is prepaid before write, including partial/error
        # output. Closing the channel retires any failed transport copy first.
        channel, credit = self._channel, None
        view = chunk = None
        code = signal = None
        transport = channel.writer.transport
        limits = transport.get_write_buffer_limits()
        try:
            credit = self._relay.ledger.reserve(2 * 65536 + 8192, encoded=2 * 65536)
            async with channel.lock:
                self._check()
                live()
                transport.set_write_buffer_limits(high=0, low=0)
                for part in (prefix, raw, suffix):
                    view = memoryview(part)
                    for start in range(0, len(view), 65536):
                        live()
                        chunk = view[start:start + 65536]
                        channel.writer.write(chunk)
                        await within_deadline(channel.writer.drain(), deadline)
                        check(boottime_ms() < deadline, "sync_acquisition_deadline")
                        live()
                        self._check()
                        check(transport.get_write_buffer_size() == 0, "sync_relay_output")
                        chunk = None
                    view = None
                size = len(prefix) + len(raw) + len(suffix)
                channel._metrics["sentFrames"] += 1
                channel._metrics["sentBytes"] += size
                channel._count_kind("sent", kind, size)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            view = chunk = raw = prefix = suffix = None
            self._begin_close()
            await finish_owned(asyncio.create_task(channel.close()))
        finally:
            view = chunk = raw = prefix = suffix = None
            try:
                transport.set_write_buffer_limits(high=limits[1], low=limits[0])
            finally:
                if credit is not None:
                    if transport.get_write_buffer_size():
                        # Failed bounded shutdown is quarantined, not reported
                        # as free storage. The sole writer owns this one pin.
                        self._io_failed, self._output_pin = True, credit
                    else:
                        credit.close()
        if signal is not None:
            raise signal
        if code is not None:
            raise ProtocolError(code)

    async def _send_control(self, value, deadline):
        raw = None
        try:
            raw = canonical(value)
            check(len(raw) + 1 <= MAX_PROOF, "sync_relay_setup")
            await self._write(raw, b"", b"\n", deadline, self._check, kind=value["kind"])
        finally:
            raw = value = None

    def _observe(self, header):
        kind = header["kind"]
        tag = _native_tag(header["resultTag"] if kind == "transaction" else header["tag"]) if header.get(
            "resultTag" if kind == "transaction" else "tag") is not None else None
        if tag is not None:
            check(self._binding_digest in (None, tag.binding), "sync_relay_header")
            self._binding_digest = tag.binding
        if kind == "baseline":
            check(binding_digest(header["nativeBinding"], native=True).hex() == tag.binding,
                  "sync_relay_header")
        return tag

    @contextmanager
    def _header(self, raw, *, head=False):
        ticket = document = credit = budget = None
        code = signal = None
        try:
            self._check()
            check(type(raw) is bytes and raw.endswith(b"\n") and raw.count(b"\n") == 1 and
                  b"\r" not in raw and len(raw) <= (MAX_HEAD if head else MAX_NATIVE), "line_framing")
            callback = self._relay._callbacks[1 if head else 0]
            budget = _ScanBudget(self._relay.ledger)
            ticket = callback(raw, budget)
            check(callable(getattr(ticket, "close", None)), "sync_relay_header")
            self._check()
            bound = ticket.header.materialization_bytes
            check(type(bound) is int and bound >= 0, "sync_relay_header")
            budget.finish()
            credit = self._relay.ledger.reserve(bound)
            document = ticket.header.materialize()
            self._check()
            check(type(document) is dict and canonical(document["descriptor"]) ==
                  self._relay.descriptor.native_descriptor, "sync_native_descriptor")
            yield document
        except BaseException as error:
            code, signal, _ = _retire_error(error)
        finally:
            document = raw = None
            if credit is not None:
                credit.close()
            if callable(getattr(ticket, "close", None)):
                ticket.close()
            if budget is not None:
                budget.finish(failed=True)
            ticket = credit = budget = None
        if signal is not None:
            raise signal
        if code is not None:
            raise ProtocolError(code)

    async def _forward(self, data, deadline, live, *, expected=None, challenge=None):
        raw = header = None
        try:
            with relay_bytes(self, data) as raw:
                with self._header(raw, head=challenge is not None) as header:
                    try:
                        return await self._forward_pinned(raw, header, deadline, live, expected=expected,
                                                          challenge=challenge)
                    finally:
                        raw = header = None
        finally:
            raw = header = data = None

    async def _forward_pinned(self, raw, header, deadline, live, *, expected=None, challenge=None):
        # Metadata, serialization scratch and provisional containers are paid
        # before construction; raw remains charged independently by its pin.
        credit = self._relay.ledger.reserve(524288, encoded=131072)
        code = signal = result = None
        try:
            async with self._output_lock:
                live()
                result = await self._emit_pinned(raw, header, deadline, live, expected=expected, challenge=challenge)
        except BaseException as error:
            code, signal, _ = _retire_error(error)
        finally:
            raw = header = expected = challenge = None
            credit.close()
        if signal is not None:
            raise signal
        if code is not None:
            raise ProtocolError(code)
        return result

    async def _emit_pinned(self, raw, header, deadline, live, *, expected=None, challenge=None):
        native = payload = prefix = suffix = None
        kind = header["kind"]
        tag = self._observe(header)
        if expected is not None:
            expected(header)
        binding = decode(self._relay._binding)
        payload = {"descriptor": self._relay.descriptor.wire(), "sourceBinding": binding}
        if challenge is not None:
            check(kind == "head" and header["challenge"] == challenge, "sync_relay_header")
            clock = header["ownerClock"]
            owner_clock(clock)
            local = clock_domain()
            check(clock["uid"] == os.getuid() and clock["bootId"] == local["bootId"] and
                  clock["clockDomain"].replace("[", "").replace("]", "") == local["timeNamespace"],
                  "sync_bridge_clock_binding")
            now = boottime_ms()
            check(now >= clock["boottimeMs"], "sync_bridge_clock_binding")
            scope = tuple(clock[name] for name in ("hostScope", "uid", "ownerEpoch", "bootId", "clockDomain"))
            check(self._last_clock is None or self._last_clock[0] == scope and
                  self._last_clock[1] <= clock["boottimeMs"], "sync_bridge_clock_regression")
            self._last_clock = scope, clock["boottimeMs"]
            remaining = entries(header["attenuation"], 32, "sync_attenuation")
            check(all(type(pair[1]) is int and pair[1] >= 0 for pair in remaining.values()),
                  "sync_receipt_remaining")
            payload.update(protocol=SYNC_PROTOCOL, kind="proof", sourceTag=_source_tag(binding, tag),
                           requestBinding=decode(self._request), challenge=challenge,
                           bridgeId=self._relay.bridge_id, bridgeClock={**local, "boottimeMs": now},
                           remaining=[[pair[0], max(0, pair[1] - (now - clock["boottimeMs"]))]
                                      for pair in remaining.values()])
            field, maximum, overhead = b',"head":', MAX_PROOF, 16384
        elif kind in ("baseline", "transaction"):
            payload.update(kind="material", sourceTag=_source_tag(binding, tag))
            field, maximum, overhead = b',"native":', MAX_MESSAGE, 65536
        else:
            check(kind == "control", "sync_relay_header")
            payload.update(kind="control")
            field, maximum, overhead = b',"native":', MAX_PROOF, MAX_PROOF
        live()
        check(self._sequence < 2**64 - 1, "sync_relay_output")
        sequence = self._sequence + 1
        prefix = (b'{"protocol":"' + SYNC_PROTOCOL.encode() + b'","kind":"delivery","requestBinding":' +
                  self._request + b',"sequence":' + str(sequence).encode() +
                  b',"payload":' + canonical(payload)[:-1] + field)
        suffix = b"}}\n"
        check(len(prefix) + len(suffix) <= overhead and len(prefix) + len(raw) - 1 + len(suffix) <= maximum,
              "sync_relay_output")
        native = memoryview(raw)[:-1]
        await self._write(prefix, native, suffix, deadline, live, kind="delivery")
        self._sequence = sequence
        prefix = suffix = native = None
        return tag

    def _begin_close(self):
        if self._close_task is None:
            self._closed = True
            if self._inputs is not None:
                self._inputs._close()
            if self._capsule is not None:
                self._capsule._retire()
            if self._watch is not None:
                self._watch._retire()
            for job in tuple(self._jobs):
                if job is not asyncio.current_task():
                    job.cancel()
            self._close_task = asyncio.create_task(self._close())

    async def aclose(self):
        self._begin_close()
        await finish_owned(self._close_task)

    async def _close(self):
        await asyncio.gather(*tuple(self._jobs), return_exceptions=True)
        if self._watch is not None:
            await self._watch.aclose()
        if self._session is not None:
            await self._session.aclose()
        await self._channel.close()
        check(self._channel.writer.transport.get_write_buffer_size() == 0, "sync_relay_output")
        if self._io_failed:
            for key, record in tuple(self._inputs._buffers.items()):
                record.consuming = False
                self._inputs._retire(key)
            self._io_failed = False
        if self._output_pin is not None:
            self._output_pin.close()
            self._output_pin = None
        if self._capsule is not None:
            self._capsule._finish()
        self._session = None
        self._relay._channels.discard(self)
        self._credit.close()


class RelayAcquisition:
    def __init__(self, channel, deadline, credit, *, _mint=None):
        check(_mint is _MINT, "sync_relay_setup")
        self._channel, self._deadline, self._credit = channel, deadline, credit
        self._closed, self._job, self._close_task = False, None, None

    def _check(self):
        check(not self._closed and boottime_ms() < self._deadline, "sync_acquisition_deadline")
        self._channel._check()

    async def _run(self, operation, *, head=False):
        channel = self._channel
        try:
            self._check()
            check(not channel._busy and (head or channel._watch is None), "sync_relay_busy")
        except BaseException:
            operation.close()
            raise
        channel._busy = True
        deadline = min(self._deadline, boottime_ms() + 2000) if head else self._deadline
        # Track the operation task itself, so synchronous retirement from its
        # own scanner does not cancel an outer timer task over its exception.
        job = self._job = asyncio.create_task(operation)
        channel._jobs.add(job)
        try:
            await within_deadline(asyncio.shield(job), deadline)
            self._check()
        except BaseException:
            self._retire()
            raise
        finally:
            if not job.done():
                job.cancel()
            await finish_owned(asyncio.gather(job, return_exceptions=True))
            channel._jobs.discard(job)
            self._job, channel._busy = None, False

    @async_admission_boundary
    async def baseline(self):
        await self._run(self._baseline())

    async def _baseline(self):
        packet = data = None
        try:
            packet = await self._channel._session.baseline()
            self._check()
            check(callable(getattr(packet, "close", None)), "sync_relay_header")
            data = packet.data
            check(type(data) is RelayInputRef, "sync_input_owner")
            def compare(header):
                check(header["kind"] in ("baseline", "control") and
                      _plain(packet.tag) == header.get("tag") and _plain(packet.cursor) == header.get("cursor"),
                      "sync_relay_header")
                if header["kind"] == "control":
                    check(packet.status == header["status"] and packet.reason == header["reason"], "sync_relay_header")
            await self._channel._forward(data, self._deadline, self._check, expected=compare)
        finally:
            if callable(getattr(packet, "close", None)):
                packet.close()
            elif packet is not None:
                self._channel._begin_close()
            packet = data = compare = None

    @async_admission_boundary
    async def changes(self, base, *, target, max_transactions=4, max_bytes=8388608):
        check(type(max_transactions) is int and 0 < max_transactions <= 4 and
              type(max_bytes) is int and 0 < max_bytes <= 8388608, "sync_catchup_capacity")
        await self._run(self._changes(_native_tag(base), _native_tag(target), max_transactions, max_bytes))

    async def _changes(self, base, target, count, maximum):
        batch = data = header = raw = None
        try:
            batch = await self._channel._session.changes(base.wire(), target=target.wire(),
                                                        max_transactions=count, max_bytes=maximum)
            self._check()
            if type(batch) is not tuple:
                check(callable(getattr(batch, "close", None)), "sync_relay_header")
                data = batch.data
                check(type(data) is RelayInputRef, "sync_input_owner")
                await self._channel._forward(data, self._deadline, self._check,
                                             expected=lambda value: check(value["kind"] == "control" and
                                                 value["status"] == batch.status and value["reason"] == batch.reason,
                                                 "sync_relay_header"))
                return
            check(len(batch) <= count and all(type(item) is RelayInputRef for item in batch), "sync_catchup_capacity")
            check(sum(item.nbytes for item in batch) <= maximum, "sync_catchup_capacity")
            # All claims are scanned before a prefix is emitted. Keep each pin
            # in an ExitStack through validation and forwarding of the batch.
            from contextlib import ExitStack
            with self._channel._relay.ledger.reserve(32768), ExitStack() as stack:
                frames = []
                try:
                    previous = base
                    for data in batch:
                        raw = stack.enter_context(relay_bytes(self._channel, data))
                        header = stack.enter_context(self._channel._header(raw))
                        check(header["kind"] == "transaction" and _native_tag(header["baseTag"]) == previous,
                              "sync_relay_chain")
                        result = _native_tag(header["resultTag"])
                        check(result.binding == previous.binding and result.generation == previous.generation + 1,
                              "sync_relay_chain")
                        cursor(header["baseCursor"], previous)
                        cursor(header["resultCursor"], result, header["baseCursor"][0])
                        frames.append((raw, header))
                        previous = result
                    check(previous == target, "sync_relay_chain")
                    # Forward using the already held pins; no second consume.
                    for raw, header in frames:
                        await self._channel._forward_pinned(raw, header, self._deadline, self._check)
                finally:
                    frames.clear()
                    raw = header = None
            # The source API has verified its native completion before return;
            # a transport completion control is not fabricated as native JSON.
        finally:
            raw = header = data = None
            if type(batch) is tuple:
                for item in batch:
                    if type(item) is RelayInputRef:
                        item.close()
            elif callable(getattr(batch, "close", None)):
                batch.close()
            elif batch is not None:
                self._channel._begin_close()
            batch = None

    @async_admission_boundary
    async def head_after_nonce(self, challenge):
        credit = self._channel._relay.ledger.reserve(32768, encoded=4096)
        value = None
        try:
            value = _plain(challenge)
            closed(value, "nonce target request", "sync_challenge")
            for name in value:
                hex_digest(value[name])
            check(value["request"] == sha256(self._channel._request).hexdigest() and
                  len(canonical(value)) <= 4096, "sync_challenge")
            await self._run(self._head(value), head=True)
        finally:
            value = challenge = None
            credit.close()

    async def _head(self, challenge):
        data = None
        try:
            data = await self._channel._session.head_after_nonce(challenge)
            self._check()
            await self._channel._forward(data, min(self._deadline, boottime_ms() + 2000), self._check,
                                         challenge=challenge)
        finally:
            if type(data) is RelayInputRef:
                data.close()
            data = challenge = None

    def _retire(self):
        self._closed = True
        if self._job is not None and self._job is not asyncio.current_task():
            self._job.cancel()

    def _finish(self):
        self._credit.close()
        if self._channel._capsule is self:
            self._channel._capsule = None

    async def aclose(self):
        self._retire()
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await finish_owned(self._close_task)

    async def _close(self):
        if self._job is not None:
            await asyncio.gather(self._job, return_exceptions=True)
        self._finish()


class RelayWatch:
    def __init__(self, channel, credit, *, _mint=None):
        check(_mint is _MINT, "sync_relay_setup")
        self._channel, self._credit = channel, credit
        self._source = self._job = self._close_task = None
        self._closed = False

    def _check(self):
        check(not self._closed, "sync_input_retired")
        self._channel._check()

    async def _run(self):
        packet = data = None
        try:
            while True:
                packet = await within_deadline(anext(self._source), boottime_ms() + 5000)
                self._check()
                data = packet if type(packet) is RelayInputRef else packet.data
                await self._channel._forward(data, boottime_ms() + 15000, self._check)
                if packet is not data:
                    packet.close()
                packet = data = None
        except StopAsyncIteration:
            pass
        except BaseException:
            if not self._closed:
                self._channel._begin_close()
            raise
        finally:
            self._closed = True
            if data is not None:
                data.close()
            if packet is not None and packet is not data:
                packet.close()
            packet = data = None

    def _retire(self):
        self._closed = True
        if self._job is not None and self._job is not asyncio.current_task():
            self._job.cancel()

    async def wait_closed(self):
        try:
            if self._job is not None:
                await asyncio.shield(self._job)
        finally:
            await self.aclose()

    async def aclose(self):
        self._retire()
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await finish_owned(self._close_task)

    async def _close(self):
        try:
            if self._job is not None:
                await asyncio.gather(self._job, return_exceptions=True)
            if self._source is not None:
                await self._source.aclose()
        finally:
            self._source = None
            if self._channel._watch is self:
                self._channel._watch = None
            self._credit.close()
