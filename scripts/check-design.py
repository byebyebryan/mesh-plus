"""Offline structural and adversarial checks for the Mesh design candidate.

The model below is validation tooling. It neither collects sources nor provides
a runtime Mesh client. --check-sources invokes only existing pure validators.
"""

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/mesh-read-v1"
PREFIX = "urn:mesh-plus:read:1:"
CHECKS = []


def require(condition, code):
    if not condition:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(path.read_text())


def wire(data, limit=16 * 1024 * 1024, line_framed=True):
    require(len(data) <= limit, "wire_capacity")
    require(data.endswith(b"\n") and not data.endswith(b"\n\n"), "wire_final_lf")
    require(not data.startswith(b"\xef\xbb\xbf"), "wire_bom")
    body = data[:-1].decode("utf-8", errors="strict")
    require(body and body[-1] not in " \t\r\n", "wire_trailing_space")
    require(not line_framed or "\n" not in body and "\r" not in body, "wire_multiple_lines")

    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "wire_duplicate_key")
            out[key] = value
        return out

    def reject_constant(value):
        raise ValueError("wire_nonfinite")

    result = json.loads(body, object_pairs_hook=pairs, parse_constant=reject_constant)
    # Reject actual NUL/surrogates after JSON escape decoding as well.
    def strings(value):
        if isinstance(value, str):
            require("\x00" not in value and not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "wire_unicode")
        elif isinstance(value, dict):
            for key, item in value.items():
                strings(key)
                strings(item)
        elif isinstance(value, list):
            for item in value:
                strings(item)
    strings(result)
    return result


SCHEMAS = {}
registry = Registry()
for path in sorted(list(BASE.glob("*.schema.json")) + [BASE / "schema.json"] + list((ROOT / "reference").rglob("*.schema.json")) + list((ROOT / "reference/tmux-observer/contracts").glob("*/schema.json"))):
    value = read(path)
    Draft202012Validator.check_schema(value)
    resource = Resource.from_contents(value)
    registry = registry.with_resource(path.as_uri(), resource)
    if "$id" in value:
        registry = registry.with_resource(value["$id"], resource)
        SCHEMAS[value["$id"]] = value
    SCHEMAS[path.as_uri()] = value


def structural(value, name):
    Draft202012Validator(SCHEMAS[name], registry=registry).validate(value)


def test(name, operation):
    operation()
    CHECKS.append({"name": name, "result": "passed"})


def rejects(name, operation, code=None):
    try:
        operation()
    except (ValueError, ValidationError) as error:
        if code is not None:
            require(str(error) == code, f"wrong rejection for {name}: {error}")
    else:
        raise AssertionError(f"accepted forbidden case: {name}")
    CHECKS.append({"name": name, "result": "passed", "expectation": "reject"})


def response_domain(value):
    return "tmux" if value["protocol"].startswith("tmux-") else "agent"


def row_host(domain, row):
    return row["hostId"] if domain == "tmux" else row["identity"]["hostScope"]


def identity(domain, row):
    if domain == "tmux":
        return tuple(row[k] for k in ["hostId", "serverGeneration", "sessionId", "createdAt"])
    return tuple(row["identity"][k] for k in ["hostScope", "provider", "namespace", "nativeIdKind", "nativeId"])


def reconstructed(value, host):
    if host["owner"] is None or host["owner"]["metadata"] is None:
        return None
    domain = response_domain(value)
    return {**host["owner"]["metadata"], "sessions": [r for r in value["sessions"] if row_host(domain, r) == host["hostId"]]}


def reconstructed_frame(value, host):
    return {**host["owner"]["service"], "snapshot": reconstructed(value, host)}


def source_clock(domain, frame):
    if domain == "tmux":
        return frame["clock"]
    match=re.fullmatch(r"time:\[([0-9]+)\]",frame["clockDomain"])
    require(match is not None,"unsupported_clock_encoding")
    return {"bootId": frame["bootId"], "timeNamespace": "time:"+match[1]}


def source_receipts(domain, frame):
    if domain == "tmux":
        r = frame["receipt"]
        return {("default", "native"): {"accepted": r["accepted"], "expiry": r["expiresAt"], "health": "current" if r["state"] == "ready" else "stale"}}
    return {(s["provider"] + ":" + s["namespace"], c["name"]):
            {"accepted": c["accepted"], "expiry": c["expiresBoottimeMs"], "health": c["health"]}
            for s in frame["sources"] for c in s["components"]}


def remote_expiry(sent, received, remaining, margin=100):
    require(all(type(v) is int and v >= 0 for v in [sent, received, remaining, margin]), "proof_integer")
    require(margin >= 100 and sent <= received <= sent + 2000, "proof_deadline")
    return received + max(0, remaining - (received - sent) - margin)


def validate_request(value):
    structural(value, PREFIX + "request")
    selection = value["selection"]
    require(bool(selection["hostIds"]) == (selection["mode"] == "hosts"), "selection_shape")
    require(len(canonical(value)) + 1 <= 16384, "request_capacity")
    common_bounds(value)


