"""Owned, proof-bound per-source cache. Material admission grants no authority."""

import contextlib
import os
import re
import secrets
import time
from dataclasses import dataclass, replace
from hashlib import sha256

from ..evidence import clock_domain
from ..protocol import check
from ..view import remote_expiry
from ._boundary import MovedHead, admission_boundary
from ._constants import SYNC_PROTOCOL
from .budget import AllocationLedger, OwnedUnit
from .canonical import Atom, canonical, decode, thaw
from .commitment import ABSENT, binding_digest, source_root
from .context import reference
from .inputs import OwnedInputRef, input_bytes, mint_input_owner
from .model import HeadRules, NativeTag, OriginalReceipt, SourceTag
from .ordered import OrderedMap, index_key
from .reconstruction import BudgetRef, PublicIndexRef, ReconstructionStore, VisitMeter
from .wire import (
    MAX_NATIVE,
    MAX_PROOF,
    closed,
    decode_reservation,
    entries,
    owner_clock,
    read_native,
)


def _now():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1_000_000


def _owner_clock_scope(value):
    # Provider/namespace context generations are deliberately excluded. They
    # can change a native binding without changing the owner's clock scope.
    return tuple(value[name] for name in ("hostScope", "uid", "ownerEpoch", "bootId", "clockDomain"))


@dataclass(frozen=True, slots=True)
class SyncBudgets:
    decoded_bytes: int = 64 * 1024 * 1024
    encoded_bytes: int = 32 * 1024 * 1024

    def __post_init__(self):
        check(type(self.decoded_bytes) is int and 0 < self.decoded_bytes <= 64 * 1024 * 1024,
              "sync_decoded_budget")
        check(type(self.encoded_bytes) is int and 0 < self.encoded_bytes <= 32 * 1024 * 1024,
              "sync_encoded_budget")


