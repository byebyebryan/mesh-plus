"""Validate delivery design schemas and adversarial lifecycle scenarios offline."""

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from delivery_model import (
    BASE,
    MAX_MESSAGE,
    ROOT,
    PendingQueue,
    RetainedEvents,
    Session,
    check_compact,
    compact_reply,
    encoded,
    endpoint,
    parse,
    require,
    sharing_key,
    validate,
)
from jsonschema.exceptions import ValidationError

CHECKS = []
EXAMPLES = {p.stem: json.loads(p.read_text()) for p in (BASE / "examples").glob("*.json")}


def check(name, operation):
    operation()
    CHECKS.append({"name": name, "result": "passed"})


def rejects(name, operation, code=None):
    try:
        operation()
    except (ValueError, ValidationError) as error:
        require(code is None or str(error) == code, "unexpected_rejection:" + str(error))
    else:
        raise AssertionError("accepted forbidden case: " + name)
    CHECKS.append({"name": name, "result": "passed", "expectation": "reject"})


def sample(name, **updates):
    return {**copy.deepcopy(EXAMPLES[name]), **updates}


def opened(product="state"):
    client = sample("client-hello" if product == "state" else "client-events-hello")
    server = sample("server-hello", product=product, profile=client["profile"])
    if product == "events":
        server["capabilities"] = ["subscribe", "replay", "status"]
    session = Session(client)
    session.receive(server)
    return session


def send(session, name, **updates):
    value = sample(name, channelId=session.channel, sequence=session.client_sequence + 1, **updates)
    session.send(value)
    return value


def receive(session, name, **updates):
    value = sample(name, channelId=session.channel, sequence=session.server_sequence + 1, **updates)
    return session.receive(value)


def subscribed(product="state", credit=None):
    session = opened(product)
    name = "client-subscribe" if product == "state" else "client-events-after"
    frame = send(session, name, **({"credit": credit} if credit is not None else {}))
    barrier = {"view": 1} if product == "state" else {"epoch": "publisher_1", "startSequence": 20, "lossFloor": 19, "highWater": 23}
    receive(session, "server-subscribed", start=frame["start"], barrier=barrier)
    return session


def source_frame():
    proof = EXAMPLES["compact-proof"]
    return {"hostId": proof["hostId"], "sourceId": proof["sourceId"], "ownerEpoch": proof["ownerEpoch"], "clock": proof["clock"], "sequence": 1, "encodedAt": 900,
            "receipts": [{k: v for k, v in r.items() if k != "remainingMs"} for r in proof["receipts"]], "snapshot": {"synthetic": True, "sessions": [{"identity": "fixture_session", "state": "unknown"}]}}


def schemas_and_parser():
    for name, value in EXAMPLES.items():
        schema = "endpoint" if name.startswith("endpoint-") else "digest-proof" if name == "compact-proof" else "client-frame" if name.startswith("client-") else "server-frame"
        check("schema example: " + name, lambda v=value, s=schema: validate(v, s))
        check("carrier-neutral roundtrip: " + name, lambda v=value, s=schema: require(parse(encoded(v), s) == parse(encoded(v) + b"\n", s, line=True) == v, "roundtrip"))
    raw = encoded(EXAMPLES["server-data"])
    rejects("duplicate JSON key", lambda: parse(raw[:-1] + b',"sequence":4}', "server-frame"), "duplicate_key")
    rejects("invalid UTF-8", lambda: parse(b'"\xff"', "server-frame"))
    rejects("BOM", lambda: parse(b"\xef\xbb\xbf" + raw, "server-frame"), "bom")
    rejects("multiple stream messages in one line", lambda: parse(raw + b"\n" + raw + b"\n", "server-frame", line=True), "line_framing")
    rejects("missing line terminator", lambda: parse(raw, "server-frame", line=True), "line_framing")
    rejects("escaped NUL", lambda: parse(raw.replace(b'"synthetic":true', b'"synthetic":"\\u0000"'), "server-frame"), "unicode")
    rejects("escaped surrogate", lambda: parse(raw.replace(b'"synthetic":true', b'"synthetic":"\\ud800"'), "server-frame"), "unicode")
    rejects("nonfinite JSON", lambda: parse(raw.replace(b'"synthetic":true', b'"synthetic":NaN'), "server-frame"), "nonfinite")
    rejects("message cap before decoding", lambda: parse(b" " * (MAX_MESSAGE + 1), "server-frame"), "message_capacity")
    rejects("unsupported delivery version", lambda: validate(sample("server-data", version=2), "server-frame"))
    rejects("unknown outer fields", lambda: validate(sample("server-data", arbitraryAction="kill"), "server-frame"))
    rejects("control reserve overflow", lambda: validate(sample("server-heartbeat", payload={"pad": "x" * 65536}), "server-frame"), "control_capacity")
    check("8 MiB payload fits explicit message maximum", lambda: validate(sample("server-data", payload={"pad": "x" * (8 * 1024 * 1024)}), "server-frame"))
    check("maximum Agent owner frame leaves separate Mesh wrapping room", lambda: validate(sample("server-data", payload={"pad": "x" * (8 * 1024 * 1024 + 16384 - 32)}), "server-frame"))