def common_bounds(value):
    nodes = 0

    def visit(item, depth=0, field=None):
        nonlocal nodes
        nodes += 1
        require(nodes <= 8192 and depth <= 12, "metadata_tree_capacity")
        if isinstance(item, dict):
            for key, child in item.items():
                nodes += 1
                require(len(key) <= 128, "metadata_key_capacity")
                visit(child, depth+1, key)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth+1, field)
        elif isinstance(item, str):
            maximum = 16384 if field in ["hostId", "hostIds", "localHostId", "expectedHost"] else 4096
            require(len(item) <= maximum and not any(ord(c)<32 or ord(c)==127 for c in item), "metadata_string_capacity")
    visit(value)


def validate_response(value):
    domain = response_domain(value)
    structural(value, PREFIX + domain + "-profile")
    require(len(canonical(value)) + 1 <= 16 * 1024 * 1024, "aggregate_capacity")
    mesh = value["mesh"]
    hosts = mesh["hosts"]
    require([h["hostId"] for h in hosts] == mesh["scope"]["hostIds"], "host_outcome_scope")
    local = mesh["catalog"]["localHostId"]
    require(all(h["local"] == (h["hostId"] == local) for h in hosts), "local_binding")
    if mesh["catalog"]["state"] == "local_only":
        require(mesh["scope"]["hostIds"] == [local] and mesh["catalog"]["revision"] is None, "local_catalog")
    else:
        require(mesh["catalog"]["revision"] is not None, "catalog_revision")
    states = [h["delivery"]["status"] for h in hosts]
    expected = "complete" if all(s == "ready" for s in states) else "partial" if "ready" in states else "pending" if "connecting" in states else "unavailable"
    require(mesh["status"] == expected, "delivery_completeness")
    known = set(mesh["scope"]["hostIds"])
    require(all(row_host(domain, row) in known for row in value["sessions"]), "row_host_scope")
    positions = [mesh["scope"]["hostIds"].index(row_host(domain, row)) for row in value["sessions"]]
    require(positions == sorted(positions), "row_host_order")
    refs = [identity(domain, row) for row in value["sessions"]]
    require(len(set(refs)) == len(refs), "duplicate_identity")
    minimal = copy.deepcopy(value)
    minimal["sessions"] = []
    for h in minimal["mesh"]["hosts"]:
        h["owner"] = None
    require(len(canonical(minimal)) + 1 <= 65536, "metadata_capacity")
    common_bounds(minimal)
    for host in hosts:
        delivery = host["delivery"]
        require((delivery["path"] == "ipc") == host["local"], "dispatch_path")
        require((delivery["routeToken"] is None) == host["local"] or delivery["status"] == "connecting", "route_binding")
        require(delivery["status"] not in ["ready", "connecting"] or delivery["error"] is None, "delivery_error")
        require(delivery["status"] in ["ready", "connecting"] or delivery["error"] is not None, "missing_delivery_error")
        current = [r for r in host["receipts"] if r["health"] in ["current", "partial"]]
        if host["viewState"] == "current":
            require(delivery["status"] == "ready" and host["owner"] is not None and host["owner"]["metadata"] is not None and bool(current), "unproved_current_view")
        else:
            require(not current, "historical_positive_receipt")
        require(host["owner"] is not None or not any(row_host(domain, row) == host["hostId"] for row in value["sessions"]), "rows_without_owner")
        require(host["viewState"] not in ["current", "historical"] or host["owner"] is not None, "missing_owner")
        require(host["owner"] is None or host["owner"]["metadata"] is not None or not any(row_host(domain, row) == host["hostId"] for row in value["sessions"]), "warming_rows")
        if host["owner"] is None:
            require(not host["receipts"], "receipts_without_owner")
            continue
        snap = reconstructed(value, host)
        if snap is not None:
            schema_id = "https://tmux-observer.invalid/contracts/observation-v1/schema.json" if domain == "tmux" else "urn:agent-observer:snapshot:4"
            structural(snap, schema_id)
            require(len(canonical(snap)) + 1 <= (1024*1024 if domain == "tmux" else 8*1024*1024-1024), "native_document_capacity")
            returned_host = snap["source"]["hostId"] if domain == "tmux" else snap["host"]["authority"]
            require(returned_host == host["hostId"], "owner_host_scope")
            require(host["owner"]["protocol"] == ("tmux-observer.observation.v1" if domain == "tmux" else "agent-observer.snapshot"), "owner_protocol")
            require(host["owner"]["version"] == (1 if domain == "tmux" else 4), "owner_version")
        require(host["owner"]["service"] is not None, "cached_service_required")
        frame = reconstructed_frame(value, host)
        schema_id = "https://tmux-observer.invalid/contracts/service-v1/schema.json" if domain == "tmux" else "urn:agent-observer:service-frame:2"
        structural(frame, schema_id)
        require(len(canonical(frame)) + 1 <= (1024*1024+16384 if domain == "tmux" else 8*1024*1024+16384), "native_frame_capacity")
        clock = source_clock(domain, frame)
        received_host = frame["source"]["hostId"] if domain == "tmux" else frame["hostScope"]
        require(received_host == host["hostId"], "service_host_scope")
        native = source_receipts(domain, frame)
        proof = delivery["proof"]
        if host["local"]:
            require(proof is None and clock == mesh["reader"]["clock"], "local_clock_scope")
        elif host["viewState"] == "current":
            require(proof is not None, "remote_proof_required")
            require(proof["payloadDigest"] == digest(frame), "proof_payload_binding")
            require(proof["bridgeClock"] == clock, "bridge_clock_scope")
            source_encoded = frame["encodedAt"] if domain == "tmux" else frame["emittedBoottimeMs"]
            require(proof["bridgeEncodedAtMs"] >= source_encoded, "bridge_encoding_before_source")
            require(proof["receivedAtMs"] <= mesh["reader"]["encodedAtMs"], "proof_future")
        keys = [(r["sourceId"], r["component"]) for r in host["receipts"]]
        require(len(set(keys)) == len(keys), "duplicate_receipt")
        if snap is not None:
            require(set(keys) == set(native), "missing_source_receipt")
        for receipt in host["receipts"]:
            key = receipt["sourceId"], receipt["component"]
            require(key in native, "unknown_receipt")
            item = native[key]
            require(receipt["accepted"] == item["accepted"], "receipt_sample_binding")
            if receipt["health"] in ["current", "partial"]:
                require(item["health"] in ["current", "partial"] and item["expiry"] is not None and receipt["accepted"] > 0, "receipt_native_health")
                require(receipt["health"] == item["health"], "receipt_health_upgrade")
                require(receipt["expiresAtMs"] is not None and receipt["expiresAtMs"] > mesh["reader"]["encodedAtMs"], "receipt_expired")
                if host["local"]:
                    require(receipt["expiresAtMs"] == item["expiry"], "local_expiry_changed")
                else:
                    remaining = max(0, item["expiry"] - proof["bridgeEncodedAtMs"])
                    require(receipt["remainingMs"] == remaining, "remaining_lease_changed")
                    require(receipt["expiresAtMs"] == remote_expiry(proof["sentAtMs"], proof["receivedAtMs"], remaining, proof["marginMs"]), "remote_expiry_changed")
            else:
                require(receipt["expiresAtMs"] is None and receipt["remainingMs"] == 0, "stale_expiry")
    if mesh["kind"] == "gap":
        require(all(h["viewState"] != "current" for h in hosts), "gap_positive_view")
    return value


