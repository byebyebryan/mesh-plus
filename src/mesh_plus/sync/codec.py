"""Configured native plans and bounded, independently hashed raw framing."""

from contextlib import contextmanager
from hashlib import sha256

from ..protocol import ProtocolError, check
from ._boundary import _retire_error
from .canonical import canonical, decode, decode_reservation
from .model import SPACES, NativeTag, hex_digest
from .streaming import array_spans, object_spans
from .wire import MAX_NATIVE, cursor


@contextmanager
def error_fence():
    """Clear unwound decoder frames before the enclosing credit is refunded."""
    failure = None
    try:
        yield
    except BaseException as error:
        failure = _retire_error(error)
    if failure is not None:
        code, signal, public = failure
        if signal is not None:
            raise signal
        raise public if public is not None else ProtocolError(code)


class _Lease:
    __slots__ = ("_budget", "_credit", "_closing")

    def __init__(self, budget, credit):
        self._budget, self._credit, self._closing = budget, credit, False

    def close(self):
        self._closing = True
        budget = self._budget
        if budget is not None and not budget._calling:
            self._release()

    def _release(self):
        credit, self._credit = self._credit, None
        budget, self._budget = self._budget, None
        if budget is not None:
            budget._leases.pop(id(self), None)
        if credit is not None:
            credit.close()

    def __enter__(self):
        check(self._credit is not None and not self._closing, "sync_reference_retired")
        return self

    def __exit__(self, *_):
        self.close()


class CodecBudget:
    """Revocable close-only credit; refunds wait for callback stack unwind."""

    def __init__(self, ledger):
        self._ledger, self._leases, self._calling = ledger, {}, False

    @property
    def remaining(self):
        check(self._ledger is not None, "sync_reference_retired")
        return self._ledger.maximum - self._ledger.used - self._ledger.reserved

    def reserve(self, amount, *, encoded=0):
        check(self._ledger is not None, "sync_reference_retired")
        check(len(self._leases) < 64, "sync_reservation_capacity")
        credit = self._ledger.reserve(amount, encoded=encoded)
        try:
            lease = _Lease(self, credit)
            self._leases[id(lease)] = lease
            return lease
        except BaseException:
            credit.close()
            raise

    def call(self, callback, *args):
        check(self._ledger is not None and not self._calling, "sync_reentrant_admission")
        self._calling = True
        failure = None
        try:
            return callback(*args)
        except StopIteration:
            raise
        except BaseException as error:
            failure = _retire_error(error)
        finally:
            self._calling = False
            for lease in tuple(self._leases.values()):
                if lease._closing:
                    lease._release()
        callback = args = None
        code, signal, public = failure
        if signal is not None:
            raise signal
        raise public if public is not None else ProtocolError(code)

    def close(self):
        for lease in tuple(self._leases.values()):
            lease.close()
        self._ledger = None


class PlanScope:
    """One plan, one iterator and a separately prepaid structural header."""

    def __init__(self, store, binding, raw, *, head=False):
        self.store, self.binding = store, binding
        self.budget, self.plan = CodecBudget(store.ledger), None
        self.iterator = self.header = self.credit = None
        try:
            store._check()
            callback = binding.codec.head if head else binding.codec.open
            self.plan = self.budget.call(callback, raw, self.budget)
            check(callable(getattr(self.plan, "close", None)), "sync_codec_plan")
            self.header = self._header()
            store._check()
        except BaseException as error:
            failure = _retire_error(error)
            self.close()
            code, signal, public = failure
            if signal is not None:
                raise signal
            raise public if public is not None else ProtocolError(code)

    def _header(self):
        # A codec advertises its detached-copy bound before allocating it.
        ref = self.budget.call(lambda: self.plan.header)
        size = self.budget.call(lambda: ref.materialization_bytes)
        check(type(size) is int and 0 < size <= 4 * 1024 * 1024, "sync_codec_header_capacity")
        self.credit = self.store.ledger.reserve(size)
        document = self.budget.call(ref.materialize)
        check(type(document) is dict, "sync_codec_header")
        return document

    @contextmanager
    def space(self, name, ctx, *, baseline):
        check(self.iterator is None and self.plan is not None, "sync_codec_iterator")
        callback = self.binding.codec.entries if baseline else self.binding.codec.operations
        self.iterator = self.budget.call(callback, self.plan, name, ctx)
        check(self.budget.call(iter, self.iterator) is self.iterator and callable(getattr(self.iterator, "close", None)),
              "sync_codec_iterator")
        try:
            yield self
        finally:
            iterator, self.iterator = self.iterator, None
            if iterator is not None:
                self.budget.call(iterator.close)

    def __iter__(self):
        return self

    def __next__(self):
        self.store._check()
        return self.budget.call(next, self.iterator)

    def close(self):
        # Release no header/codec credit until private exception frames and
        # callback-owned aliases have unwound. close() is terminal/idempotent.
        failure = None
        for name in ("iterator", "plan"):
            owned = getattr(self, name)
            setattr(self, name, None)
            if owned is not None:
                try:
                    self.budget.call(owned.close)
                except BaseException as error:
                    failure = _retire_error(error)
            owned = None
        self.header = None
        if self.credit is not None:
            self.credit.close()
            self.credit = None
        self.budget.close()
        if failure is not None:
            code, signal, public = failure
            if signal is not None:
                raise signal
            raise public if public is not None else ProtocolError(code)


