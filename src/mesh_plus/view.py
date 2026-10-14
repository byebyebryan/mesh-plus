"""Pure mesh-aware domain facade. Original records remain owner attributable."""

import copy
import hashlib
import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .evidence import digest
from .protocol import check, encode, metadata_bounds
from .state import inspect_state, resolve_profile

_PROFILE_DIGESTS = {}


@lru_cache(maxsize=2)
def _control_validator(kind):
    schema = json.loads(files("mesh_plus").joinpath("schemas", "read-" + kind + ".schema.json").read_text())
    return Draft202012Validator(schema)


def plain_json(value):
    """Cache only ordinary JSON types; tuples and coercible keys are distinct."""
    kind = type(value)
    if kind is dict:
        return all(type(key) is str and plain_json(child) for key, child in value.items())
    if kind is list:
        return all(plain_json(child) for child in value)
    return kind in (str, int, float, bool, type(None))


@lru_cache(maxsize=4)
def profile_validator(domain, profile_id=None):
    # Descriptor admission limits identifiers before they select package paths.
    from .state import descriptor
    selected = descriptor(domain, profile_id=profile_id)
    registry = Registry()
    for path in files("mesh_plus").joinpath("schemas").iterdir():
        schema = json.loads(path.read_text())
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    suffix = {"agent-observer.mesh-candidate.v2": "-v2", "agent-observer.mesh-candidate.v3": "-v3"}.get(selected.profile_id, "")
    profile = json.loads(files("mesh_plus").joinpath("schemas", "read-" + domain + suffix + ".profile.schema.json").read_text())
    return Draft202012Validator(profile, registry=registry)


def remote_expiry(sent, received, remaining, margin=100):
    check(all(type(v) is int and v >= 0 for v in (sent, received, remaining, margin)), "proof_integer")
    check(100 <= margin <= 2000 and sent <= received <= sent + 2000, "proof_deadline")
    return received + max(0, remaining - (received - sent) - margin)


def row_host(domain, row):
    return row["hostId"] if domain == "tmux" else row["identity"]["hostScope"]


def reconstructed(response, host, *, profile=None):
    domain = "tmux" if response["protocol"].startswith("tmux-") else "agent"
    profile = resolve_profile(domain, profile)
    return profile.restore_native(host["owner"], [row for row in response["sessions"]
                                                 if profile.record_host(row) == host["hostId"]])