def effective_current(value, now, clock):
    """Conservative design oracle; production projection belongs to each domain."""
    validate_response(value)
    require(clock == value["mesh"]["reader"]["clock"], "reader_clock_scope")
    require(type(now) is int and now >= value["mesh"]["reader"]["encodedAtMs"], "reader_clock_regressed")
    domain = response_domain(value)
    rows = []
    for host in value["mesh"]["hosts"]:
        if host["viewState"] != "current" or host["delivery"]["status"] != "ready":
            continue
        original = source_receipts(domain, reconstructed_frame(value, host))
        for row in value["sessions"]:
            if row_host(domain, row) != host["hostId"]:
                continue
            source = "default" if domain == "tmux" else row["identity"]["provider"] + ":" + row["identity"]["namespace"]
            receipts = [r for r in host["receipts"] if r["sourceId"] == source and r["health"] in ["current", "partial"]]
            expected = {component for (source_id, component), receipt in original.items()
                        if source_id == source and receipt["health"] in ["current", "partial"]}
            if receipts and {r["component"] for r in receipts} == expected and all(r["expiresAtMs"] > now for r in receipts):
                rows.append(row)
    return rows


def validate_bridge(reply, request):
    structural(request, PREFIX + "bridge-request")
    structural(reply, PREFIX + "bridge-reply")
    require(reply["kind"]=="proof", "bridge_correlated_kind")
    require(reply["nonce"] == request["nonce"] and reply["hostId"] == request["expectedHost"] and reply["sourceId"] == request["sourceId"], "bridge_request_binding")
    if reply["ownerFrame"] is None:
        require(reply["error"] is not None and reply["ownerDigest"] is None and not reply["remaining"], "bridge_error_shape")
        return
    require(reply["error"] is None, "bridge_success_error")
    require(reply["ownerDigest"] == digest(reply["ownerFrame"]), "bridge_payload_digest")
    frame = reply["ownerFrame"]
    # The frozen bridge example is Agent service 2.
    structural(frame, "urn:agent-observer:service-frame:2")
    require(frame["hostScope"] == reply["hostId"] and source_clock("agent", frame) == reply["clock"], "bridge_source_scope")
    require(reply["encodedAtMs"] >= frame["emittedBoottimeMs"], "bridge_clock_regression")
    native = source_receipts("agent", frame)
    keys = [(r["sourceId"], r["component"]) for r in reply["remaining"]]
    require(len(keys) == len(set(keys)), "bridge_duplicate_receipt")
    require(set(native) == {(r["sourceId"], r["component"]) for r in reply["remaining"]}, "bridge_receipt_scope")
    for r in reply["remaining"]:
        original = native[r["sourceId"], r["component"]]
        expected_remaining = max(0, original["expiry"] - reply["encodedAtMs"]) if original["health"] in ["current", "partial"] else 0
        require(r["health"] == original["health"] and r["accepted"] == original["accepted"] and r["remainingMs"] == expected_remaining, "bridge_original_lease")


