"""Study-only sealed value. Static callback compilation is NOT SDK 1 authority."""

import copy
from dataclasses import dataclass

from mesh_plus.protocol import check, decode_json, encode
from mesh_plus.view import _validated_response


@dataclass(frozen=True)
class Row:
    payload: bytes
    required: frozenset
    expiry: int


@dataclass(frozen=True)
class Value:
    snapshot: bytes
    clock: tuple
    encoded_at: int
    rows: tuple


class Prepared:
    """No public mutable JSON aliases; every exported result owns its bytes."""

    __slots__ = ("_value",)

    def __init__(self, response, profile):
        owned = copy.deepcopy(response)
        _, states = _validated_response(owned, profile)
        snapshot = encode(owned)
        clock = tuple(sorted(owned["mesh"]["reader"]["clock"].items()))
        encoded_at = owned["mesh"]["reader"]["encodedAtMs"]
        rows = []
        for host in owned["mesh"]["hosts"]:
            if host["viewState"] != "current" or host["delivery"]["status"] != "ready":
                continue
            state = states[host["hostId"]]
            native = {(r["sourceId"], r["component"]) for r in state.receipts if r["health"] in {"current", "partial"}}
            leases = {(r["sourceId"], r["component"]): r["expiresAtMs"] for r in host["receipts"] if r["health"] in {"current", "partial"}}
            # Explicit experimental assumption: receipts/eligibility are static
            # functions of one admitted native value. SDK 1 does not opt in.
            for record in state.records:
                required = profile.record_receipts(record, state)
                check(required is None or (type(required) is frozenset and all(type(k) is tuple and len(k) == 2 and
                    all(type(v) is str for v in k) for k in required)), "record_receipt_keys")
                if required and required <= native and required <= leases.keys() and profile.record_eligible(record, state):
                    rows.append(Row(encode(record), required, min(leases[key] for key in required)))
        self._value = Value(snapshot, clock, encoded_at, tuple(rows))

    @property
    def rows(self):
        return () if self._value is None else self._value.rows

    @property
    def encoded_at(self):
        return self._value.encoded_at

    def snapshot(self):
        check(self._value is not None, "prepared_retired")
        return decode_json(self._value.snapshot, 16 * 1024 * 1024)

    def current(self, now, clock):
        value = self._value
        if value is None:
            return []
        check(type(now) is int and now >= value.encoded_at and tuple(sorted(clock.items())) == value.clock, "reader_clock_scope")
        return [decode_json(row.payload) for row in value.rows if row.expiry > now]

    def invalidate(self):
        self._value = None


class PreparedGuard:
    """Study lifecycle wiring; legacy ReadGuard and SDK runtime stay unchanged."""

    def __init__(self, domain, request_id, profile):
        from mesh_plus.api import ReadGuard
        self._guard = ReadGuard(domain, request_id, profile=profile)
        self._profile = profile
        self._prepared = None

    def accept(self, frame):
        try:
            self._guard.accept(frame)
            if self._guard.closed or self._guard.needs_resync:
                self._retire()
            elif "mesh" in frame and frame["mesh"]["kind"] not in {"heartbeat", "gap"}:
                replacement = Prepared(self._guard.view, self._profile)
                self._retire()
                self._prepared = replacement
        except Exception:
            self.disconnect()
            raise
        return frame

    def _retire(self):
        if self._prepared is not None:
            self._prepared.invalidate()
        self._prepared = None

    def current(self, now, clock):
        return [] if self._prepared is None else self._prepared.current(now, clock)

    def disconnect(self):
        self._retire()
        self._guard.disconnect()