def _validated_response(response, profile=None):
    domain = "tmux" if response.get("protocol") == "tmux-observer.mesh-candidate.v1" else "agent"
    profile = resolve_profile(domain, profile)
    profile_id = profile.descriptor.profile_id
    # A composed response passes several independent consumers in one process.
    # Reuse only static schema success for identical complete JSON bytes. Native
    # validation, proofs, receipts, chronology and current-time checks still run.
    # Keep one digest per frozen profile, rather than retaining response bodies.
    try:
        encoded = encode(response)
    except ValueError:
        profile_validator(domain, profile_id).validate(response)
        raise
    key = hashlib.sha256(encoded).digest() if plain_json(response) else None
    if key is None or _PROFILE_DIGESTS.get(profile_id) != key:
        profile_validator(domain, profile_id).validate(response)
        if key is not None:
            _PROFILE_DIGESTS[profile_id] = key
    check(len(encoded) + 1 <= 16 * 1024 * 1024, "aggregate_capacity")
    profile.validate_response(response)
    mesh = response["mesh"]
    hosts = mesh["hosts"]
    scope = mesh["scope"]["hostIds"]
    check([host["hostId"] for host in hosts] == scope, "host_outcome_scope")
    states = [host["delivery"]["status"] for host in hosts]
    expected = "complete" if all(state == "ready" for state in states) else "partial" if "ready" in states else "pending" if "connecting" in states else "unavailable"
    check(mesh["status"] == expected, "delivery_completeness")
    local_host = mesh["catalog"]["localHostId"]
    if mesh["catalog"]["state"] == "local_only":
        check(scope == [local_host] and mesh["catalog"]["revision"] is None, "local_catalog")
    else:
        check(mesh["catalog"]["revision"] is not None, "catalog_revision")
    references = []
    host_positions = []
    positions = {host: index for index, host in enumerate(scope)}
    records = {host: [] for host in scope}
    for row in response["sessions"]:
        host_id = profile.record_host(row)
        check(host_id in positions, "row_host_scope")
        host_positions.append(positions[host_id])
        records[host_id].append(row)
        identity = profile.record_identity(row)
        check(type(identity) is tuple and bool(identity) and all(type(v) in {str, int} for v in identity),
              "record_identity")
        references.append(identity)
    check(len(references) == len(set(references)), "duplicate_identity")
    check(host_positions == sorted(host_positions), "row_host_order")
    admitted = {}
    for host in hosts:
        host_records = records[host["hostId"]]
        local = host["hostId"] == local_host
        check(host["local"] == local and (host["delivery"]["path"] == "ipc") == local, "local_binding")
        delivery = host["delivery"]
        check((delivery["error"] is None) == (delivery["status"] in {"ready", "connecting"}), "delivery_error")
        check(local or delivery["routeToken"] is not None or delivery["status"] == "connecting", "route_binding")
        current = [r for r in host["receipts"] if r["health"] in {"current", "partial"}]
        check((host["viewState"] == "current") == bool(current), "current_receipt_binding")
        if host["owner"] is None:
            check(not host["receipts"] and not host_records,
                  "rows_without_owner")
            continue
        # Reconstruction may mutate its records list. Keep the admission's
        # grouped rows separate so that projection equality still detects loss.
        frame = profile.restore_native(host["owner"], list(host_records))
        codec = profile.bind(host["hostId"], "default")
        state = inspect_state(profile, codec, frame)
        admitted[host["hostId"]] = state
        check(state.owner == host["owner"] and list(state.records) == host_records, "owner_projection")
        snapshot = state.owner["metadata"]
        check(host["owner"]["protocol"] == profile.descriptor.native_protocol
              and host["owner"]["version"] == profile.descriptor.native_version, "owner_version")
        check(snapshot is not None or not host_records,
              "warming_rows")
        native = {(r["sourceId"], r["component"]): r for r in state.receipts}
        keys = [(r["sourceId"], r["component"]) for r in host["receipts"]]
        check(len(keys) == len(set(keys)) and set(keys) <= set(native) and
              (snapshot is None or set(keys) == set(native)), "receipt_scope")
        check(not current or snapshot is not None, "warming_positive_receipt")
        proof = delivery["proof"]
        if local:
            check(proof is None and state.clock == mesh["reader"]["clock"], "local_clock_scope")
        elif current:
            check(proof is not None and proof["payloadDigest"] == digest(frame) and
                  proof["bridgeClock"] == state.clock and proof["bridgeEncodedAtMs"] >= state.emitted_ms and
                  proof["receivedAtMs"] <= mesh["reader"]["encodedAtMs"], "remote_proof_binding")
        for receipt in host["receipts"]:
            original = native[receipt["sourceId"], receipt["component"]]
            check(receipt["accepted"] == original["accepted"], "receipt_sample_binding")
            if receipt["health"] in {"current", "partial"}:
                check(delivery["status"] == "ready" and original["health"] in {"current", "partial"} and
                      original["accepted"] > 0, "receipt_native_health")
                check(receipt["health"] == original["health"], "receipt_health_upgrade")
                expiry = receipt["expiresAtMs"]
                check(expiry is not None and expiry > mesh["reader"]["encodedAtMs"], "receipt_expired")
                if local:
                    check(expiry == original["expiry"], "local_expiry_changed")
                else:
                    remaining = max(0, original["expiry"] - proof["bridgeEncodedAtMs"])
                    check(receipt["remainingMs"] == remaining and expiry == remote_expiry(
                        proof["sentAtMs"], proof["receivedAtMs"], remaining, proof["marginMs"]), "remaining_lease_changed")
            else:
                check(receipt["expiresAtMs"] is None and receipt["remainingMs"] == 0, "stale_expiry")
    # The bound checks below only read this metadata view. Native bodies are
    # already validated and excluded, so avoid copying them just to discard them.
    metadata = {**response, "sessions": [],
                "mesh": {**mesh, "hosts": [{**host, "owner": None} for host in hosts]}}
    check(len(encode(metadata)) + 1 <= 65536, "metadata_capacity")
    metadata_bounds(metadata)
    return response, admitted


def validate_response(response, *, profile=None):
    return _validated_response(response, profile)[0]


def current_sessions(response, now_ms, clock, *, profile=None):
    """Only records with unexpired scoped leases; never infer idle from absence."""
    domain = "tmux" if response["protocol"].startswith("tmux-") else "agent"
    profile = resolve_profile(domain, profile)
    _, admitted = _validated_response(response, profile)
    check(clock == response["mesh"]["reader"]["clock"] and type(now_ms) is int and
          now_ms >= response["mesh"]["reader"]["encodedAtMs"], "reader_clock_scope")
    rows = []
    for host in response["mesh"]["hosts"]:
        if host["viewState"] != "current" or host["delivery"]["status"] != "ready":
            continue
        state = admitted[host["hostId"]]
        available = {(r["sourceId"], r["component"]) for r in host["receipts"]
                     if r["health"] in {"current", "partial"} and r["expiresAtMs"] > now_ms}
        native = {(r["sourceId"], r["component"]) for r in state.receipts
                  if r["health"] in {"current", "partial"}}
        for row in state.records:
            required = profile.record_receipts(row, state)
            check(required is None or (type(required) is frozenset and all(
                type(k) is tuple and len(k) == 2 and all(type(v) is str for v in k) for k in required)),
                "record_receipt_keys")
            if required and required <= native and required <= available and profile.record_eligible(row, state):
                rows.append(copy.deepcopy(row))

    return rows