class StreamOracle:
    """Validate the candidate stream contract; no transport implementation."""

    def __init__(self):
        self.binding = self.previous = None
        self.full_binding = None
        self.gapped = False
        self.closed = False

    def accept(self, value):
        require(not self.closed, "stream_closed")
        if "error" in value:
            structural(value, PREFIX+"error")
            require(self.previous is not None and value["requestId"] == self.previous["mesh"]["requestId"], "stream_error_binding")
            self.closed = True
            self.gapped = True
            return
        full = "sessions" in value
        if full:
            validate_response(value)
        else:
            validate_control(value)
        mesh = value["mesh"]
        binding = (value["protocol"], mesh["requestId"], mesh["operation"], mesh["reader"]["id"],
                   canonical(mesh["reader"]["clock"]))
        full_binding = (canonical(mesh["catalog"]), tuple(mesh["scope"]["hostIds"])) if full else None
        if self.binding is None:
            require(mesh["kind"] in ["view", "resync"] and mesh["reader"]["sequence"] == 1, "stream_initial")
        else:
            require(binding == self.binding, "stream_binding_changed")
            require(not full or full_binding == self.full_binding, "stream_binding_changed")
            before = self.previous["mesh"]
            require(mesh["reader"]["sequence"] == before["reader"]["sequence"] + 1 and mesh["reader"]["revision"] >= before["reader"]["revision"], "stream_order")
            require(mesh["reader"]["encodedAtMs"] >= before["reader"]["encodedAtMs"], "stream_clock_regression")
            require(not self.gapped or not full or mesh["kind"] == "resync", "stream_resync_required")
            if mesh["kind"] == "heartbeat":
                require(mesh["reader"]["revision"] == before["reader"]["revision"], "heartbeat_renewed_evidence")
        self.binding = binding
        if full:
            self.full_binding = full_binding
        self.previous = copy.deepcopy(value)
        if mesh["kind"] == "gap":
            self.gapped = True
        elif mesh["kind"] == "resync":
            self.gapped = False


def validate_control(value):
    structural(value, PREFIX+response_domain(value)+"-stream")
    structural(value, PREFIX+"control")
    require(len(canonical(value))+1 <= 65536, "control_capacity")
    common_bounds(value)


def control_for(value, kind, sequence, revision, encoded_at):
    mesh=value["mesh"]
    control={"protocol":value["protocol"],"schemaVersion":value["schemaVersion"],
             "mesh":{k:copy.deepcopy(mesh[k]) for k in ["meshProtocol","requestId","operation","access","reader"]} | {"kind":kind}}
    control["mesh"]["reader"].update(sequence=sequence,revision=revision,encodedAtMs=encoded_at)
    return control


def validate_bridge_event(event, host_id, source_id):
    structural(event,PREFIX+"bridge-reply")
    require(event["hostId"]==host_id and event["sourceId"]==source_id,"bridge_event_scope")
    require(event["kind"]!="proof" and event["nonce"] is None,"bridge_unsolicited_nonce")
    require(not event["remaining"],"bridge_unsolicited_receipts")
    if event["kind"]=="candidate":
        require(event["ownerFrame"] is not None and event["ownerDigest"]==digest(event["ownerFrame"]),"bridge_candidate_digest")
        structural(event["ownerFrame"],"urn:agent-observer:service-frame:2")
        require(event["ownerFrame"]["hostScope"]==host_id and source_clock("agent",event["ownerFrame"])==event["clock"],"bridge_candidate_scope")
    else:
        require(event["ownerFrame"] is None and event["ownerDigest"] is None,"bridge_control_payload")
        require((event["error"] is not None)==(event["kind"]=="error"),"bridge_control_error")


class ProofOracle:
    """One correlated full reply per outstanding epoch and nonce."""

    def __init__(self, request, epoch, sent_at):
        self.request = request
        self.epoch, self.sent_at, self.used = epoch, sent_at, False

    def accept(self, reply, epoch, received_at):
        require(not self.used and epoch == self.epoch, "proof_replay_or_epoch")
        remote_expiry(self.sent_at, received_at, 0)
        validate_bridge(reply, self.request)
        self.used = True


