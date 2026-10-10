"""Pure mesh-aware domain facade. Original records remain owner attributable."""

import copy
import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .observer import ObserverCodec, digest
from .protocol import check, encode, metadata_bounds


@lru_cache(maxsize=2)
def profile_validator(domain):
    registry = Registry()
    for path in files("mesh_plus").joinpath("schemas").iterdir():
        schema = json.loads(path.read_text())
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    profile = json.loads(files("mesh_plus").joinpath("schemas", "read-" + domain + ".profile.schema.json").read_text())
    return Draft202012Validator(profile, registry=registry)


def remote_expiry(sent, received, remaining, margin=100):
    check(all(type(v) is int and v >= 0 for v in (sent, received, remaining, margin)), "proof_integer")
    check(100 <= margin <= 2000 and sent <= received <= sent + 2000, "proof_deadline")
    return received + max(0, remaining - (received - sent) - margin)


def row_host(domain, row):
    return row["hostId"] if domain == "tmux" else row["identity"]["hostScope"]


def reconstructed(response, host):
    domain = "tmux" if response["protocol"].startswith("tmux-") else "agent"
    metadata = host["owner"]["metadata"]
    snapshot = None if metadata is None else {**metadata, "sessions": [row for row in response["sessions"]
                                                                      if row_host(domain, row) == host["hostId"]]}
    return {**host["owner"]["service"], "snapshot": snapshot}