def lifecycle():
    client = sample("client-hello")
    for key, replacement in [("helloNonce", "2" * 32), ("hostId", "wrong-host"), ("sourceId", "other"), ("product", "events"), ("profile", "other.v1")]:
        rejects("hello binding: " + key, lambda k=key, r=replacement: Session(client).receive(sample("server-hello", **{k: r})), "hello_binding")
    rejects("route-authenticated host differs", lambda: Session(client, authenticated_host="other-host").receive(sample("server-hello")), "authenticated_host_binding")
    rejects("required capability absent", lambda: Session(client).receive(sample("server-hello", capabilities=["snapshot"])), "unsupported_capability")
    smaller = sample("client-hello"); smaller["limits"]["maxMessageBytes"] = 1024
    rejects("server cannot enlarge negotiated limits", lambda: Session(smaller).receive(sample("server-hello")), "limit_enlargement")
    session = opened()
    rejects("reply without request", lambda: receive(session, "server-result"), "unknown_handle")
    session = opened(); send(session, "client-request")
    check("poll terminal result", lambda: receive(session, "server-result"))
    rejects("duplicate terminal result", lambda: receive(session, "server-result"), "terminal_barrier")
    rejects("request ID cannot be reused", lambda: send(session, "client-request"), "handle_reuse")
    session = opened(); send(session, "client-subscribe")
    rejects("data before subscription barrier", lambda: receive(session, "server-data"), "subscription_barrier")
    session = subscribed(); send(session, "client-request")
    check("push while poll outstanding", lambda: receive(session, "server-data"))
    check("poll resolves amid push", lambda: receive(session, "server-result"))
    check("heartbeat amid same subscription", lambda: receive(session, "server-heartbeat"))
    rejects("heartbeat cannot carry source leases", lambda: receive(session, "server-heartbeat", streamSequence=3, payload={"remainingMs": 10000}), "heartbeat_evidence")
    session = subscribed()
    rejects("skipped stream sequence", lambda: receive(session, "server-data", streamSequence=2), "stream_order")
    session = subscribed()
    rejects("publisher incarnation changed silently", lambda: receive(session, "server-data", publisherEpoch="publisher_2"), "publisher_epoch")
    session = subscribed()
    rejects("late old channel frame", lambda: session.receive(sample("server-data", sequence=3, channelId="22222222-2222-4222-8222-222222222222")), "channel_binding")
    session = subscribed()
    rejects("skipped session frame", lambda: session.receive(sample("server-data", sequence=4)), "server_order")
    session = subscribed(); receive(session, "server-gap", streamSequence=1)
    rejects("state view after gap without resync", lambda: receive(session, "server-data", streamSequence=2), "resync_required")
    check("state full resync restores delivery", lambda: receive(session, "server-resync", streamSequence=2))
    session = subscribed(); second = send(session, "client-subscribe", subscriptionId="s2")
    receive(session, "server-subscribed", subscriptionId="s2", start=second["start"])
    send(session, "client-cancel")
    check("in-flight cancelled data is quarantined", lambda: require(receive(session, "server-data") == "quarantined", "cancel_quarantine"))
    receive(session, "server-ended")
    check("cancelled sibling does not close other push", lambda: receive(session, "server-data", subscriptionId="s2"))
    send(session, "client-request")
    check("cancelled sibling does not close request", lambda: receive(session, "server-result"))
    rejects("data after ended barrier", lambda: receive(session, "server-data", streamSequence=2), "terminal_barrier")
    session = subscribed(); send(session, "client-cancel")
    rejects("duplicate subscription acknowledgment during cancel", lambda: receive(session, "server-subscribed"), "subscription_barrier")
    session = opened(); send(session, "client-request"); session.expire(2000)
    check("timed-out reply quarantined in original ID", lambda: require(receive(session, "server-result") == "quarantined", "timeout_quarantine"))
    session = opened(); send(session, "client-request"); session.expire(2000)
    send(session, "client-request", requestId="r2")
    receive(session, "server-result")
    check("late r1 cannot fulfill r2", lambda: require(session.handles["r2"]["phase"] == "pending", "correlation"))
    session = opened()
    rejects("domain write cannot use read interface", lambda: send(session, "client-request", operation="kill"))
    session = opened()
    for i in range(8):
        send(session, "client-request", requestId="r" + str(i))
    rejects("outstanding request cap", lambda: send(session, "client-request", requestId="overflow"), "handle_capacity")
    session = opened(); session.handles = {"old" + str(i): {"type": "request", "phase": "done"} for i in range(4096)}
    rejects("completed handle tombstones require bounded channel rotation", lambda: send(session, "client-request"), "channel_handle_capacity")
    session = opened(); session.limits["maxMessageBytes"] = 1024
    send(session, "client-request")
    rejects("negotiated size enforced after handshake", lambda: receive(session, "server-result", payload={"pad": "x" * 1024}), "negotiated_capacity")


