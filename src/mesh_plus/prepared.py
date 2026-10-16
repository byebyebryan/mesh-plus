"""Explicit opt-in static preparation, independent of the frozen wire contract.

Installed owner code promises generation-static rules. This is not a sandbox
or automatic certification of an existing StateProfile's callbacks.
"""

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from .admission import AdmittedResponse
from .protocol import check, decode_json, encode
from .state import ProfileDescriptor, ReceiptKey, resolve_profile
from .view import ReadGuard, plain_json

PREPARATION_INTERFACE_VERSION = 1
SELECTION_INTERFACE_VERSION = 1
_CAPACITY = 16 * 1024 * 1024


@dataclass(frozen=True)
class PreparationDescriptor:
    interface_version: int
    profile: ProfileDescriptor
    implementation_id: str


@dataclass(frozen=True)
class PreparationState:
    """Borrowed deeply immutable native facts; JSON arrays become tuples."""

    owner: Mapping
    records: tuple
    clock: Mapping
    publisher: str
    emitted_ms: int
    receipts: tuple


@dataclass(frozen=True)
class PreparedRule:
    identity: tuple[str | int, ...]
    required: frozenset[ReceiptKey] | None
    eligible: bool


@dataclass(frozen=True)
class SelectionRule:
    """Generation-static projection decision; summary is optional consumer JSON."""

    selected: bool
    summary: dict | None


class StatePreparation(Protocol):
    descriptor: PreparationDescriptor

    def prepare_rules(self, state: PreparationState) -> tuple[PreparedRule, ...]: ...


def _profile_matches(actual, expected):
    return (isinstance(actual, ProfileDescriptor) and actual == expected and
            all(type(getattr(actual, key)) is int for key in ("sdk_version", "native_version", "frame_bytes")))


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if type(value) in {list, tuple}:
        return tuple(_freeze(child) for child in value)
    check(type(value) in {str, int, float, bool, type(None)}, "preparation_json")
    return value


@dataclass(frozen=True)
class _Row:
    payload: bytes
    expiry: int | None


@dataclass(frozen=True)
class _Generation:
    header: bytes
    rows: tuple[_Row, ...]
    clock: tuple
    encoded_at: int


class _OwnedAdmission(ReadGuard):
    """Shares full admission/order checks, never retains an exposed raw view."""

    admitted = None
    pending = None

    def _admit(self, frame):
        self.admitted = self.pending if self.pending is not None else super()._admit(frame)
        return self.admitted

    def _retain(self, frame):
        return None