def validate_response(response):
    domain = "tmux" if response.get("protocol") == "tmux-observer.mesh-candidate.v1" else "agent"
    profile_validator(domain).validate(response)
    check(len(encode(response)) + 1 <= 16 * 1024 * 1024, "aggregate_capacity")
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
    for row in response["sessions"]:
        check(row_host(domain, row) in scope, "row_host_scope")
        host_positions.append(scope.index(row_host(domain, row)))
        references.append(tuple(row[k] for k in ("hostId", "serverGeneration", "sessionId", "createdAt")) if domain == "tmux"
                          else tuple(row["identity"][k] for k in ("hostScope", "provider", "namespace", "nativeIdKind", "nativeId")))
    check(len(references) == len(set(references)), "duplicate_identity")
    check(host_positions == sorted(host_positions), "row_host_order")
    for host in hosts:
        local = host["hostId"] == local_host
        check(host["local"] == local and (host["delivery"]["path"] == "ipc") == local, "local_binding")
        delivery = host["delivery"]
        check((delivery["error"] is None) == (delivery["status"] in {"ready", "connecting"}), "delivery_error")
        check(local or delivery["routeToken"] is not None or delivery["status"] == "connecting", "route_binding")
        current = [r for r in host["receipts"] if r["health"] in {"current", "partial"}]
        check((host["viewState"] == "current") == bool(current), "current_receipt_binding")
        if host["owner"] is None:
            check(not host["receipts"] and not any(row_host(domain, row) == host["hostId"] for row in response["sessions"]),
                  "rows_without_owner")
            continue
        frame = reconstructed(response, host)
        codec = ObserverCodec(domain, host["hostId"], "default")
        codec.native(frame)
        snapshot = frame["snapshot"]
        check(host["owner"]["protocol"] == ("tmux-observer.observation.v1" if domain == "tmux" else "agent-observer.snapshot")
              and host["owner"]["version"] == (1 if domain == "tmux" else 4), "owner_version")
        check(snapshot is not None or not any(row_host(domain, row) == host["hostId"] for row in response["sessions"]),
              "warming_rows")
        native = {(r["sourceId"], r["component"]): r for r in codec.receipts(frame)}
        keys = [(r["sourceId"], r["component"]) for r in host["receipts"]]
        check(len(keys) == len(set(keys)) and set(keys) <= set(native) and
              (snapshot is None or set(keys) == set(native)), "receipt_scope")
        check(not current or snapshot is not None, "warming_positive_receipt")
        proof = delivery["proof"]
        if local:
            check(proof is None and codec.clock(frame) == mesh["reader"]["clock"], "local_clock_scope")
        elif current:
            check(proof is not None and proof["payloadDigest"] == digest(frame) and
                  proof["bridgeClock"] == codec.clock(frame) and proof["bridgeEncodedAtMs"] >= codec.emitted(frame) and
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
    metadata = copy.deepcopy(response)
    metadata["sessions"] = []
    for host in metadata["mesh"]["hosts"]:
        host["owner"] = None
    check(len(encode(metadata)) + 1 <= 65536, "metadata_capacity")
    metadata_bounds(metadata)
    return response


def current_sessions(response, now_ms, clock):
    """Only records with unexpired scoped leases; never infer idle from absence."""
    validate_response(response)
    check(clock == response["mesh"]["reader"]["clock"] and type(now_ms) is int and
          now_ms >= response["mesh"]["reader"]["encodedAtMs"], "reader_clock_scope")
    domain = "tmux" if response["protocol"].startswith("tmux-") else "agent"
    rows = []
    for host in response["mesh"]["hosts"]:
        if host["viewState"] != "current" or host["delivery"]["status"] != "ready":
            continue
        codec = ObserverCodec(domain, host["hostId"], "default")
        native = codec.receipts(reconstructed(response, host))
        for row in response["sessions"]:
            if row_host(domain, row) != host["hostId"]:
                continue
            source = "default" if domain == "tmux" else row["identity"]["provider"] + ":" + row["identity"]["namespace"]
            active = [r for r in host["receipts"] if r["sourceId"] == source and r["health"] in {"current", "partial"}]
            expected = {r["component"] for r in native if r["sourceId"] == source and r["health"] in {"current", "partial"}}
            if active and {r["component"] for r in active} == expected and all(r["expiresAtMs"] > now_ms for r in active):
                rows.append(copy.deepcopy(row))
    return rows


class ReadGuard:
    """Per-request replacement stream guard; validity still needs current_sessions."""

    def __init__(self, domain, request_id, *, host_ids=None):
        check(domain in {"tmux", "agent"}, "observer_domain")
        self.profile = domain + "-observer.mesh-candidate.v1"
        self.request_id, self.host_ids = request_id, None if host_ids is None else tuple(host_ids)
        self.binding, self.sequence, self.revision = None, 0, 0
        self.encoded_at, self.scope, self.catalog = 0, None, None
        self.needs_resync, self.closed = False, False
        self.view = None
        self.host_bindings = {}

    def accept(self, frame):
        check(not self.closed, "read_terminal_barrier")
        if "error" in frame and "mesh" not in frame:
            schema = json.loads(files("mesh_plus").joinpath("schemas", "read-error.schema.json").read_text())
            Draft202012Validator(schema).validate(frame)
            check(len(encode(frame)) <= 16384, "error_capacity")
            check(frame["requestId"] == self.request_id, "read_request_binding")
            self.closed = True
            self.view = None
            return frame
        mesh = frame["mesh"]
        control = mesh["kind"] in {"gap", "heartbeat"}
        if control:
            schema = json.loads(files("mesh_plus").joinpath("schemas", "read-control.schema.json").read_text())
            Draft202012Validator(schema).validate(frame)
            check(len(encode(frame)) <= 16384, "control_capacity")
            check(self.binding is not None, "read_baseline_required")
        else:
            validate_response(frame)
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
                publisher = None if owner is None else owner["service"].get("publisherId", owner["service"].get("serviceId"))
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
            self.view = copy.deepcopy(frame)
            self.host_bindings = next_hosts
        return frame

    def current(self, now_ms, clock):
        if self.closed or self.needs_resync or self.view is None:
            return []
        return current_sessions(self.view, now_ms, clock)

    def disconnect(self):
        """EOF/framing/liveness failure revokes cached positives immediately."""
        self.closed, self.view = True, None