def credits():
    session = subscribed(credit={"frames": 1, "bytes": 2048})
    receive(session, "server-data")
    rejects("frame credit exhausted", lambda: receive(session, "server-data", streamSequence=2), "credit_exhausted")
    session = subscribed(credit={"frames": 1, "bytes": 2048}); receive(session, "server-data")
    send(session, "client-credit", credit={"frames": 1, "bytes": 2048})
    rejects("repeated cumulative credit gives no extra delivery", lambda: receive(session, "server-data", streamSequence=2), "credit_exhausted")
    send(session, "client-credit", credit={"frames": 2, "bytes": 4096})
    check("credit increase permits next frame", lambda: receive(session, "server-data", streamSequence=2))
    rejects("regressing credit", lambda: send(session, "client-credit", credit={"frames": 1, "bytes": 4096}), "credit_regression")
    session = subscribed(credit={"frames": 1, "bytes": 100})
    rejects("byte credit exhausted before frame credit", lambda: receive(session, "server-data"), "credit_exhausted")
    session = opened()
    rejects("oversized initial credit window", lambda: send(session, "client-subscribe", credit={"frames": 33, "bytes": 2048}), "credit_window")


def events():
    session = opened("events")
    rejects("state baseline cannot stand in for event start", lambda: send(session, "client-subscribe"), "start_product")
    session = opened()
    rejects("event after-cursor cannot stand in for state baseline", lambda: send(session, "client-events-after"), "start_product")
    session = opened("events")
    rejects("after mode requires a cursor", lambda: send(session, "client-events-after", start={"mode": "after", "cursor": None}), "cursor_start")
    for mode, start_sequence in [("live", 23), ("retained", 19)]:
        session = opened("events")
        frame = send(session, "client-events-after", start={"mode": mode, "cursor": None})
        check("event " + mode + " has an explicit producer barrier", lambda s=session, f=frame, n=start_sequence: receive(s, "server-subscribed", start=f["start"], barrier={"epoch": "publisher_1", "startSequence": n, "lossFloor": 19, "highWater": 23}))
    session = opened("events"); session.capabilities.remove("replay")
    rejects("no replay capability cannot silently fall back to live", lambda: send(session, "client-events-after"), "unsupported_replay")
    session = subscribed("events")
    for admission in [21, 22, 23, 24]:
        check("event replay then live admission " + str(admission), lambda a=admission: receive(session, "server-event", streamSequence=a-20, cursor={"epoch": "publisher_1", "sequence": a}, payload={"synthetic": True, "eventId": "receipt_" + str(a)}))
    check("hidden records still advance native progress", lambda: require(session.handles["s1"]["cursor"]["sequence"] == 24, "filtered_progress"))
    rejects("checkpoint cannot skip undelivered admissions", lambda: receive(session, "server-heartbeat", streamSequence=5, control="checkpoint", payload={"cursor": {"epoch": "publisher_1", "sequence": 30}}), "checkpoint_skips_admission")
    session = subscribed("events")
    rejects("out-of-order native admission", lambda: receive(session, "server-event", cursor={"epoch": "publisher_1", "sequence": 22}), "event_admission_order")
    session = subscribed("events"); receive(session, "server-gap", streamSequence=1)
    rejects("state resync cannot repair missed events", lambda: receive(session, "server-resync", streamSequence=2), "event_gap_terminal")
    check("event gap terminates with cursor barrier", lambda: receive(session, "server-ended", reason="gap", cursor={"epoch": "publisher_1", "sequence": 20}))
    ring = RetainedEvents()
    for _ in range(5):
        ring.publish()
    check("retained suffix after valid cursor", lambda: require([r["sequence"] for r in ring.after({"epoch": "publisher_1", "sequence": 2})] == [3, 4, 5], "retained_suffix"))
    rejects("expired cursor is typed loss", lambda: ring.after({"epoch": "publisher_1", "sequence": 1}), "retention_gap")
    rejects("cursor from prior publisher epoch", lambda: ring.after({"epoch": "publisher_0", "sequence": 3}), "publisher_restart")
    ring.expire_all()
    rejects("empty retained ring preserves loss floor", lambda: ring.after({"epoch": "publisher_1", "sequence": 4}), "retention_gap")