def baseline_checks(check_sources):
    manifest = read(ROOT / "docs/evidence/source-baselines.json")
    for repo, info in manifest["repositories"].items():
        for item in info["files"]:
            if "frozenPath" in item:
                require(hashlib.sha256((ROOT/item["frozenPath"]).read_bytes()).hexdigest() == item["sha256"], "frozen_baseline_changed")
        if check_sources:
            path = ROOT.parent/repo
            require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip() == info["head"], "source_head_changed:"+repo)
            for item in info["files"]:
                require(hashlib.sha256((path/item["path"]).read_bytes()).hexdigest() == item["sha256"], "source_file_changed:"+repo+":"+item["path"])


def producer_validation():
    # Black-box existing pure public validators against all reconstructed owners.
    # No collector, provider query, endpoint, service start or mutable source file.
    program = r'''
import json, sys
sys.dont_write_bytecode = True
from pathlib import Path
root=Path(sys.argv[1]); repo=Path(sys.argv[2]); domain=sys.argv[3]
sys.path.insert(0, str(repo/'src' if domain=='tmux' else repo))
if domain=='tmux':
    from tmux_observer.native import validate_observation as snapshot
    from tmux_observer.delivery import validate_service_frame as service
else:
    from agent_observer.public import validate_snapshot as snapshot
    from agent_observer.service_public import validate_frame as service
count=0
for path in (root/'contracts/mesh-read-v1/examples').glob(domain+'-*.json'):
    value=json.loads(path.read_text())
    for host in value['mesh']['hosts']:
        if host['owner'] is None: continue
        metadata=host['owner']['metadata']
        rows=[r for r in value['sessions'] if (r['hostId'] if domain=='tmux' else r['identity']['hostScope'])==host['hostId']]
        doc=None if metadata is None else {**metadata,'sessions':rows}
        if doc is not None: snapshot(doc)
        service({**host['owner']['service'],'snapshot':doc})
        count+=1
for forbidden in ['agent_observer.collection','agent_observer.adapters','agent_observer.service_runtime','agent_observer.write_cli','tmux_observer.core','tmux_observer.owner']:
    assert forbidden not in sys.modules, forbidden
print(json.dumps({'domain':domain,'ownersValidated':count,'pureImports':True}))
'''
    results = []
    for domain, repo in [("tmux", "tmux-observer"), ("agent", "agent-observer")]:
        result = subprocess.run([sys.executable, "-I", "-c", program, str(ROOT), str(ROOT.parent/repo), domain], capture_output=True, text=True, check=False)
        require(result.returncode == 0, f"pure producer validation failed: {result.stderr}")
        results.append(json.loads(result.stdout))
    return results