def source_binding(host, source, descriptor):
    check(type(host) is str and 0 < len(host) <= 256, "sync_host")
    check(type(source) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", source), "sync_source")
    return {"host": host, "source": source, "profile": descriptor.profile_id,
            "profileSchema": descriptor.profile_schema_digest,
            "nativeDescriptor": descriptor.native_descriptor_digest}


class CandidateRef(OwnedUnit):
    """Cache-minted identity capability, never an owning pointer to a root."""

    __slots__ = ("_owner", "_permit", "_tag")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync candidate")
        object.__setattr__(self, name, value)

    def __init__(self, owner, permit, tag):
        self._owner, self._permit, self._tag = owner, permit, tag

    @property
    def tag(self):
        self._owner._candidate(self)
        return self._tag

    def owned_children(self):
        # The owner is a lookup capability, not an owned child graph.
        return self._permit, self._tag


class ViewRef:
    __slots__ = ("_owner", "_permit", "_tag")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync view")
        object.__setattr__(self, name, value)

    def __init__(self, owner, permit, tag):
        self._owner, self._permit, self._tag = owner, permit, tag

    @property
    def tag(self):
        with self._owner._lock:
            self._owner._view_root(self._permit)
            return self._tag

    def lookup(self, space, key):
        location = ("view", "table", space, canonical(key))
        return reference(self._owner, self._permit, location)

    def index(self, name):
        return PublicIndexRef(self._owner, self._permit, "view", name)

    def context(self, now_ms, clock):
        return self._owner._context(self._permit, now_ms, clock)

    def changes(self, since):
        with self._owner._lock:
            root = self._owner._view_root(self._permit)
            check(self._permit == self._owner._view_permit, "sync_unconfirmed_view")
            if since == self._tag:
                return ChangeSet(self._tag, self._tag, (), (), ())
            if type(since) is not SourceTag or root.change_base != since.native or since != self._owner._tag(since.native):
                return ResyncRequired("change_base_evicted")
            return ChangeSet(since, self._tag,
                             tuple((item.space, thaw(item.key.value), item.removed) for item in root.changes),
                             tuple(thaw(key.value) for key in root.affected_scopes),
                             tuple(thaw(item.value) for item in root.invalidations))

    def export_committed(self):
        with self._owner._lock:
            self._owner._view_root(self._permit)
            return self._owner.profile.export_committed(self)


@dataclass(frozen=True, slots=True)
class ResyncRequired:
    reason: str


@dataclass(frozen=True, slots=True)
class ChangeSet:
    base: SourceTag
    result: SourceTag
    keys: tuple
    affected_scopes: tuple
    invalidations: tuple


@dataclass(frozen=True, slots=True)
class _Confirmation(OwnedUnit):
    owner_clock: Atom
    receipts: tuple
    expiries: tuple
    received_ms: int
    permit: str

    def owned_children(self):
        return self.owner_clock, self.receipts, self.expiries, self.received_ms, self.permit


@dataclass(frozen=True, slots=True)
class _History(OwnedUnit):
    known: NativeTag | None = None
    retired: tuple = ()
    clock: tuple | None = None
    transactions: tuple = ()

    def owned_children(self):
        return self.known, self.retired, self.clock, self.transactions


@dataclass(frozen=True, slots=True)
class PublicCommitContext:
    view: ViewRef
    descriptor: object
    binding: object
    tag: SourceTag
    original_receipts: object
    budget: BudgetRef


class OwnedSyncCache:
    def __init__(self, profile, source_binding, budgets=None, *, request_binding=None,
                 ledger=None, local_owner=False, _now_ms=None, _clock=None):
        budgets = SyncBudgets() if budgets is None else budgets
        check(type(budgets) is SyncBudgets and type(source_binding) is dict, "sync_cache_configuration")
        expected = globals()["source_binding"](source_binding.get("host"), source_binding.get("source"), profile.descriptor)
        check(canonical(source_binding) == canonical(expected), "sync_source_binding")
        self.profile, self.descriptor = profile, profile.descriptor
        self.ledger = (AllocationLedger(budgets.decoded_bytes, encoded_maximum=budgets.encoded_bytes)
                       if ledger is None else ledger)
        self._binding = Atom.own(expected)
        self._request = Atom.own({"readerEpoch": secrets.token_hex(16)} if request_binding is None else request_binding)
        check(len(self._request.encoded) <= 4096, "sync_request_binding_capacity")
        self._binding_digest = binding_digest(expected, native=False).hex()
        self._clock = Atom.own(clock_domain() if _clock is None else _clock)
        self._now_ms = _now if _now_ms is None else _now_ms
        self.local_owner = local_owner
        self.store = ReconstructionStore(profile, host=expected["host"], ledger=self.ledger)
        self._lock = self.store._lock
        self._metadata = (self._binding, self._request, self._clock, self._binding_digest)
        self._history = None
        retained = False
        try:
            self.ledger.retain(self._metadata)
            retained = True
            self._replace_history()
        except BaseException:
            if retained:
                self.ledger.release(self._metadata)
            self.store.close()
            raise
        self._candidate_ref = self._view_permit = self._proof = self._proof_context = self._confirmation = None
        self.reason = "unconfirmed"
        self._closed = False
        self._acquisition = None
        self._inputs = None
        self._confirming = self._retired_candidate = False

    def _replace_history(self, **changes):
        old = self._history
        with self.ledger.reserve(8192) as reservation:
            history = replace(_History() if old is None else old, **changes)
            self.ledger.retain(history, reservation=reservation)
        self._history = history
        self._known_head, self._retired_bindings = history.known, history.retired
        self._last_head_clock, self._transaction_tokens = history.clock, history.transactions
        if old is not None:
            self.ledger.release(old)

    def _check(self):
        check(not self._closed, "sync_cache_closed")
        try:
            self.store._check()
        except Exception:
            self.close()
            raise

    @admission_boundary
    def input_owner(self):
        with self._lock:
            self._check()
            if self._inputs is None or self._inputs._closed:
                self._inputs = mint_input_owner(self)
            return self._inputs

    def _tag(self, native):
        return SourceTag(native, self._binding_digest,
                         source_root(thaw(self._binding.value), bytes.fromhex(native.root)).hex())

    def _candidate(self, candidate):
        with self._lock:
            self._check()
            check(type(candidate) is CandidateRef and candidate is self._candidate_ref and candidate._owner is self,
                  "sync_candidate_retired")
            root = self.store.candidate if self.store.candidate is not None else self.store.current
            check(root is not None and self._tag(root.tag) == candidate._tag, "sync_candidate_retired")
            return root

    def _mint(self, root):
        check(not self._retired_candidate or root is not self.store.candidate, "sync_candidate_retired")
        with self.ledger.allocations(), self.ledger.reserve(8192) as reservation:
            candidate = CandidateRef(self, secrets.token_hex(16), self._tag(root.tag))
            self.ledger.retain(candidate, reservation=reservation)
        if self._candidate_ref is not None:
            self.ledger.release(self._candidate_ref)
        self._candidate_ref = candidate
        return self._candidate_ref

    def _discard_candidate(self):
        if self._candidate_ref is not None:
            self.ledger.release(self._candidate_ref)
        self._candidate_ref = None
        if self.store.candidate is not None:
            if self._confirming:
                # Revocation invalidates capabilities immediately. The compact
                # proof still borrows this graph on its synchronous frames:
                # keep the existing stage slot and charge, without reclaiming
                # a roster inside the nonce operation. The next material entry
                # or explicit owning close retires it outside confirmation.
                self._retired_candidate = True
            else:
                self.ledger.release(self.store.candidate)
                self.store.candidate = None
                self._retired_candidate = False

    @contextlib.contextmanager
    def _material_entry(self):
        check(not self._confirming, "sync_reentrant_admission")
        if self._retired_candidate:
            self._discard_candidate()
        yield

    @contextlib.contextmanager
    def _confirmation_entry(self):
        check(not self._confirming, "sync_reentrant_admission")
        self._confirming = True
        try:
            yield
        finally:
            self._confirming = False

    def revoke(self, reason):
        with self._lock:
            check(type(reason) is str and 0 < len(reason) <= 256, "sync_revoke_reason")
            if self._proof is not None:
                self.ledger.release(self._proof[1])
            self._view_permit = self._proof = self._proof_context = None
            self.reason = reason
            self.store._arena.clear()
            if self._confirmation is not None:
                self.ledger.release(self._confirmation)
                self._confirmation = None

    @admission_boundary
    def admit_baseline(self, raw):
        with self._lock, self._material_entry(), input_bytes(self, raw) as (raw, prepaid):
            self._check()
            self.revoke("baseline_pending")
            self._discard_candidate()
            self._replace_history(transactions=())
            # A replacement has no readable old root after revocation. Retire
            # it before cold/recovery admission instead of retaining two full
            # rosters during parsing. Deltas retain their immutable base.
            self.store.retire_material()
            retained_input = False
            try:
                from .streaming import baseline_header
                check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_message_capacity")
                if not prepaid:
                    self.ledger.retain(raw)
                    retained_input = True
                document, reservation = baseline_header(raw, self.descriptor, self.ledger)
                with reservation:
                    root = self.store.stage_baseline(document["nativeBinding"], NativeTag.parse(document["tag"]),
                                                     tuple(document["cursor"]), document["tables"])
                return self._mint(root)
            except BaseException:
                self._discard_candidate()
                self.revoke("invalid_baseline")
                raise
            finally:
                if retained_input:
                    self.ledger.release(raw)
                # Streaming table adapters borrow the complete input. Retire
                # those aliases before the enclosing owned-input pin refunds.
                document = reservation = root = raw = None

    @admission_boundary
    def stage(self, raw):
        with self._lock, self._material_entry(), input_bytes(self, raw) as (raw, prepaid):
            self._check()
            retained_input = False
            try:
                check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_message_capacity")
                if not prepaid:
                    self.ledger.retain(raw)
                    retained_input = True
                from .transactions import transaction_input
                with self.ledger.allocations():
                    document, reservation = transaction_input(raw, self.descriptor, self.ledger)
                    with reservation:
                        return self._stage_document(document)
            except BaseException:
                self._discard_candidate()
                self.revoke("invalid_transaction")
                raise
            finally:
                if retained_input:
                    self.ledger.release(raw)
                document = reservation = raw = None

    def _stage_document(self, document):
        before = self.store.candidate if self.store.candidate is not None else self.store.current
        token = document["transactionId"], tuple(document["resultTag"])
        if token in self._transaction_tokens and before is not None and before.tag.wire() == document["resultTag"]:
            # Exact canonical content is committed by transactionId.
            # Recognition does not readmit or refresh a lease.
            return self._candidate_ref if self._candidate_ref is not None else self._mint(before)
        self.revoke("head_changed")
        check(before is not None and tuple(document["baseCursor"]) == before.cursor, "sync_wrong_base_cursor")
        root = self.store.stage_delta(NativeTag.parse(document["baseTag"]),
                                      NativeTag.parse(document["resultTag"]), tuple(document["resultCursor"]),
                                      document["operations"])
        self._replace_history(transactions=(*self._transaction_tokens[-3:], token))
        return self._mint(root)

    @admission_boundary
    def stage_batch(self, base, frames):
        with self._lock, self._material_entry():
            check(type(frames) is tuple and 0 < len(frames) <= 4 and
                  all(type(raw) in (bytes, OwnedInputRef) for raw in frames),
                  "sync_catchup_capacity")
            retained = False
            bare = None
            try:
                self._check()
                check(sum(len(raw) if type(raw) is bytes else raw.nbytes for raw in frames) <= 8 * 1024 * 1024,
                      "sync_catchup_capacity")
                staged = self.store.candidate
                before = staged if staged is not None and base == self._tag(staged.tag) else self.store.current
                check(type(base) is SourceTag and before is not None and base == self._tag(before.tag), "sync_wrong_base")
                if before is not staged:
                    self._discard_candidate()
                # Own the bounded batch container and all legacy bare inputs.
                # Sealed buffers keep their existing reservations throughout.
                with self.ledger.reserve(1024):
                    bare = tuple(raw for raw in frames if type(raw) is bytes)
                    if bare:
                        self.ledger.retain(bare)
                        retained = True
                    for raw in frames:
                        candidate = self.stage(raw)
                    return candidate
            except BaseException:
                self._discard_candidate()
                raise
            finally:
                if retained:
                    self.ledger.release(bare)
                for raw in frames:
                    if type(raw) is OwnedInputRef:
                        raw.close()

    def _proof_request(self, candidate, *, deadline_ms=None):
        """Owned transport calls immediately before sending, never proof data."""
        with self._lock:
            self._candidate(candidate)
            challenge = {"nonce": secrets.token_hex(32), "target": sha256(canonical(candidate._tag.wire())).hexdigest(),
                         "request": sha256(self._request.encoded).hexdigest()}
            check(deadline_ms is None or type(deadline_ms) is int, "sync_acquisition_deadline")
            with self.ledger.allocations():
                owned = Atom.own(challenge)
                self.ledger.retain(owned)
            if self._proof is not None:
                self.ledger.release(self._proof[1])
            self._proof = candidate, owned, self._now_ms(), deadline_ms
            return challenge

    def _observe_head(self, actual):
        check(type(actual) is NativeTag, "sync_tag")
        known = self._known_head
        check(actual.binding not in self._retired_bindings, "sync_owner_retired")
        if known is not None and actual.binding == known.binding:
            check(actual.generation > known.generation or actual == known, "sync_head_regression")
        retired = self._retired_bindings
        if known is not None and actual.binding != known.binding:
            check(len(self._retired_bindings) < 4, "sync_owner_history_capacity")
            retired = (*retired, known.binding)
        self._replace_history(known=actual, retired=retired)

    def _view_root(self, permit):
        self._check()
        if self._proof_context is not None and permit == self._proof_context[0]:
            return self._proof_context[1]
        check(self._view_permit is not None and permit == self._view_permit and self._confirmation is not None,
              "sync_view_retired")
        return self.store.current

    @contextlib.contextmanager
    def _active_root(self, permit):
        with self._lock:
            root = self._view_root(permit)
            with self.store._arena.active():
                yield root

    def _atom_at(self, root, permit, location):
        side, kind, space, encoded = location
        check(side == "view", "sync_reference_side")
        if kind == "binding":
            return root.binding
        if kind == "head":
            check(self._proof_context is not None and permit == self._proof_context[0], "sync_reference_retired")
            return self._proof_context[2]
        maps = dict(root.tables if kind == "table" else root.indexes)
        table = maps.get(space)
        leaf = ABSENT if table is None else (table.find(decode(encoded)) if type(table) is OrderedMap
                                            else table.find_encoded(encoded))
        return ABSENT if leaf is ABSENT else leaf.atom

    @contextlib.contextmanager
    def peek(self, permit, location):
        with self._active_root(permit) as root:
            if self._proof_context is not None and permit == self._proof_context[0]:
                self._proof_context[3].charge()
            yield self._atom_at(root, permit, location)

    @contextlib.contextmanager
    def borrow(self, permit, location, path):
        with self.peek(permit, location) as atom:
            value = atom if atom is ABSENT or atom is None else atom.value
            for part in path:
                value = value[part]
            yield value

    def index_next(self, permit, side, name, rank, prefix):
        with self._lock:
            root = self._view_root(permit)
            table = dict(root.indexes).get(name)
            if table is None:
                return None
            if rank is None:
                rank = table.lower_bound(prefix) if prefix is not None and type(table) is OrderedMap else 0
            while rank < len(table):
                leaf = table.leaf_at(rank)
                rank += 1
                key = index_key(leaf) if type(table) is OrderedMap else decode(leaf.key)
                if self._proof_context is not None and permit == self._proof_context[0]:
                    self._proof_context[3].charge(iteration=True)
                if prefix is None or key[:len(prefix)] == prefix:
                    return rank, key
                if type(table) is OrderedMap:
                    return None
            return None

    def materialization_budget(self, permit, location):
        with self._lock:
            root = self._view_root(permit)
            atom = self._atom_at(root, permit, location)
            if self._proof_context is not None and permit == self._proof_context[0]:
                self._proof_context[3].charge()
            return 0 if atom is None or atom is ABSENT else atom.copy_budget

    @admission_boundary
    def confirm(self, candidate, proof, clock):
        with self._lock, self._confirmation_entry(), input_bytes(self, proof) as (proof, _), self.ledger.allocations():
            retained = pending = None
            try:
                root = self._candidate(candidate)
                pending, self._proof = self._proof, None  # consume even failed attempts
                check(pending is not None and pending[0] is candidate, "sync_missing_proof_request")
                with self.ledger.reserve(decode_reservation(proof, MAX_PROOF)):
                    document = decode(proof, MAX_PROOF)
                    closed(document, "protocol kind descriptor sourceBinding sourceTag requestBinding challenge bridgeId bridgeClock head remaining",
                           "sync_proof_shape")
                    check(document["protocol"] == SYNC_PROTOCOL and document["kind"] == "proof" and
                          canonical(document["descriptor"]) == canonical(self.descriptor.wire()), "sync_proof_descriptor")
                    check(canonical(document["sourceBinding"]) == self._binding.encoded and
                          canonical(document["requestBinding"]) == self._request.encoded and
                          canonical(document["challenge"]) == pending[1].encoded, "sync_proof_binding")
                    head_raw = canonical(document["head"])
                    check(len(proof) - len(head_raw) <= 16384, "sync_proof_envelope_capacity")
                    head = read_native(head_raw, self.descriptor)
                    check(head["kind"] == "head", "sync_expected_head")
                    check(canonical(head["challenge"]) == pending[1].encoded, "sync_nonce")
                    actual = NativeTag.parse(head["tag"])
                    check(canonical(document["sourceTag"]) == canonical(self._tag(actual).wire()), "sync_proof_source_root")
                    owner_clock(head["ownerClock"])
                    check(head["ownerClock"]["hostScope"] == self._binding.value["host"], "sync_owner_clock_host")
                    self._observe_head(actual)
                    if actual != root.tag:
                        raise MovedHead(actual)
                    native_binding = thaw(root.binding.value)
                    owner_clock(head["ownerClock"], native_binding)
                    observed = head["ownerClock"]["boottimeMs"]
                    clock_scope = _owner_clock_scope(head["ownerClock"])
                    previous_clock = self._last_head_clock
                    check(previous_clock is None or previous_clock[0] != clock_scope or
                          previous_clock[1] <= observed, "sync_head_clock_regression")
                    self._head_matches(root, head)
                    rules = self._head_rules(root, candidate._tag, head)
                    check(self._candidate(candidate) is root, "sync_candidate_retired")
                    result = self._leases(root, head, document, rules, pending[2], clock)
                    self.ledger.retain(result)
                    retained = result
                    self._replace_history(clock=(clock_scope, observed, document["bridgeClock"]["boottimeMs"]))
                self._check()
                check(self._now_ms() < pending[2] + 2000, "sync_proof_deadline")
                check(pending[3] is None or self._now_ms() < pending[3], "sync_acquisition_deadline")
                if self.store.candidate is root:
                    self.store.advance_material()
                if self._confirmation is not None:
                    self.ledger.release(self._confirmation)
                self._confirmation = result
                retained = None
                self._view_permit = result.permit
                self.reason = "confirmed"
                return ViewRef(self, self._view_permit, candidate._tag)
            except BaseException:
                if retained is not None:
                    self.ledger.release(retained)
                self.revoke("proof_failed")
                raise
            finally:
                if pending is not None:
                    self.ledger.release(pending[1])
                proof = None

    def _head_matches(self, root, head):
        tables = dict(root.tables)
        for name, field in (("receipts", "originalReceipts"), ("cohorts", "cohortHeads")):
            values = entries(head[field], 32, "sync_head_entries")
            check(len(values) == len(tables[name]), "sync_head_root_context")
            for key, value in values.values():
                if name == "cohorts":
                    check(type(value) is dict, "sync_head_cohort")
                    value = {**value, "receipt": key}
                leaf = tables[name].find(key)
                check(leaf is not ABSENT and leaf.atom.encoded == canonical(value), "sync_head_root_context")

    def _head_rules(self, root, tag, head):
        permit = secrets.token_hex(16)
        budget = BudgetRef(self.ledger)
        self._proof_context = permit, root, Atom.own(head), VisitMeter(4096)
        try:
            view = ViewRef(self, permit, tag)
            ctx = PublicCommitContext(view, self.descriptor, reference(self, permit, ("view", "binding", "", b"")), tag,
                                      reference(self, permit, ("view", "head", "", b""), ("originalReceipts",)), budget)
            result = self.profile.check_head(ctx, reference(self, permit, ("view", "head", "", b"")))
            self._check()
            check(self._proof_context is not None and self._proof_context[0] == permit, "sync_reference_retired")
            check(type(result) is HeadRules, "sync_head_rules")
            return result
        finally:
            budget.close()
            self._proof_context = None

    def _leases(self, root, head, proof, rules, sent, clock):
        check(canonical(clock) == self._clock.encoded, "sync_reader_clock")
        bridge = proof["bridgeClock"]
        closed(bridge, "bootId timeNamespace boottimeMs", "sync_bridge_clock")
        native_clock = head["ownerClock"]
        check(bridge["bootId"] == native_clock["bootId"] and
              bridge["timeNamespace"] == native_clock["clockDomain"].replace("[", "").replace("]", "") and
              type(bridge["boottimeMs"]) is int and bridge["boottimeMs"] >= native_clock["boottimeMs"],
              "sync_bridge_clock_binding")
        request = thaw(self._request.value)
        check(type(proof["bridgeId"]) is str and len(proof["bridgeId"]) == 32 and
              request.get("bridgeId") == proof["bridgeId"], "sync_bridge_incarnation")
        if self.local_owner:
            check({key: bridge[key] for key in ("bootId", "timeNamespace")} == clock and
                  root.binding.value["uid"] == os.getuid(), "sync_local_owner_clock")
        attenuation = entries(head["attenuation"], 32, "sync_attenuation")
        remaining = entries(proof["remaining"], 32, "sync_remaining")
        receipts = dict(root.tables)["receipts"]
        projected = {}
        allowed = None if rules.allowed_receipts is None else {canonical(key) for key in rules.allowed_receipts}
        for receipt in rules.original_receipts:
            # Freeze the callback's projection again; a user-created Atom is
            # data, not an owned-input capability.
            receipt = OriginalReceipt(Atom.own(thaw(receipt.key.value)), receipt.value_hash,
                                      receipt.accepted, receipt.health, receipt.expiry_ms)
            key = receipt.key.encoded
            check(key not in projected, "sync_duplicate_receipt")
            leaf = receipts.find(thaw(receipt.key.value))
            check(leaf is not ABSENT and receipt.value_hash == leaf.value_hash.hex(), "sync_receipt_projection")
            projected[key] = receipt
        check(len(projected) == len(receipts) and set(projected) == set(attenuation) == set(remaining),
              "sync_receipt_coverage")
        if allowed is not None:
            check(allowed <= set(projected), "sync_receipt_restrictions")
        expiries = []
        received = self._now_ms()  # callback/validation time belongs to RTT
        check(type(received) is int and type(sent) is int and sent <= received <= sent + 2000, "sync_proof_deadline")
        previous = self._last_head_clock
        check(previous is None or previous[0] != _owner_clock_scope(native_clock) or
              previous[2] <= bridge["boottimeMs"], "sync_bridge_clock_regression")
        check(bridge["boottimeMs"] - native_clock["boottimeMs"] <= received - sent + 100,
              "sync_bridge_clock_elapsed")
        check(not self.local_owner or bridge["boottimeMs"] <= received, "sync_local_owner_clock")
        for key, receipt in projected.items():
            native_remaining, bridge_remaining = attenuation[key][1], remaining[key][1]
            check(type(native_remaining) is int and native_remaining >= 0 and
                  type(bridge_remaining) is int and bridge_remaining >= 0, "sync_receipt_remaining")
            native_limit = (max(0, receipt.expiry_ms - native_clock["boottimeMs"])
                            if receipt.health in {"current", "partial"} else 0)
            bridge_limit = (max(0, receipt.expiry_ms - bridge["boottimeMs"])
                            if receipt.health in {"current", "partial"} else 0)
            check(native_remaining <= native_limit and bridge_remaining <= min(native_remaining, bridge_limit),
                  "sync_receipt_extension")
            expiry = receipt.expiry_ms if self.local_owner else remote_expiry(sent, received, bridge_remaining)
            if receipt.health not in {"current", "partial"} or allowed is not None and key not in allowed:
                expiry = received
            expiries.append((receipt.key, expiry))
        return _Confirmation(Atom.own(native_clock), tuple(projected.values()), tuple(expiries), received,
                             secrets.token_hex(16))

    def acquire(self):
        with self._lock:
            self._check()
            check(self._view_permit is not None and self._confirmation is not None, "sync_unconfirmed")
            return ViewRef(self, self._view_permit, self._tag(self.store.current.tag))

    def _context(self, permit, now_ms, clock):
        with self._lock:
            root = self._view_root(permit)
            check(permit == self._view_permit, "sync_unconfirmed_view")
            confirmation = self._confirmation
            check(type(now_ms) is int and now_ms >= confirmation.received_ms and
                  canonical(clock) == self._clock.encoded, "sync_reader_clock")
            now_ms = max(now_ms, self._now_ms())
            expiries = {key.encoded: expiry for key, expiry in confirmation.expiries}
            return {"status": "confirmed", "host": self._binding.value["host"], "source": self._binding.value["source"],
                    "profile": self.descriptor.profile_id, "tag": self._tag(root.tag).wire(),
                    "nativeBinding": thaw(root.binding.value), "ownerClock": thaw(confirmation.owner_clock.value),
                    "confirmedAtMs": confirmation.received_ms,
                    "receipts": [{"key": thaw(item.key.value), "valueHash": item.value_hash,
                                  "accepted": item.accepted, "health": item.health,
                                  "expiresMs": expiries[item.key.encoded],
                                  "current": item.health in {"current", "partial"} and now_ms < expiries[item.key.encoded]}
                                 for item in confirmation.receipts]}

    def disconnect(self):
        with self._lock:
            if self._inputs is not None:
                self._inputs.close()
                self._inputs = None
            self.revoke("disconnected")
            self._discard_candidate()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self.disconnect()
            self.store.close()
            self.ledger.release(self._history)
            self._history = None
            self._known_head = self._last_head_clock = None
            self._transaction_tokens = self._retired_bindings = ()
            self.ledger.release(self._metadata)
            self._metadata = ()
            self._closed = True
            # Profile callbacks may retain a retired view/head reference back
            # to this cache. Closing must retire that cycle without cyclic GC.
            self.profile = self._now_ms = None
