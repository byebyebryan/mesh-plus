"""Pure mesh-aware domain facade. Original records remain owner attributable."""

import copy
import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .observer import ObserverCodec, digest
from .protocol import check, encode


def metadata_bounds(value):
    nodes = 0

    def visit(item, depth=0, field=None):
        nonlocal nodes
        nodes += 1
        check(nodes <= 8192 and depth <= 12, "metadata_tree_capacity")
        if isinstance(item, dict):
            for key, child in item.items():
                nodes += 1
                check(len(key) <= 128, "metadata_key_capacity")
                visit(child, depth + 1, key)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1, field)
        elif isinstance(item, str):
            maximum = 16384 if field in {"hostId", "hostIds", "localHostId", "expectedHost"} else 4096
            check(len(item) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in item), "metadata_string_capacity")
    visit(value)


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
    for row in response["sessions"]:
        check(row_host(domain, row) in scope, "row_host_scope")
        references.append(tuple(row[k] for k in ("hostId", "serverGeneration", "sessionId", "createdAt")) if domain == "tmux"
                          else tuple(row["identity"][k] for k in ("hostScope", "provider", "namespace", "nativeIdKind", "nativeId")))
    check(len(references) == len(set(references)), "duplicate_identity")
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