def validate_header(raw, header, descriptor, ledger, *, baseline):
    """Check the logical bounded header against original encoded bytes.

    Codec-specific reference dictionaries remain in the raw transaction hash.
    Only one raw operation value is decoded at a time for that hash; no second
    normalized or decoded roster is retained.
    """
    fields = ({"kind", "descriptor", "nativeBinding", "tag", "cursor"} if baseline else
              {"kind", "descriptor", "nativeBindingDigest", "transactionId", "baseTag", "resultTag",
               "baseCursor", "resultCursor"})
    group = "tables" if baseline else "operations"
    check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_message_capacity")
    spans = object_spans(raw, maximum=16)
    check(set(spans) in (fields | {group}, fields | {group, "receiptRefs"}) and
          set(header) == fields | {group}, "sync_codec_header")
    for name in fields:
        start, end = spans[name]
        check(end - start <= (256 * 1024 if name == "nativeBinding" else 16384), "sync_codec_header_capacity")
        with ledger.reserve(3 * (end - start) + decode_reservation(raw, _start=start, _end=end),
                            encoded=3 * (end - start)), error_fence():
            value = decode(raw[start:end])
            check(canonical(value) == canonical(header[name]), "sync_codec_header")
            value = None
    check(canonical(header["descriptor"]) == descriptor.native_descriptor, "sync_native_descriptor")
    check(header["kind"] == ("baseline" if baseline else "transaction"), "sync_codec_kind")
    check(type(header[group]) is dict and set(header[group]) == set(SPACES), "sync_codec_header")
    check(all(type(rows) is list and (name == "receipts" and baseline and len(rows) <= 32 or not rows)
              for name, rows in header[group].items()), "sync_codec_header")
    if baseline:
        tag = NativeTag.parse(header["tag"])
        check(type(header["nativeBinding"]) is dict, "sync_native_binding")
        cursor(header["cursor"], tag, header["nativeBinding"].get("ownerEpoch"))
        return
    base, result = NativeTag.parse(header["baseTag"]), NativeTag.parse(header["resultTag"])
    check(header["nativeBindingDigest"] == base.binding == result.binding and
          result.generation == base.generation + 1, "sync_transaction_tag")
    before = cursor(header["baseCursor"], base)
    cursor(header["resultCursor"], result, before[0])
    hex_digest(header["transactionId"])
    spaces = object_spans(raw, *spans[group])
    check(set(spaces) == set(SPACES), "sync_operation_registry")

    def parts():
        yield b"{"
        for index, name in enumerate(sorted(set(spans) - {"transactionId"})):
            if index:
                yield b","
            yield canonical(name)
            yield b":"
            if name != group:
                start, end = spans[name]
                with ledger.reserve(2 * (end - start) + decode_reservation(raw, _start=start, _end=end),
                                    encoded=end - start), error_fence():
                    value = decode(raw[start:end])
                    yield canonical(value)
                    value = None
                continue
            yield b"{"
            for number, space in enumerate(sorted(SPACES)):
                if number:
                    yield b","
                yield canonical(space)
                yield b":["
                for row, (start, end) in enumerate(array_spans(raw, *spaces[space])):
                    if row:
                        yield b","
                    with ledger.reserve(2 * (end - start) + decode_reservation(raw, _start=start, _end=end),
                                        encoded=end - start), error_fence():
                        value = decode(raw[start:end], _depth=3)
                        yield canonical(value)
                        value = None
                yield b"]"
            yield b"}"
        yield b"}"

    try:
        size = sum(map(len, parts()))
        digest = sha256(b"mesh-sync-transaction\0" + size.to_bytes(8, "big"))
        for part in parts():
            digest.update(part)
            part = None
        check(digest.hexdigest() == header["transactionId"], "sync_transaction_id")
    finally:
        parts = None  # break recursive scope cells, including held-error paths