class PreparedReadGuard:
    """One serialized generation; accept failures revoke and close this guard.

    Methods are synchronous and must be serialized by the caller. No I/O,
    coroutine, background task, or implicit transport-failure detector is owned.
    Reconnect or installed preparation/profile changes require a fresh guard.
    """

    __slots__ = ("_guard", "_profile", "_preparation", "_descriptor", "_compile", "_generation", "_accepting")

    def __init__(self, domain, request_id, *, profile, preparation, host_ids=None):
        self._profile = resolve_profile(domain, profile)
        actual = getattr(preparation, "descriptor", None)
        check(type(actual) is PreparationDescriptor and type(actual.interface_version) is int and
              actual.interface_version == PREPARATION_INTERFACE_VERSION and
              _profile_matches(actual.profile, self._profile.descriptor) and
              type(actual.implementation_id) is str and 0 < len(actual.implementation_id) <= 256,
              "preparation_descriptor")
        self._compile = getattr(preparation, "prepare_rules", None)
        check(callable(self._compile), "preparation_interface")
        self._descriptor = actual
        self._preparation = preparation
        self._guard = _OwnedAdmission(domain, request_id, profile=profile, host_ids=host_ids)
        self._generation = None
        self._accepting = False

    def _binding(self):
        try:
            actual = self._preparation.descriptor
            check(_profile_matches(self._profile.descriptor, self._descriptor.profile) and
                  type(actual) is PreparationDescriptor and type(actual.interface_version) is int and
                  _profile_matches(actual.profile, self._descriptor.profile) and actual == self._descriptor and
                  self._preparation.prepare_rules == self._compile, "preparation_binding")
        except BaseException:
            self.disconnect()
            raise

    def _prepare(self, frame, states):
        rows = []
        for host in frame["mesh"]["hosts"]:
            if host["owner"] is None:
                continue
            state = states[host["hostId"]]
            identities = tuple(self._profile.record_identity(record) for record in state.records)
            frozen = PreparationState(_freeze(state.owner), _freeze(state.records), _freeze(state.clock),
                                      state.publisher, state.emitted_ms, _freeze(state.receipts))
            rules = self._compile(frozen)
            check(type(rules) is tuple and len(rules) == len(state.records), "preparation_rule_count")
            known = {(r["sourceId"], r["component"]) for r in state.receipts}
            native = {(r["sourceId"], r["component"]) for r in state.receipts
                      if r["health"] in {"current", "partial"}}
            leases = {(r["sourceId"], r["component"]): r["expiresAtMs"] for r in host["receipts"]
                      if r["health"] in {"current", "partial"}}
            for record, identity, rule in zip(state.records, identities, rules):
                check(type(rule) is PreparedRule and type(rule.identity) is tuple and
                      all(type(part) in {str, int} for part in rule.identity) and rule.identity == identity and
                      type(rule.eligible) is bool, "preparation_rule_identity")
                required = rule.required
                check(required is None or (type(required) is frozenset and all(
                    type(key) is tuple and len(key) == 2 and all(type(part) is str for part in key)
                    for key in required)), "preparation_receipt_keys")
                check(required is None or required <= known, "preparation_receipt_scope")
                expiry = None
                if (host["viewState"] == "current" and host["delivery"]["status"] == "ready" and
                        rule.eligible and required and required <= native and required <= leases.keys()):
                    expiry = min(leases[key] for key in required)
                rows.append(_Row(encode(record), expiry))
        header = encode({**frame, "sessions": []})
        check(len(header) + sum(len(row.payload) + 1 for row in rows) <= _CAPACITY,
              "prepared_capacity")
        reader = frame["mesh"]["reader"]
        return _Generation(header, tuple(rows), tuple(sorted(reader["clock"].items())), reader["encodedAtMs"])

    def accept(self, frame):
        """Admit exactly once before compilation; no partial publication or fallback."""
        if self._accepting:
            self.disconnect()
            check(False, "prepared_reentrant")
        try:
            self._accepting = True
            self._binding()
            if type(frame) is AdmittedResponse:
                owned, self._guard.pending = frame._open(self._profile)
            else:
                owned = copy.deepcopy(frame)
            self._guard.accept(owned)
            if self._guard.closed or self._guard.needs_resync:
                self._generation = None
            elif owned["mesh"]["kind"] not in {"heartbeat", "gap"}:
                replacement = self._prepare(owned, self._guard.admitted)
                self._binding()
                check(not self._guard.closed, "prepared_retired")
                self._generation = replacement
        except BaseException:
            self.disconnect()
            raise
        finally:
            self._guard.admitted = None
            self._guard.pending = None
            self._accepting = False
        return frame

    def current(self, now_ms, clock):
        value = self._current_generation(now_ms, clock)
        if value is None:
            return []
        return [decode_json(row.payload, _CAPACITY) for row in value.rows
                if row.expiry is not None and row.expiry > now_ms]

    def _current_generation(self, now_ms, clock):
        self._binding()
        value = self._generation
        if value is None:
            return None
        try:
            check(type(now_ms) is int and now_ms >= value.encoded_at and type(clock) is dict and
                  clock == dict(value.clock), "reader_clock_scope")
        except BaseException:
            self.disconnect()
            raise
        return value

    def select(self, classify):
        """Register an explicit static-per-generation selector over every row."""
        self._binding()
        check(callable(classify), "selection_interface")
        return PreparedSelection(self, classify)

    def snapshot(self):
        """A fresh raw export, or None before a baseline/after retirement."""
        self._binding()
        value = self._generation
        if value is None:
            return None
        result = decode_json(value.header, _CAPACITY)
        result["sessions"] = [decode_json(row.payload, _CAPACITY) for row in value.rows]
        return result

    def context(self):
        """Detached aggregate header with sessions=[]; never decodes row bodies."""
        self._binding()
        value = self._generation
        return None if value is None else decode_json(value.header, _CAPACITY)

    def disconnect(self):
        self._generation = None
        self._guard.admitted = None
        self._guard.pending = None
        self._guard.disconnect()


class PreparedSelection:
    """Selected bodies and whole-roster summaries, with independent row expiry.

    classify receives a deeply immutable record once per generation, including
    historical/ineligible rows. It returns SelectionRule. current returns two
    detached lists: selected native rows, and non-null summaries of current rows.
    Policy, summary meaning and output limits belong to the installed consumer.
    """

    __slots__ = ("_guard", "_classify", "_generation", "_rows", "_selecting")

    def __init__(self, guard, classify):
        self._guard, self._classify = guard, classify
        self._generation, self._rows, self._selecting = None, (), False

    def _compile(self, generation):
        rows, size = [], 0
        for row in generation.rows:
            rule = self._classify(_freeze(decode_json(row.payload, _CAPACITY)))
            check(type(rule) is SelectionRule and type(rule.selected) is bool and
                  (rule.summary is None or (type(rule.summary) is dict and plain_json(rule.summary))), "selection_rule")
            summary = None if rule.summary is None else encode(rule.summary)
            # Bound retained extra projection data independently of native bytes.
            size += 0 if summary is None else len(summary) + 1
            check(size <= _CAPACITY, "selection_capacity")
            rows.append((row, rule.selected, summary))
        check(self._guard._generation is generation, "selection_retired")
        self._guard._binding()
        self._generation, self._rows = generation, tuple(rows)

    def current(self, now_ms, clock):
        if self._selecting:
            self._guard.disconnect()
            check(False, "selection_reentrant")
        try:
            self._selecting = True
            value = self._guard._current_generation(now_ms, clock)
            if value is None:
                self._generation, self._rows = None, ()
                return [], []
            if value is not self._generation:
                self._compile(value)
            rows, summaries = [], []
            for row, selected, summary in self._rows:
                if row.expiry is not None and row.expiry > now_ms:
                    if selected:
                        rows.append(decode_json(row.payload, _CAPACITY))
                    if summary is not None:
                        summaries.append(decode_json(summary, _CAPACITY))
            return rows, summaries
        except BaseException:
            self._generation, self._rows = None, ()
            self._guard.disconnect()
            raise
        finally:
            self._selecting = False