class ReadGuard:
    """Per-request replacement stream guard; validity still needs current_sessions."""

    def __init__(self, domain, request_id, *, host_ids=None, profile=None):
        check(domain in {"tmux", "agent"}, "observer_domain")
        self.state_profile = resolve_profile(domain, profile)
        self.profile = self.state_profile.descriptor.profile_id
        self.request_id, self.host_ids = request_id, None if host_ids is None else tuple(host_ids)
        self.binding, self.sequence, self.revision = None, 0, 0
        self.encoded_at, self.scope, self.catalog = 0, None, None
        self.needs_resync, self.closed = False, False
        self.view = None
        self.host_bindings = {}

    def _admit(self, frame):
        return _validated_response(frame, self.state_profile)[1]

    def _retain(self, frame):
        return copy.deepcopy(frame)

    def accept(self, frame):
        check(not self.closed, "read_terminal_barrier")
        if "error" in frame and "mesh" not in frame:
            _control_validator("error").validate(frame)
            check(len(encode(frame)) <= 16384, "error_capacity")
            check(frame["requestId"] == self.request_id, "read_request_binding")
            self.closed = True
            self.view = None
            return frame
        mesh = frame["mesh"]
        control = mesh["kind"] in {"gap", "heartbeat"}
        if control:
            _control_validator("control").validate(frame)
            check(len(encode(frame)) <= 16384, "control_capacity")
            check(self.binding is not None, "read_baseline_required")
        else:
            admitted = self._admit(frame)
        check(frame["protocol"] == self.profile and mesh["requestId"] == self.request_id and
              mesh["operation"] == "watch", "read_request_binding")
        reader = mesh["reader"]
        binding = (reader["id"], reader["clock"])
        check(self.binding is None or binding == self.binding, "read_incarnation_binding")
        check(reader["sequence"] == self.sequence + 1 and reader["encodedAtMs"] >= self.encoded_at, "read_order")
        check(self.revision <= reader["revision"] <= self.revision + 1 and
              reader["revision"] <= reader["sequence"], "read_revision")
        if control:
            check(reader["revision"] == self.revision, "control_revision")
        else:
            scope, catalog = tuple(mesh["scope"]["hostIds"]), mesh["catalog"]
            check(self.host_ids is None or scope == self.host_ids, "read_scope_binding")
            check(self.scope is None or (scope == self.scope and catalog == self.catalog), "read_scope_binding")
            check(not self.needs_resync or mesh["kind"] == "resync", "read_resync_required")
            next_hosts = {}
            for host in mesh["hosts"]:
                epoch = host["delivery"]["epoch"]
                owner = host["owner"]
                publisher = None
                if owner is not None:
                    publisher = admitted[host["hostId"]].publisher
                previous = self.host_bindings.get(host["hostId"])
                if previous is not None:
                    check(epoch >= previous[0], "read_host_epoch_regression")
                    restart = epoch > previous[0] or (publisher is not None and previous[1] is not None and publisher != previous[1])
                    check(not restart or mesh["kind"] == "resync", "read_resync_required")
                    publisher = previous[1] if publisher is None else publisher
                next_hosts[host["hostId"]] = epoch, publisher
        # Commit only after every admission check; bad frames cannot advance a guard.
        self.binding = copy.deepcopy(binding)
        self.sequence, self.revision, self.encoded_at = reader["sequence"], reader["revision"], reader["encodedAtMs"]
        if control:
            self.needs_resync = self.needs_resync or mesh["kind"] == "gap"
            if self.needs_resync:
                self.view = None
        else:
            self.scope, self.catalog = scope, copy.deepcopy(catalog)
            self.needs_resync = False
            self.view = self._retain(frame)
            self.host_bindings = next_hosts
        return frame

    def current(self, now_ms, clock):
        if self.closed or self.needs_resync or self.view is None:
            return []
        return current_sessions(self.view, now_ms, clock, profile=self.state_profile)

    def disconnect(self):
        """EOF/framing/liveness failure revokes cached positives immediately."""
        self.closed, self.view = True, None