def check_links(pending_output=None):
    for path in [ROOT/"README.md", *sorted((ROOT/"docs").rglob("*.md")), *sorted((ROOT/"contracts").rglob("*.md"))]:
        text = path.read_text()
        require(text.endswith("\n"), "missing_final_newline:"+str(path))
        require(not any(line.rstrip() != line for line in text.splitlines()), "trailing_whitespace:"+str(path))
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            linked = (path.parent/target.split("#", 1)[0]).resolve()
            require(linked.is_relative_to(ROOT), "external_checkout_link:"+target)
            require(linked.exists() or linked == pending_output, "missing_link:"+target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-sources", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    test("frozen source digests" + (" and current checkout parity" if args.check_sources else ""), lambda: baseline_checks(args.check_sources))
    examples = sorted((BASE/"examples").glob("*.json"))
    responses = {}
    for path in examples:
        value = read(path)
        if path.name.startswith(("tmux-", "agent-")):
            test("valid profile " + path.stem, lambda v=value: validate_response(v))
            responses[path.stem] = value
        elif path.name.startswith("request-"):
            test("valid " + path.stem, lambda v=value: structural(v, PREFIX+"error") if "error" in v else validate_request(v))
        elif path.name.startswith("control-"):
            test("valid "+path.stem,lambda v=value:validate_control(v))
    bridge_request = read(BASE/"examples/bridge-request.json")
    bridge_reply = read(BASE/"examples/bridge-reply.json")
    test("correlated host-local bridge proof", lambda: validate_bridge(bridge_reply, bridge_request))
    for filename in ["bridge-candidate.json","bridge-heartbeat.json"]:
        event=read(BASE/"examples"/filename)
        test("valid "+filename,lambda e=event:validate_bridge_event(e,bridge_request["expectedHost"],bridge_request["sourceId"]))
    for domain in ["tmux", "agent"]:
        local = responses[domain+"-local"]
        fleet = responses[domain+"-fleet"]
        fixture = ROOT/("reference/tmux-observer/contracts/observation-v1/fixtures/complete.json" if domain == "tmux" else "reference/agent-observer/tests/fixtures/contract-v4/claude-interactive.json")
        test(domain+" lossless original snapshot reconstruction", lambda v=local, f=fixture: require(reconstructed(v, v["mesh"]["hosts"][0]) == read(f), "projection_changed_original"))
        test(domain+" same local and fleet selector", lambda a=local,b=fleet,d=domain: require(effective_current(a, 2000, a["mesh"]["reader"]["clock"]) == [r for r in effective_current(b, 2000, b["mesh"]["reader"]["clock"]) if row_host(d, r) == a["mesh"]["catalog"]["localHostId"]], "local_fleet_selector_changed"))
        test(domain+" cross-host equal native IDs stay distinct", lambda v=fleet,d=domain: require(len({identity(d,r) for r in v["sessions"]}) == len(v["sessions"]), "host_collision"))
        test(domain+" expiry while retaining cached response", lambda v=local: require(not effective_current(v, 400000, v["mesh"]["reader"]["clock"]), "expired_positive"))
        historical = responses[domain+"-historical"]
        test(domain+" historical delivery cannot supply current rows", lambda v=historical: require(not effective_current(v, 2000, v["mesh"]["reader"]["clock"]), "historical_positive"))
        partial = responses[domain+"-partial-host"]
        test(domain+" unavailable sibling preserves healthy rows", lambda v=partial,a=local: require(effective_current(v,2000,v["mesh"]["reader"]["clock"]) == a["sessions"], "sibling_failure"))
    test("complete delivery preserves partial Claude coverage", lambda: require(responses["agent-local"]["mesh"]["status"] == "complete" and any(s["coverage"]["runtime"]["status"] == "partial" for s in responses["agent-local"]["mesh"]["hosts"][0]["owner"]["metadata"]["sources"]), "coverage_upgraded"))
    test("empty and warming have distinct metadata", lambda: require(responses["tmux-empty"]["mesh"]["hosts"][0]["owner"]["metadata"] is not None and responses["tmux-warming"]["mesh"]["hosts"][0]["owner"]["metadata"] is None, "warming_is_empty"))
    test("conservative numeric remote proof", lambda: require(remote_expiry(1000,1200,10000) == 10900, "expiry_equation"))
    test("expired during round trip", lambda: require(remote_expiry(1000,1200,250) == 1200, "expired_roundtrip"))
    rejects("late proof", lambda: remote_expiry(1000,3001,10000), "proof_deadline")
    rejects("cross-clock negative RTT", lambda: remote_expiry(2000,1000,10000), "proof_deadline")
    rejects("boolean proof counter", lambda: remote_expiry(True,1200,10000), "proof_integer")
    # Mutations target contract invariants, independently of the example builder.
    def mutate(name, key, fn, code=None):
        value=copy.deepcopy(responses[key]); fn(value)
        rejects(name, lambda: validate_response(value), code)
    mutate("missing selected host outcome", "tmux-fleet", lambda v: v["mesh"]["hosts"].pop(), "host_outcome_scope")
    mutate("foreign record host", "tmux-local", lambda v: v["sessions"][0].update(hostId="other"), "row_host_scope")
    mutate("duplicate exact native identity", "agent-local", lambda v: v["sessions"].append(copy.deepcopy(v["sessions"][0])), "duplicate_identity")
    mutate("owner host relabelling", "agent-local", lambda v: v["mesh"]["hosts"][0]["owner"]["metadata"]["host"].update(authority="other"), "owner_host_scope")
    mutate("wrong local clock domain", "agent-local", lambda v: v["mesh"]["reader"]["clock"].update(timeNamespace="time:99"), "local_clock_scope")
    mutate("remote arrival without proof", "tmux-fleet", lambda v: v["mesh"]["hosts"][1]["delivery"].update(proof=None), "remote_proof_required")
    mutate("proof digest changed", "agent-fleet", lambda v: v["mesh"]["hosts"][1]["delivery"]["proof"].update(payloadDigest="sha256:"+"f"*64), "proof_payload_binding")
    mutate("remote validity reset on delivery", "agent-fleet", lambda v: v["mesh"]["hosts"][1]["receipts"][0].update(expiresAtMs=999999), "remote_expiry_changed")
    mutate("unproved extra remaining lease", "tmux-fleet", lambda v: v["mesh"]["hosts"][1]["receipts"][0].update(remainingMs=20000), "remaining_lease_changed")
    mutate("late proof accepted", "agent-fleet", lambda v: v["mesh"]["hosts"][1]["delivery"]["proof"].update(sentAtMs=0,receivedAtMs=3000), "proof_future")
    mutate("catalog revision missing", "tmux-fleet", lambda v: v["mesh"]["catalog"].update(revision=None), "catalog_revision")
    mutate("successful facade hides sibling failure", "tmux-partial-host", lambda v: v["mesh"].update(status="complete"), "delivery_completeness")
    mutate("unsupported Mesh version", "agent-local", lambda v: v["mesh"].update(meshProtocol=2))
    mutate("unsupported owner version", "agent-local", lambda v: v["mesh"]["hosts"][0]["owner"].update(version=5), "owner_version")
    mutate("unsupported domain profile version", "tmux-local", lambda v: v.update(schemaVersion=2))
    mutate("base watch cannot dispatch action", "tmux-local", lambda v: v["mesh"].update(operation="kill"))
    mutate("wrong source component", "agent-local", lambda v: v["mesh"]["hosts"][0]["receipts"][0].update(sourceId="other"), "missing_source_receipt")
    mutate("omitted history receipt would bypass conservative expiry", "agent-local", lambda v: v["mesh"]["hosts"][0]["receipts"].pop(), "missing_source_receipt")
    mutate("expired source asserted current", "agent-local", lambda v: v["mesh"]["hosts"][0]["receipts"][0].update(expiresAtMs=1500), "receipt_expired")
    mutate("heartbeat cannot carry fresh positive expiry", "agent-local", lambda v: (v["mesh"].update(kind="heartbeat"),v["mesh"]["hosts"][0]["receipts"][0].update(expiresAtMs=999999)))
    mutate("gap cannot carry positive view", "tmux-local", lambda v: v["mesh"].update(kind="gap"))
    mutate("duplicate source receipt", "agent-local", lambda v: v["mesh"]["hosts"][0]["receipts"].append(copy.deepcopy(v["mesh"]["hosts"][0]["receipts"][0])), "duplicate_receipt")
    mutate("catalog capacity silently enlarged", "agent-local", lambda v: v["mesh"]["scope"].update(hostIds=["h"+str(i) for i in range(17)]))
    mutate("oversized common extensions", "tmux-local", lambda v: v["mesh"]["extensions"].update(large="x"*65536), "metadata_capacity")
    request=read(BASE/"examples/request-local.json")
    wrong=copy.deepcopy(request);wrong["selection"]["hostIds"]=["other"]
    rejects("local request with remote host list", lambda: validate_request(wrong))
    wrong=copy.deepcopy(bridge_reply);wrong["nonce"]="3"*32
    rejects("wrong bridge nonce", lambda: validate_bridge(wrong,bridge_request), "bridge_request_binding")
    wrong=copy.deepcopy(bridge_reply);wrong["remaining"][0]["remainingMs"]+=1000
    rejects("bridge renews lease from arrival", lambda: validate_bridge(wrong,bridge_request), "bridge_original_lease")
    guard=ProofOracle(bridge_request,1,1000)
    test("matching proof in current epoch",lambda: guard.accept(bridge_reply,1,1200))
    rejects("replayed correlated nonce",lambda: guard.accept(bridge_reply,1,1300),"proof_replay_or_epoch")
    guard=ProofOracle(bridge_request,2,1000)
    rejects("late previous connection epoch",lambda: guard.accept(bridge_reply,1,1200),"proof_replay_or_epoch")
    rejects("reply completed after absolute proof deadline",lambda: guard.accept(bridge_reply,2,3001),"proof_deadline")
    unavailable=copy.deepcopy(bridge_reply)
    unavailable.update(ownerFrame=None,ownerDigest=None,remaining=[],error={"code":"tool_missing","message":"Configured source is not installed"})
    test("reached bridge with unavailable owner",lambda: validate_bridge(unavailable,bridge_request))
    unavailable["error"]=None
    rejects("empty bridge reply without source error",lambda: validate_bridge(unavailable,bridge_request),"bridge_error_shape")
    first=copy.deepcopy(responses["tmux-local"]);first["mesh"]["operation"]="watch"
    stream=StreamOracle()
    test("initial full watch view",lambda: stream.accept(first))
    beat=control_for(first,"heartbeat",2,1,2001);beat["mesh"]["reader"].update(sequence=2,revision=1,encodedAtMs=2001)
    test("heartbeat changes delivery time only",lambda: stream.accept(beat))
    requires_resync=copy.deepcopy(first);requires_resync["mesh"]["reader"].update(sequence=4)
    rejects("skipped sequence without gap",lambda: stream.accept(requires_resync),"stream_order")
    previous_epoch=copy.deepcopy(first);previous_epoch["mesh"]["reader"].update(sequence=3,id="44444444-4444-4444-8444-444444444444")
    rejects("publisher replacement in old stream guard",lambda: stream.accept(previous_epoch),"stream_binding_changed")
    old_scope=copy.deepcopy(first);old_scope["mesh"]["reader"].update(sequence=3);old_scope["mesh"]["catalog"].update(state="ready",revision="sha256:"+"c"*64)
    rejects("catalog replacement in old stream guard",lambda: stream.accept(old_scope),"stream_binding_changed")
    gap=control_for(first,"gap",3,2,2002);gap["mesh"]["reader"].update(sequence=3,revision=2,encodedAtMs=2002)
    test("gap revokes positive view",lambda: stream.accept(gap))
    next_view=copy.deepcopy(first);next_view["mesh"]["reader"].update(sequence=4,revision=3,encodedAtMs=2003)
    rejects("view before scoped resync",lambda: stream.accept(next_view),"stream_resync_required")
    next_view["mesh"]["kind"]="resync"
    test("full resync restores supported view",lambda: stream.accept(next_view))
    terminal={"meshProtocol":1,"requestId":first["mesh"]["requestId"],"error":{"code":"scope_changed","message":"Catalog was replaced"}}
    test("catalog loss terminates watch guard",lambda: stream.accept(terminal))
    rejects("late view after terminated watch",lambda: stream.accept(next_view),"stream_closed")
    for domain in ["tmux","agent"]:
        sample=responses[domain+"-local"]
        rejects(domain+" suspended reader clock expires positives",lambda v=sample: require(bool(effective_current(v,400000,v["mesh"]["reader"]["clock"])),"expired_after_suspend"),"expired_after_suspend")
    # Independent expiry components do not permit stale metadata to look current.
    agent=copy.deepcopy(responses["agent-local"])
    claude=next(s for s in agent["mesh"]["hosts"][0]["owner"]["service"]["sources"] if s["provider"]=="claude")
    next(c for c in claude["components"] if c["name"]=="history")["expiresBoottimeMs"]=3000
    for receipt in agent["mesh"]["hosts"][0]["receipts"]:
        if receipt["sourceId"].startswith("claude:") and receipt["component"]=="history":
            receipt.update(expiresAtMs=3000,remainingMs=1000)
    test("earliest provider component expires only affected provider",lambda: require(all(r["identity"]["provider"]=="codex" for r in effective_current(agent,3001,agent["mesh"]["reader"]["clock"])) and bool(effective_current(agent,3001,agent["mesh"]["reader"]["clock"])),"provider_expiry_isolation"))
    agent["mesh"]["reader"]["encodedAtMs"] = 3001
    for receipt in agent["mesh"]["hosts"][0]["receipts"]:
        if receipt["sourceId"].startswith("claude:") and receipt["component"] == "history":
            receipt.update(health="stale", expiresAtMs=None, remainingMs=0)
    test("mesh expiry downgrade cannot bypass provider invalidation", lambda: require(
        bool(effective_current(agent, 3001, agent["mesh"]["reader"]["clock"])) and
        all(r["identity"]["provider"] == "codex" for r in effective_current(agent, 3001, agent["mesh"]["reader"]["clock"])),
        "provider_expiry_downgrade"))
    future_error=copy.deepcopy(responses["tmux-partial-host"])
    future_error["mesh"]["hosts"][1]["delivery"]["error"]["code"]="future_transport_condition"
    test("unfamiliar bounded diagnostic accepted",lambda: validate_response(future_error))
    remote_only=copy.deepcopy(responses["agent-fleet"])
    remote_only["mesh"]["hosts"]=remote_only["mesh"]["hosts"][1:]
    remote_only["mesh"]["scope"]["hostIds"]=["fixture-remote"]
    remote_only["sessions"]=[r for r in remote_only["sessions"] if r["identity"]["hostScope"]=="fixture-remote"]
    test("explicit remote selection need not include local owner",lambda: validate_response(remote_only))
    # Frozen published Host Mesh document/raw framing corpus.
    host_bundle=ROOT/"reference/rofi-ssh-plus/contracts/host-mesh-v1"
    for case in read(host_bundle/"fixtures/index.json")["cases"]:
        if case["kind"] == "document":
            test("Host Mesh published "+case["name"], lambda c=case: structural(wire((host_bundle/"fixtures"/c["fixture"]).read_bytes(),524288,line_framed=False),(host_bundle/c["schema"]).as_uri()))
        elif case["kind"] == "raw":
            rejects("Host Mesh published "+case["name"], lambda c=case: wire((host_bundle/"fixtures"/c["fixture"]).read_bytes(),524288,line_framed=False))
    test("strict Mesh wire", lambda: require(wire(canonical(responses["agent-local"])+b"\n") == responses["agent-local"], "wire_roundtrip"))
    rejects("escaped surrogate",lambda: wire(b'{"bad":"\\ud800"}\n'))
    rejects("multiline frame",lambda: wire(b'{\n"ok":true}\n'),"wire_multiple_lines")
    rejects("aggregate wire cap", lambda: wire(b'{}\n',limit=2), "wire_capacity")
    test("documentation links and whitespace",lambda: check_links(args.report.resolve() if args.report else None))
    pure=producer_validation() if args.check_sources else []
    if pure:
        CHECKS.append({"name":"existing pure producer semantic validators", "result":"passed", "details":pure})
    report={"status":"passed","checkedAtUtc":datetime.now(timezone.utc).isoformat(),
            "validationScope":"schemas, adversarial design model, frozen producer projection; no native/network/runtime acceptance",
            "sourceParityChecked":args.check_sources,"checksPassed":len(CHECKS),"checks":CHECKS,
            "limits":"Native passivity, SSH integration, GUI, resource, physical suspend and deployment remain later gates"}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="checks"},indent=2))


if __name__ == "__main__":
    main()
