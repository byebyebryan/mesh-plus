"""Conservative full-view encoder and independently validating receiver."""

import copy
import math
import sys
import threading
import uuid

from ..evidence import digest
from ..protocol import MAX_MESSAGE, ProtocolError, check
from ..state import check_binding, validate_bridge
from .budget import FeedBudget, FeedLimits
from .protocol import FEED_PROTOCOL, json_size, validate_packet

_MAX_REVISION = 9007199254740991
_MAX_TREE_NODES = 1_000_000
_SELECTOR_BYTES = 16 * 1024
_TOKEN_BYTES = 128
_INDEX_HEAP_PER_RECORD = 2048


class _FrozenDict(dict):
    __slots__ = ("_credit",)

    def __init__(self, pairs=(), *, credit=None):
        dict.__init__(self, pairs)
        self._credit = credit

    @staticmethod
    def _refuse(*_args, **_kwargs):
        raise TypeError("borrowed feed payload is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _refuse
    __ior__ = _refuse

    def __deepcopy__(self, memo):
        if id(self) in memo:
            return memo[id(self)]
        result = {}
        memo[id(self)] = result
        for key, value in self.items():
            result[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)
        return result


class _FrozenList(list):
    __slots__ = ("_credit",)

    def __init__(self, values=(), *, credit=None):
        list.__init__(self, values)
        self._credit = credit

    @staticmethod
    def _refuse(*_args, **_kwargs):
        raise TypeError("borrowed feed payload is immutable")

    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = _refuse
    __iadd__ = __imul__ = _refuse

    def __deepcopy__(self, memo):
        if id(self) in memo:
            return memo[id(self)]
        result = []
        memo[id(self)] = result
        result.extend(copy.deepcopy(value, memo) for value in self)
        return result


def _freeze(value, credit):
    if isinstance(value, dict):
        return _FrozenDict(((key, _freeze(child, credit)) for key, child in value.items()), credit=credit)
    if isinstance(value, list):
        return _FrozenList((_freeze(child, credit) for child in value), credit=credit)
    return value


def _clone_json(value, depth=0):
    check(depth <= 64, "tree_depth")
    kind = type(value)
    if kind in (str, int, float, bool, type(None)):
        if kind is float:
            check(math.isfinite(value), "nonfinite")
        return value
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            check(type(key) is str, "invalid_json")
            result[key] = _clone_json(child, depth + 1)
        return result
    if isinstance(value, list):
        return [_clone_json(child, depth + 1) for child in value]
    raise ProtocolError("invalid_json")


def _tree_nodes(value, depth=0, count=0):
    check(depth <= 64, "tree_depth")
    count += 1
    check(count <= _MAX_TREE_NODES, "view_feed_node_capacity")
    if isinstance(value, dict):
        for key, child in value.items():
            count += 1  # JSON object keys are owned string objects too.
            check(count <= _MAX_TREE_NODES, "view_feed_node_capacity")
            count = _tree_nodes(child, depth + 1, count)
    elif isinstance(value, (list, tuple)):
        for child in value:
            count = _tree_nodes(child, depth + 1, count)
    return count


def _heap_census(value, *, unique=False):
    """Count Python object storage; nonunique traversal is a safe copy upper bound."""
    seen = set() if unique else None

    nodes = 0

    def visit(item, depth=0):
        nonlocal nodes
        check(depth <= 64, "tree_depth")
        nodes += 1
        check(nodes <= _MAX_TREE_NODES, "view_feed_node_capacity")
        if seen is not None:
            identity = id(item)
            if identity in seen:
                return 0
            seen.add(identity)
        total = sys.getsizeof(item)
        if isinstance(item, dict):
            total += sum(visit(key, depth + 1) + visit(child, depth + 1)
                         for key, child in item.items())
        elif isinstance(item, (list, tuple, set, frozenset)):
            total += sum(visit(child, depth + 1) for child in item)
        return total

    try:
        return visit(value)
    finally:
        # A recursive local function closes over itself. Break that cycle even
        # with cyclic GC disabled, and retire the temporary identity set.
        visit = None
        if seen is not None:
            seen.clear()


def _container_slack(value):
    """Bound container-subclass and copy-growth overhead from observed topology."""
    return _tree_nodes(value) * 32 + 4096


def _generation_heap(generation):
    retained = (generation.binding, generation.envelope, generation.owner, generation.records,
                generation.keys, generation.record_map, generation.fingerprints, generation.tokens,
                generation.identity_credits)
    # The unique census temporarily stores one object id per traversed node.
    # Pay its conservative scratch bound before allocating that set.
    census_credit = generation.scope.reserve(96 * _tree_nodes(retained) + 4096)
    try:
        return max(4096, sys.getsizeof(generation) + _heap_census(retained, unique=True) + 1024)
    finally:
        census_credit.release()


def _copy_heap_bound(value):
    return _heap_census(value) + _container_slack(value)


def _defer_active_credits(*credits):
    """Keep failed-operation reservations alive with the escaping exception."""
    error = sys.exc_info()[1]
    if error is None:
        return
    held = tuple(credit for credit in credits if credit is not None)
    if not held:
        return
    try:
        existing = getattr(error, "_view_feed_credits", ())
        known = {id(credit) for credit in existing}
        combined = existing + tuple(credit for credit in held if id(credit) not in known)
        setattr(error, "_view_feed_credits", combined)
    except Exception:
        # The active traceback still owns this frame and its credit locals, so
        # callers must skip release even for exception types without __dict__.
        return


def _incoming_reservation(scope, value, size):
    # validate_bridge and the native digest path can hold a compact JSON text
    # and its UTF-8 bytes at once. Both are bounded by the admitted input size.
    return scope.reserve(_copy_heap_bound(value) + 2 * size + 4096,
                         encoded_bytes=size)


def _digest_scratch(scope, value, size=None):
    if size is None:
        size = json_size(value, maximum=MAX_MESSAGE)
    check(size <= MAX_MESSAGE, "view_feed_digest_capacity")
    return scope.reserve(2 * size + 4096, encoded_bytes=size)


def _funded_digest(scope, value, size=None):
    credit = _digest_scratch(scope, value, size)
    failed = False
    try:
        return digest(value)
    except BaseException:
        _defer_active_credits(credit)
        failed = True
        raise
    finally:
        if not failed:
            credit.release()


def _record_identity_heap_bound(key):
    # Count strings separately even when they alias record fields. This is
    # intentionally conservative and remains bounded by the packet identity.
    return _heap_census(key) + 256


def _array_json_size(values):
    return 2 + sum(json_size(value) + (1 if index else 0)
                   for index, value in enumerate(values))


def _identity_array_json_size(keys):
    return 2 + sum(_array_json_size(key) + (1 if index else 0)
                   for index, key in enumerate(keys))


def _object_json_size(items):
    return 2 + sum((1 if index else 0) + json_size(key) + 1 + value_size
                   for index, (key, value_size) in enumerate(items))


def _target_json_size(target):
    return _object_json_size((
        ("revision", json_size(target.revision)),
        ("digest", json_size(target.digest)),
    ))


def _replacement_packet_size(target, reason):
    binding_size = json_size(target.binding)
    envelope_size = json_size(target.envelope)
    owner_size = json_size(target.owner)
    records_size = _array_json_size(target.records)
    order_size = _identity_array_json_size(target.keys)
    fields = (
        ("protocol", json_size(FEED_PROTOCOL)),
        ("kind", json_size("replacement")),
        ("streamId", json_size(target.stream_id)),
        ("binding", binding_size),
        ("base", json_size(None)),
        ("target", _target_json_size(target)),
        ("owner", owner_size),
        ("envelope", envelope_size),
        ("records", records_size),
        ("upserts", 2),
        ("removals", 2),
        ("order", order_size),
        ("reason", json_size(reason)),
    )
    return _object_json_size(fields)


def _delta_packet_size(target, previous, upserts, removals, order):
    base_size = _object_json_size((
        ("revision", json_size(previous.revision)),
        ("digest", json_size(previous.digest)),
    ))
    fields = (
        ("protocol", json_size(FEED_PROTOCOL)),
        ("kind", json_size("delta")),
        ("streamId", json_size(target.stream_id)),
        ("binding", json_size(target.binding)),
        ("base", base_size),
        ("target", _target_json_size(target)),
        ("owner", json_size(target.owner)),
        ("envelope", json_size(target.envelope)),
        ("records", json_size(None)),
        ("upserts", _array_json_size(upserts)),
        ("removals", _identity_array_json_size(removals)),
        ("order", json_size(None) if order is None else _identity_array_json_size(order)),
        ("reason", json_size("delta")),
    )
    return _object_json_size(fields)


def _replacement_message(target, reason, scope, limits):
    structure = scope.reserve(512 * len(target.records) + 8192)
    packet = None
    failed = False
    try:
        packet = _replacement_packet(target, reason)
        check(_replacement_packet_size(target, reason) == json_size(packet), "view_feed_packet_size")
        return _message_from_packet(packet, target, scope, limits)
    except BaseException:
        _defer_active_credits(structure)
        failed = True
        raise
    finally:
        packet = None
        if not failed:
            structure.release()


def _apply_operations(profile, base_map, base_keys, removals, upserts, order):
    """Common whole-record merge used by sender verification and receiver apply."""
    records_by_key = dict(base_map)
    for key_value in removals:
        key = _wire_identity(key_value)
        check(key in records_by_key, "view_feed_removal_missing")
        del records_by_key[key]
    for item in upserts:
        key = _wire_identity(item["key"])
        check(_identity(profile, item["record"]) == key, "view_feed_upsert_identity")
        records_by_key[key] = item["record"]
    keys = base_keys if order is None else tuple(_wire_identity(key) for key in order)
    check(len(keys) == len(records_by_key) and set(keys) == set(records_by_key), "view_feed_order")
    if order is None:
        check(keys == base_keys, "view_feed_order_required")
    return tuple(records_by_key[key] for key in keys), keys, records_by_key


def _identity(profile, record):
    value = profile.record_identity(record)
    check(type(value) is tuple and 0 < len(value) <= 16 and
          all(type(part) in (str, int) for part in value), "view_feed_identity")
    check(all(type(part) is not str or len(part) <= 16384 for part in value), "view_feed_identity")
    return value


def _wire_identity(value):
    check(isinstance(value, list) and 0 < len(value) <= 16 and
          all(type(part) in (str, int) for part in value), "view_feed_identity")
    check(all(type(part) is not str or len(part) <= 16384 for part in value), "view_feed_identity")
    return tuple(value)


def _validate_token(value):
    check(type(value) in (str, int), "view_feed_token")
    if type(value) is str:
        size = json_size(value, maximum=_TOKEN_BYTES)
        check(size <= _TOKEN_BYTES, "view_feed_token")
    else:
        check(value.bit_length() <= 256, "view_feed_token")
    return value


class _Generation:
    __slots__ = ("stream_id", "revision", "digest", "binding", "envelope", "owner", "records",
                 "keys", "record_map", "fingerprints", "tokens", "heap_bytes", "encoded_bytes",
                 "credit", "identity_credits", "scope", "encoder_id")

    def __init__(self, *, stream_id, revision, target_digest, binding, envelope, owner, records,
                 keys, record_map, fingerprints, tokens, credit, identity_credits, scope, encoder_id=None):
        self.stream_id, self.revision, self.digest = stream_id, revision, target_digest
        self.binding, self.envelope, self.owner = binding, envelope, owner
        self.records, self.keys, self.record_map = tuple(records), tuple(keys), record_map
        self.fingerprints, self.tokens = fingerprints, tokens
        self.credit, self.identity_credits = credit, tuple(identity_credits)
        self.scope, self.encoder_id = scope, encoder_id
        self.encoded_bytes = (json_size(binding) + json_size(envelope) + json_size(owner) +
                              sum(json_size(record) for record in self.records) +
                              sum(_array_json_size(key) for key in self.keys) +
                              sum(json_size(value) for value in tokens.values()) +
                              sum(json_size(value) for value in fingerprints.values()))
        self.heap_bytes = _generation_heap(self)


class _Engine:
    def __init__(self, profile, codec, selector, limits, budget):
        check(isinstance(selector, dict), "view_feed_selector")
        if limits is None and type(budget) is FeedBudget:
            limits = budget.limits
        limits = FeedLimits() if limits is None else limits
        check(type(limits) is FeedLimits, "view_feed_limits")
        check_binding(codec, codec.host, codec.source, profile.descriptor.profile_id)
        selector_size = json_size(selector, maximum=_SELECTOR_BYTES)
        check(selector_size <= _SELECTOR_BYTES, "view_feed_selector_capacity")
        self.profile, self.codec = profile, codec
        self.limits = limits
        self.budget = FeedBudget(limits) if budget is None else budget
        check(type(self.budget) is FeedBudget, "view_feed_budget")
        self.scope = self.budget.scope(limits)
        self._selector_credit = self.scope.reserve(_copy_heap_bound(selector) + 2 * selector_size + 8192,
                                                   encoded_bytes=selector_size)
        self.selector = _clone_json(selector)
        self._static_binding = {
            "hostId": codec.host,
            "sourceId": codec.source,
            "profileId": profile.descriptor.profile_id,
            "contractDigest": profile.descriptor.contract_digest,
            "selector": self.selector,
        }
        self._static_binding_digest = _funded_digest(self.scope, self._static_binding)
        self._closed = False
        self._busy = False
        self._lock = threading.Lock()

    def _begin(self):
        with self._lock:
            check(not self._closed, "view_feed_closed")
            check(not self._busy, "view_feed_reentrant")
            self._busy = True

    def _end(self):
        with self._lock:
            self._busy = False
            if self._closed:
                _defer_active_credits(self._selector_credit)
                self._selector_credit = None

    def _check_open(self):
        with self._lock:
            check(not self._closed, "view_feed_closed")

    def _validate_static_binding(self, binding):
        static = {key: binding[key] for key in ("hostId", "sourceId", "profileId", "contractDigest", "selector")}
        check(_funded_digest(self.scope, static) == self._static_binding_digest, "view_feed_binding")

    def _make_binding(self, publisher, clock, bridge_id):
        return {**self._static_binding, "nativePublisher": publisher,
                "nativeClock": clock, "bridgeId": bridge_id}

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if not self._busy:
                self._selector_credit = None
            self.selector = None
            self._static_binding = None

    def _inspect(self, *, revision=None, valid=None):
        local = self.scope.inspect()
        shared = self.budget.inspect()
        return {"closed": self._closed, "revision": revision, "valid": valid,
                "heapBytes": local["heapBytes"], "encodedBytes": local["encodedBytes"],
                "heapLimitBytes": local["heapLimitBytes"], "encodedLimitBytes": local["encodedLimitBytes"],
                "sharedHeapBytes": shared["heapBytes"], "sharedEncodedBytes": shared["encodedBytes"],
                "peakHeapBytes": shared["peakHeapBytes"],
                "peakEncodedBytes": shared["peakEncodedBytes"]}


class FeedMessage:
    """Owned checked packet handle; ``payload`` is borrowed until the handle closes."""

    __slots__ = ("_payload", "_target", "_scope", "_limits", "_closed")

    def __init__(self, payload, target, scope, limits):
        self._payload, self._target = payload, target
        self._scope, self._limits = scope, limits
        self._closed = False

    @property
    def payload(self):
        check(not self._closed and self._payload is not None, "view_feed_message_closed")
        return self._payload

    @property
    def revision(self):
        check(not self._closed and self._target is not None, "view_feed_message_closed")
        return self._target.revision

    @property
    def kind(self):
        return self.payload["kind"]

    def replacement(self):
        check(not self._closed and self._target is not None, "view_feed_message_closed")
        target = self._target
        return _replacement_message(target, "resync", self._scope, self._limits)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._payload = self._target = self._scope = self._limits = None

    def __enter__(self):
        check(not self._closed, "view_feed_message_closed")
        return self

    def __exit__(self, *_args):
        self.close()


def _packet_shell(kind, target, *, base=None, records=None, upserts=None, removals=None,
                  order=None, reason):
    return {
        "protocol": FEED_PROTOCOL,
        "kind": kind,
        "streamId": target.stream_id,
        "binding": target.binding,
        "base": base,
        "target": {"revision": target.revision, "digest": target.digest},
        "owner": target.owner,
        "envelope": target.envelope,
        "records": records,
        "upserts": [] if upserts is None else upserts,
        "removals": [] if removals is None else removals,
        "order": order,
        "reason": reason,
    }


def _replacement_packet(target, reason):
    return _packet_shell("replacement", target, records=list(target.records),
                         order=[list(key) for key in target.keys], reason=reason)


def _message_from_packet(packet, target, scope, limits):
    size = json_size(packet, maximum=min(limits.max_packet_bytes, MAX_MESSAGE))
    validate_packet(packet, limits)
    credit = scope.reserve(_copy_heap_bound(packet), encoded_bytes=size)
    payload = _freeze(packet, credit)
    return FeedMessage(payload, target, scope, limits)


class FeedEncoder(_Engine):
    """Validate complete Bridge candidates and emit checked whole-record batches."""

    def __init__(self, profile, codec, *, selector, limits=None, token=None, token_scheme=None, budget=None):
        check((token is None) == (token_scheme is None), "view_feed_token_scheme")
        if token is not None:
            check(callable(token) and type(token_scheme) is str and 0 < len(token_scheme) <= _TOKEN_BYTES and
                  json_size(token_scheme, maximum=_TOKEN_BYTES) <= _TOKEN_BYTES,
                  "view_feed_token_scheme")
        super().__init__(profile, codec, selector, limits, budget)
        self._base = None
        self._stream_id = str(uuid.uuid4())
        self._encoder_id = str(uuid.uuid4())
        self._token_callback, self._token_scheme = token, token_scheme
        self._token_enabled = token is not None

    def _construct_target(self, candidate, previous):
        check(isinstance(candidate, dict), "view_feed_candidate")
        size = json_size(candidate, maximum=min(self.limits.encoded_bytes, MAX_MESSAGE))
        check(size <= self.limits.encoded_bytes and size <= MAX_MESSAGE, "view_feed_input_capacity")
        incoming_credit = _incoming_reservation(self.scope, candidate, size)
        generation_credit = None
        identity_credits = []
        owned = state = restored = None
        failed = False
        try:
            owned = _clone_json(candidate)
            check(owned.get("kind") == "candidate", "view_feed_candidate_kind")
            state = validate_bridge(self.profile, self.codec, owned)
            check(type(state.records) in (list, tuple) and len(state.records) <= self.limits.max_records,
                  "view_feed_record_capacity")

            # Reserve for the complete private projection and all indexes before
            # copying any owner, row, envelope or selector value into the base.
            envelope_source = {key: value for key, value in owned.items() if key != "ownerFrame"}
            binding_source = self._make_binding(state.publisher, state.clock, owned["bridgeId"])
            binding_size = json_size(binding_source, maximum=self.limits.encoded_bytes)
            projection_size = (binding_size + json_size(envelope_source) + json_size(state.owner) +
                               sum(json_size(record) for record in state.records) +
                               512 * len(state.records) + 4096)
            projection_heap = (_copy_heap_bound(binding_source) + _copy_heap_bound(envelope_source) +
                               _copy_heap_bound(state.owner) + _copy_heap_bound(state.records) +
                               16 * 1024 + _INDEX_HEAP_PER_RECORD * len(state.records))
            check(projection_size <= self.limits.encoded_bytes, "view_feed_capacity")
            generation_credit = self.scope.reserve(projection_heap, encoded_bytes=projection_size)

            binding = _clone_json(binding_source)
            envelope = _clone_json(envelope_source)
            owner = _clone_json(state.owner)
            records = [_clone_json(record) for record in state.records]
            target_digest = owned["ownerDigest"]

            keys, record_map, fingerprints, tokens = [], {}, {}, {}
            token_enabled = self._token_enabled
            reused = set()
            for record in records:
                key = _identity(self.profile, record)
                key_credit = self.scope.reserve(_record_identity_heap_bound(key))
                identity_credits.append(key_credit)
                check(key not in record_map, "view_feed_duplicate_identity")
                check(self.profile.record_host(record) == self.codec.host, "view_feed_scope")
                keys.append(key)
                record_map[key] = record

                if token_enabled:
                    # The token callback receives a detached immutable copy.
                    # Each container carries the lease so a callback that
                    # retains an argument cannot outlive its charge.
                    token_temp = self.scope.reserve(2 * _copy_heap_bound(record) + 8192)
                    token_input = None
                    token_failed = False
                    try:
                        token_input = _freeze(_clone_json(record), token_temp)
                        token_value = _validate_token(self._token_callback(token_input))
                        self._check_open()
                    except BaseException:
                        _defer_active_credits(token_temp)
                        token_failed = True
                        raise
                    finally:
                        if not token_failed:
                            token_input = None
                    tokens[key] = token_value
                    if previous is not None and key in previous.tokens and \
                            previous.tokens[key] == token_value and key in previous.fingerprints:
                        fingerprints[key] = previous.fingerprints[key]
                        reused.add(key)
                    else:
                        fingerprints[key] = _funded_digest(self.scope, record)
                else:
                    fingerprints[key] = _funded_digest(self.scope, record)

            # Check the final private generation after every row callback, not
            # an earlier projection. Even an accidentally mutating pure-profile
            # callback cannot cause an unchecked initial replacement to escape.
            restored = self.profile.restore_native(owner, records)
            check(_funded_digest(self.scope, restored) == target_digest,
                  "view_feed_sender_reconstruction")

            target = _Generation(
                stream_id=self._stream_id, revision=0, target_digest=target_digest,
                binding=binding, envelope=envelope, owner=owner, records=records,
                keys=keys, record_map=record_map, fingerprints=fingerprints, tokens=tokens,
                credit=generation_credit, identity_credits=identity_credits,
                scope=self.scope, encoder_id=self._encoder_id)
            check(target.encoded_bytes <= generation_credit.encoded_bytes, "view_feed_capacity")
            check(target.heap_bytes <= generation_credit.heap_bytes +
                  sum(credit.heap_bytes for credit in identity_credits), "view_feed_capacity")
            self._validate_static_binding(binding)
            if previous is not None:
                check(_funded_digest(self.scope, binding) == _funded_digest(self.scope, previous.binding),
                      "view_feed_native_binding")

            # The original full input and validation projection are temporary.
            # The committed generation has separately funded immutable copies.
            owned = state = restored = envelope_source = binding_source = None
            incoming_credit.release()
            return target, token_enabled, reused
        except BaseException:
            _defer_active_credits(incoming_credit, generation_credit, *identity_credits)
            failed = True
            raise
        finally:
            if not failed:
                incoming_credit.release()

    @staticmethod
    def _delta_values(previous, target, *, token_mismatch=False):
        upserts = []
        removals = [list(key) for key in previous.keys if key not in target.record_map]
        for key in target.keys:
            if key not in previous.record_map or previous.fingerprints[key] != target.fingerprints[key]:
                upserts.append({"key": list(key), "record": target.record_map[key]})
        order = [list(key) for key in target.keys] if target.keys != previous.keys else None
        return upserts, removals, order

    def _verify_delta(self, previous, target, upserts, removals, order):
        rows, keys, _ = _apply_operations(self.profile, previous.record_map, previous.keys,
                                           removals, upserts, order)
        if keys != target.keys:
            return False
        size = min(MAX_MESSAGE, target.encoded_bytes)
        scratch = self.scope.reserve(_copy_heap_bound((target.owner, rows)) +
                                     2 * size + 4096 + 256 * len(rows), encoded_bytes=size)
        failed = False
        try:
            frame = self.profile.restore_native(target.owner, rows)
            return digest(frame) == target.digest
        except BaseException:
            _defer_active_credits(scratch)
            failed = True
            raise
        finally:
            if not failed:
                scratch.release()

    def encode(self, full_bridge_candidate, *, force_replacement=False):
        check(type(force_replacement) is bool, "view_feed_force_replacement")
        self._begin()
        target = message = None
        committed = False
        failed = False
        try:
            previous = self._base
            target, token_enabled, reused = self._construct_target(full_bridge_candidate, previous)
            self._check_open()
            same_target = (previous is not None and previous.digest == target.digest and
                           _funded_digest(self.scope, previous.envelope) ==
                           _funded_digest(self.scope, target.envelope) and
                           _funded_digest(self.scope, previous.binding) ==
                           _funded_digest(self.scope, target.binding))
            if same_target:
                target.credit.release()
                for credit in target.identity_credits:
                    credit.release()
                target = None
                if not force_replacement:
                    return None
                message = _replacement_message(previous, "forced", self.scope, self.limits)
                committed = True
                return message

            if previous is None:
                target.revision = 1
                message = _replacement_message(target, "initial", self.scope, self.limits)
            else:
                check(previous.revision < _MAX_REVISION, "view_feed_revision_capacity")
                target.revision = previous.revision + 1
                if force_replacement:
                    message = _replacement_message(target, "forced", self.scope, self.limits)
                else:
                    provisional = self.scope.reserve(
                        1024 * (len(previous.records) + len(target.records)) + 16 * 1024)
                    upserts = removals = order = packet = None
                    provisional_failed = False
                    try:
                        upserts, removals, order = self._delta_values(previous, target)
                        verified = self._verify_delta(previous, target, upserts, removals, order)
                        token_mismatch = not verified and bool(reused)
                        if token_mismatch:
                            # Equal tokens skipped row hashes; whole-target
                            # reconstruction disproves that promise. Retire it
                            # and independently fingerprint every target row.
                            self._token_enabled = False
                            target.tokens = {}
                            target.fingerprints = {
                                key: _funded_digest(self.scope, target.record_map[key])
                                for key in target.keys
                            }
                            message = _replacement_message(target, "token_mismatch",
                                                           self.scope, self.limits)
                        elif verified:
                            delta_size = _delta_packet_size(target, previous, upserts, removals, order)
                            replacement_size = _replacement_packet_size(target, "larger_delta")
                            if delta_size < replacement_size:
                                packet = _packet_shell(
                                    "delta", target,
                                    base={"revision": previous.revision, "digest": previous.digest},
                                    records=None, upserts=upserts, removals=removals, order=order,
                                    reason="delta")
                                check(json_size(packet) == delta_size, "view_feed_packet_size")
                                message = _message_from_packet(packet, target, self.scope, self.limits)
                            else:
                                message = _replacement_message(target, "larger_delta",
                                                               self.scope, self.limits)
                        else:
                            message = _replacement_message(target, "larger_delta",
                                                           self.scope, self.limits)
                    except BaseException:
                        _defer_active_credits(provisional)
                        provisional_failed = True
                        raise
                    finally:
                        packet = upserts = removals = order = None
                        if not provisional_failed:
                            provisional.release()
            self._check_open()
            with self._lock:
                check(not self._closed, "view_feed_closed")
                self._base = target
                self._token_enabled = token_enabled and self._token_enabled
                committed = True
            return message
        except BaseException:
            if target is not None:
                _defer_active_credits(target.credit, *target.identity_credits)
            failed = True
            raise
        finally:
            if not committed and not failed and target is not None:
                target.credit.release()
                for credit in target.identity_credits:
                    credit.release()
            if not committed and message is not None:
                message.close()
            self._end()

    def replacement(self, message):
        check(type(message) is FeedMessage and message._target is not None and
              message._target.encoder_id == self._encoder_id, "view_feed_message_binding")
        return message.replacement()

    def inspect(self):
        return self._inspect(revision=None if self._base is None else self._base.revision,
                             valid=self._base is not None and not self._closed)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._base = None
            if not self._busy:
                self._selector_credit = None
            self.selector = None
            self._static_binding = None
            self._token_callback = None
            self._token_scheme = None
            self._token_enabled = False


class FeedApplied:
    """Owned reconstructed Bridge candidate and accepted change metadata."""

    __slots__ = ("_payload", "_kind", "_revision", "_upserts", "_removals", "_order", "_closed")

    def __init__(self, payload, kind, revision, upserts, removals, order):
        self._payload, self._kind, self._revision = payload, kind, revision
        self._upserts, self._removals, self._order = upserts, removals, order
        self._closed = False

    @property
    def payload(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._payload

    @property
    def candidate(self):
        return self.payload

    @property
    def kind(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._kind

    @property
    def revision(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._revision

    @property
    def upserts(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._upserts

    @property
    def removals(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._removals

    @property
    def order(self):
        check(not self._closed, "view_feed_applied_closed")
        return self._order

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._payload = self._upserts = self._removals = self._order = None

    def __enter__(self):
        check(not self._closed, "view_feed_applied_closed")
        return self

    def __exit__(self, *_args):
        self.close()


class FeedReceiver(_Engine):
    """Reconstruct and fully admit one stream without trusting sender state."""

    def __init__(self, profile, codec, *, selector, limits=None, budget=None):
        super().__init__(profile, codec, selector, limits, budget)
        self._generation = None
        self._stream_id = None
        self._bridge_id = None
        self._native_binding = None
        self._last_stream_id = None
        self._last_revision = None
        self._last_target_digest = None
        self._last_bridge_id = None
        self._last_sequence = None
        self._last_envelope_digest = None
        self._last_encoded_at = None
        self._needs_replacement = True
        self._invalid = False
        self._epoch = 0

    def _invalidate_locked(self):
        self._generation = None
        self._stream_id = None
        self._bridge_id = None
        self._needs_replacement = True
        self._invalid = True
        self._epoch += 1

    def mark_gap(self):
        """Revoke the baseline and require an explicit replacement after a Delivery gap."""
        with self._lock:
            check(not self._closed, "view_feed_closed")
            self._generation = None
            self._stream_id = None
            self._bridge_id = None
            self._needs_replacement = True
            self._invalid = False
            self._epoch += 1

    def _check_receiver_binding(self, packet):
        binding = packet["binding"]
        self._validate_static_binding(binding)
        dynamic = (binding["nativePublisher"], _funded_digest(self.scope, binding["nativeClock"]))
        if self._native_binding is not None:
            check(dynamic == self._native_binding, "view_feed_native_binding")
        if self._stream_id is not None:
            check(packet["streamId"] == self._stream_id and binding["bridgeId"] == self._bridge_id,
                  "view_feed_stream_binding")
        check(not self._needs_replacement or packet["kind"] == "replacement",
              "view_feed_replacement_required")
        envelope = packet["envelope"]
        sequence, encoded_at = envelope["sequence"], envelope["encodedAtMs"]
        check(type(sequence) is int and type(encoded_at) is int, "view_feed_native_chronology")
        envelope_digest = _funded_digest(self.scope, envelope)
        if self._last_encoded_at is not None:
            check(encoded_at >= self._last_encoded_at, "view_feed_native_chronology")
        if binding["bridgeId"] == self._last_bridge_id and self._last_sequence is not None:
            check(sequence >= self._last_sequence, "view_feed_native_chronology")
            if sequence == self._last_sequence:
                check(envelope_digest == self._last_envelope_digest and
                      packet["target"]["digest"] == self._last_target_digest,
                      "view_feed_native_chronology")

        stream_id = packet["streamId"]
        target_revision = packet["target"]["revision"]
        if self._last_stream_id is None:
            # Initial Delivery credit/coalescing can drop the first few
            # publications before a client admits any feed packet. A complete
            # replacement is self-contained, so only positive revision is
            # required here (the packet validator has already enforced it).
            check(packet["kind"] == "replacement", "view_feed_replacement_required")
        elif stream_id == self._last_stream_id:
            if packet["kind"] == "replacement":
                check(target_revision >= self._last_revision and
                      (target_revision != self._last_revision or
                       (packet["target"]["digest"] == self._last_target_digest and
                        envelope_digest == self._last_envelope_digest)),
                      "view_feed_revision")
        else:
            check(packet["kind"] == "replacement" and target_revision == 1,
                  "view_feed_stream_binding")
        return dynamic, envelope_digest, sequence, encoded_at

    def _target_from_packet(self, packet):
        kind = packet["kind"]
        base = self._generation
        if self._invalid:
            check(False, "view_feed_reset_required")
        if self._needs_replacement:
            check(kind == "replacement", "view_feed_replacement_required")
        if kind == "delta":
            check(base is not None and not self._needs_replacement and
                  packet["streamId"] == self._stream_id, "view_feed_base")
            check(packet["base"]["revision"] == base.revision and
                  packet["base"]["digest"] == base.digest, "view_feed_base")
            check(packet["target"]["revision"] == base.revision + 1, "view_feed_revision")
            record_sources, keys, _ = _apply_operations(
                self.profile, base.record_map, base.keys,
                packet["removals"], packet["upserts"], packet["order"])
        else:
            check(packet["base"] is None and packet["records"] is not None, "view_feed_replacement")
            if base is not None and not self._needs_replacement:
                revision = packet["target"]["revision"]
                check(revision in {base.revision, base.revision + 1} and
                      (revision != base.revision or packet["target"]["digest"] == base.digest),
                      "view_feed_revision")
            record_sources = packet["records"]
            keys = tuple(_wire_identity(key) for key in packet["order"])
            check(len(record_sources) == len(keys), "view_feed_order")

        check(len(record_sources) <= self.limits.max_records, "view_feed_record_capacity")
        source_binding, source_envelope, source_owner = packet["binding"], packet["envelope"], packet["owner"]
        projection_size = (json_size(source_binding) + json_size(source_envelope) + json_size(source_owner) +
                           sum(json_size(record) for record in record_sources) +
                           _identity_array_json_size(keys) + 512 * len(record_sources) + 4096)
        projection_heap = (_copy_heap_bound(source_binding) + _copy_heap_bound(source_envelope) +
                           _copy_heap_bound(source_owner) + _copy_heap_bound(record_sources) +
                           16 * 1024 + _INDEX_HEAP_PER_RECORD * len(record_sources))
        generation_credit = self.scope.reserve(projection_heap, encoded_bytes=projection_size)
        identity_credits = []
        restore_credit = None
        owner = envelope = binding = None
        records = record_map = None
        try:
            binding = _clone_json(source_binding)
            envelope = _clone_json(source_envelope)
            owner = _clone_json(source_owner)
            records = [_clone_json(record) for record in record_sources]
            record_map = {}
            actual_keys = []
            for expected, record in zip(keys, records):
                actual = _identity(self.profile, record)
                key_credit = self.scope.reserve(_record_identity_heap_bound(actual))
                identity_credits.append(key_credit)
                check(actual == expected, "view_feed_record_order")
                check(actual not in record_map, "view_feed_duplicate_identity")
                check(self.profile.record_host(record) == self.codec.host, "view_feed_scope")
                actual_keys.append(actual)
                record_map[actual] = record
            keys = tuple(actual_keys)

            target_digest = packet["target"]["digest"]
            restore_size = min(MAX_MESSAGE, projection_size)
            restore_credit = self.scope.reserve(_copy_heap_bound((owner, records)) +
                                                2 * restore_size + 256 * len(records) + 8192)
            frame = candidate = state = None
            try:
                frame = self.profile.restore_native(owner, records)
                check(_funded_digest(self.scope, frame) == target_digest and
                      envelope["ownerDigest"] == target_digest,
                      "view_feed_target_digest")
                candidate = {**envelope, "ownerFrame": frame}
                candidate_size = json_size(candidate, maximum=MAX_MESSAGE)
                state = validate_bridge(self.profile, self.codec, candidate)
                validated_keys = tuple(_identity(self.profile, record) for record in state.records)
                check(validated_keys == keys and
                      _funded_digest(self.scope, state.owner) == _funded_digest(self.scope, owner),
                      "view_feed_native_roundtrip")
                target = _Generation(
                    stream_id=packet["streamId"], revision=packet["target"]["revision"],
                    target_digest=target_digest, binding=binding, envelope=envelope, owner=owner,
                    records=records, keys=keys, record_map=record_map, fingerprints={}, tokens={},
                    credit=generation_credit, identity_credits=identity_credits, scope=self.scope)
                check(target.encoded_bytes <= generation_credit.encoded_bytes and
                      target.heap_bytes <= generation_credit.heap_bytes +
                      sum(credit.heap_bytes for credit in identity_credits), "view_feed_capacity")
                return target, candidate, candidate_size, generation_credit, identity_credits, restore_credit
            except BaseException:
                _defer_active_credits(restore_credit)
                raise
        except BaseException:
            _defer_active_credits(generation_credit, *identity_credits, restore_credit)
            raise

    def apply(self, packet):
        self._begin()
        epoch = self._epoch
        packet_credit = stage_credit = generation_credit = restore_credit = output_credit = None
        identity_credits = []
        owned = candidate = output_tree = frozen = result = target = None
        committed = False
        failed = False
        try:
            size = json_size(packet, maximum=min(self.limits.max_packet_bytes, MAX_MESSAGE))
            packet_credit = _incoming_reservation(self.scope, packet, size)
            validate_packet(packet, self.limits)
            owned = _clone_json(packet)
            validate_packet(owned, self.limits)
            with self._lock:
                check(not self._closed and self._epoch == epoch, "view_feed_interrupted")
                dynamic, envelope_digest, sequence, encoded_at = self._check_receiver_binding(owned)
            stage_count = (len(self._generation.records) if self._generation is not None else 0)
            stage_count += len(owned["records"] or []) + len(owned["upserts"]) + len(owned["removals"])
            stage_count += 0 if owned["order"] is None else len(owned["order"])
            stage_credit = self.scope.reserve(1024 * stage_count + 16 * 1024)
            target, candidate, candidate_size, generation_credit, identity_credits, restore_credit = \
                self._target_from_packet(owned)
            upserts, removals, order = owned["upserts"], owned["removals"], owned["order"]
            output_tree = {"candidate": candidate, "upserts": upserts,
                           "removals": removals, "order": order}
            output_size = candidate_size + json_size(upserts) + json_size(removals) + json_size(order)
            check(output_size <= self.limits.encoded_bytes, "view_feed_capacity")
            output_credit = self.scope.reserve(_copy_heap_bound(output_tree), encoded_bytes=output_size)
            frozen = _freeze(output_tree, output_credit)
            result = FeedApplied(frozen["candidate"], owned["kind"], target.revision,
                                 frozen["upserts"], frozen["removals"], frozen["order"])
            with self._lock:
                check(not self._closed and self._epoch == epoch and not self._invalid,
                      "view_feed_interrupted")
                self._generation = target
                self._stream_id = target.stream_id
                self._bridge_id = target.binding["bridgeId"]
                self._native_binding = dynamic
                self._last_stream_id = target.stream_id
                self._last_revision = target.revision
                self._last_target_digest = target.digest
                self._last_bridge_id = target.binding["bridgeId"]
                self._last_sequence = sequence
                self._last_envelope_digest = envelope_digest
                self._last_encoded_at = encoded_at
                self._needs_replacement = False
                self._invalid = False
                committed = True
                # Ownership of the generation/output credits transfers to the
                # receiver state and FeedApplied's frozen containers.
                generation_credit = output_credit = None
                identity_credits = []
                frozen = None
            return result
        except BaseException:
            _defer_active_credits(packet_credit, stage_credit, generation_credit,
                                  *identity_credits, output_credit, restore_credit)
            failed = True
            with self._lock:
                if not self._closed and self._epoch == epoch:
                    self._invalidate_locked()
            raise
        finally:
            if not committed:
                if result is not None:
                    result.close()
            owned = candidate = output_tree = frozen = target = None
            upserts = removals = order = None
            if not committed and not failed:
                if generation_credit is not None:
                    generation_credit.release()
                for credit in identity_credits:
                    credit.release()
                if output_credit is not None:
                    output_credit.release()
            if stage_credit is not None and not failed:
                stage_credit.release()
            if packet_credit is not None and not failed:
                packet_credit.release()
            if restore_credit is not None and not failed:
                restore_credit.release()
            if not committed:
                result = None
            self._end()

    def inspect(self):
        return self._inspect(revision=None if self._generation is None else self._generation.revision,
                             valid=self._generation is not None and not self._invalid and not self._closed)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation = None
            if not self._busy:
                self._selector_credit = None
            self.selector = None
            self._static_binding = None
            self._epoch += 1