def proofs_and_sharing():
    owner = source_frame(); current = copy.deepcopy(owner); current.update(sequence=2, encodedAt=1100)
    nonce = "1" * 32
    proof = compact_reply(owner, current, nonce, 1200)
    check("compact proof for identical semantic version", lambda: require(check_compact(proof, owner, nonce, 1000, 1300) == [9700], "compact_expiry"))
    check("same compact proof expiry as full RTT translation", lambda: require(1300 + max(0, 8800 - 300 - 100) == check_compact(proof, owner, nonce, 1000, 1300)[0], "full_parity"))
    rejects("retained bridge cannot prove lost publisher", lambda: compact_reply(owner, current, nonce, 1200, owner_available=False), "owner_unavailable")
    for field, replacement in [("ownerEpoch", "publisher_2"), ("hostId", "other-host"), ("clock", {**owner["clock"], "timeNamespace": "time:2"}), ("snapshot", {"synthetic": True, "sessions": []})]:
        changed = {**current, field: replacement}
        rejects("source version changed: " + field, lambda v=changed: compact_reply(owner, v, nonce, 1200), "full_replacement_required")
    changed = copy.deepcopy(current); changed["receipts"][0]["accepted"] += 1
    rejects("new native receipt requires full replacement", lambda: compact_reply(owner, changed, nonce, 1200), "full_replacement_required")
    rejects("wrong nonce", lambda: check_compact(proof, owner, "2" * 32, 1000, 1300), "proof_binding")
    wrong = {**proof, "ownerDigest": "sha256:" + "f" * 64}
    rejects("digest not in validated cache", lambda: check_compact(wrong, owner, nonce, 1000, 1300), "proof_binding")
    wrong = copy.deepcopy(proof); wrong["receipts"][0]["remainingMs"] = 10000
    rejects("lease cannot restart on delivery", lambda: check_compact(wrong, owner, nonce, 1000, 1300), "lease_from_arrival")
    wrong = copy.deepcopy(proof); wrong["receipts"] = []
    rejects("missing original component", lambda: check_compact(wrong, owner, nonce, 1000, 1300), "receipt_set")
    rejects("proof RTT deadline", lambda: check_compact(proof, owner, nonce, 1000, 3001), "proof_deadline")
    expired = compact_reply(owner, current, nonce, 11000)
    check("compact proof preserves expired original lease", lambda: require(check_compact(expired, owner, nonce, 1000, 1300) == [1300], "expired_lease"))
    descriptor = sample("endpoint-ssh-stdio-state")
    check("same source selector shares state upstream", lambda: require(sharing_key(descriptor, {}) == sharing_key(copy.deepcopy(descriptor), {}), "shared_key"))
    for field, replacement in [("authRef", "other_user"), ("revision", "sha256:" + "f" * 64), ("sourceId", "other"), ("profile", "other.v1")]:
        check("distinct sharing scope: " + field, lambda k=field, r=replacement: require(sharing_key(descriptor, {}) != sharing_key({**descriptor, k: r}, {}), "sharing_scope"))
    event_descriptor = sample("endpoint-ssh-stdio-events")
    check("different event cursors need independent replay interest", lambda: require(sharing_key(event_descriptor, {}, {"mode": "after", "sequence": 20}) != sharing_key(event_descriptor, {}, {"mode": "after", "sequence": 21}), "event_replay_interest"))
    for name in [n for n in EXAMPLES if n.startswith("endpoint-")]:
        check("endpoint binding: " + name, lambda n=name: endpoint(EXAMPLES[n]))
    rejects("IPC cannot name remote host", lambda: endpoint(sample("endpoint-ipc-state", hostId="remote-host")), "ipc_scope")
    rejects("WSS cannot embed credentials", lambda: endpoint(sample("endpoint-wss-state", address={"url": "wss://user:secret@fixture.example/mesh"})), "wss_address")
    rejects("WSS cannot silently downgrade to WS", lambda: endpoint(sample("endpoint-wss-state", address={"url": "ws://fixture.example/mesh"})))


def queue_scenarios():
    queue = PendingQueue("state", max_bytes=1024)
    queue.enqueue({"view": 1})
    started = queue.begin()
    queue.enqueue({"view": 2})
    queue.enqueue({"view": 3})
    check("started state frame stays immutable while later views coalesce", lambda: require(started["record"] == {"view": 1} and list(queue.pending) == [{"view": 3}], "started_frame_preserved"))
    queue.finish()
    next_frame = queue.begin()
    check("coalesced state carries gap then full resync", lambda: require(next_frame == {"gapBefore": True, "kind": "resync", "record": {"view": 3}}, "coalesced_resync"))
    slow = PendingQueue("events", max_records=2, max_bytes=1024)
    fast = PendingQueue("events", max_records=2, max_bytes=1024)
    for i in [1, 2]:
        record = {"eventId": "receipt_" + str(i)}
        slow.enqueue(record); fast.enqueue(record); fast.begin(); fast.finish()
    rejects("slow event reader reports overflow instead of replacing records", lambda: slow.enqueue({"eventId": "receipt_3"}), "event_queue_gap")
    fast.enqueue({"eventId": "receipt_3"})
    check("slow event reader leaves healthy sibling deliverable", lambda: require(fast.begin()["record"] == {"eventId": "receipt_3"}, "reader_isolation"))
    rejects("event queue cannot continue silently after loss", lambda: slow.enqueue({"eventId": "receipt_4"}), "queue_closed")
    byte_limited = PendingQueue("events", max_records=64, max_bytes=64)
    byte_limited.enqueue({"pad": "x" * 30})
    rejects("event byte cap independent of record cap", lambda: byte_limited.enqueue({"pad": "x" * 30}), "event_queue_gap")
    oversized = PendingQueue("state", max_bytes=64)
    rejects("state payload admission rejects oversize explicitly", lambda: oversized.enqueue({"pad": "x" * 64}), "queue_record_capacity")
    started_budget = PendingQueue("state", max_bytes=64)
    started_budget.enqueue({"pad": "x" * 30}); started_budget.begin()
    rejects("state queue admits started and pending bytes together", lambda: started_budget.enqueue({"pad": "x" * 30}), "queue_byte_capacity")
    check("failed state admission never leaves an oversized queue", lambda: require(started_budget.size() <= 64 and not started_budget.pending, "queue_bounded_after_rejection"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    schemas_and_parser()
    lifecycle()
    credits()
    events()
    proofs_and_sharing()
    queue_scenarios()
    report = {"status": "passed", "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "checksPassed": len(CHECKS), "schemas": len(list(BASE.glob("*.schema.json"))), "examples": len(EXAMPLES),
              "validationScope": "offline schemas, synthetic lifecycle/cursor/credit/proof/sharing oracles; no producer event wire or deployed runtime acceptance", "checks": CHECKS}
    if args.report:
        path = args.report if args.report.is_absolute() else ROOT / args.report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))


if __name__ == "__main__":
    main()
