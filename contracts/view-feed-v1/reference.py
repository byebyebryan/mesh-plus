"""Independent stdlib packet reconstruction oracle; no Mesh/runtime imports."""

import copy
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def key(parts):
    require(type(parts) is list and 0 < len(parts) <= 16 and
            all(type(p) in (str, int) for p in parts), "identity")
    return tuple(parts)


def reconstruct(previous, packet, *, identity=None, restore=None):
    """Default toy native uses full id/birth; tests may supply independent splits."""
    identity = (lambda r: [r["id"], r["birth"]]) if identity is None else identity
    restore = (lambda owner, rows: {"meta": owner, "rows": rows}) if restore is None else restore
    p = copy.deepcopy(packet)
    require(set(p) == {"protocol", "kind", "streamId", "binding", "base", "target", "owner",
                       "envelope", "records", "upserts", "removals", "order", "reason"}, "fields")
    require(p["protocol"] == "mesh-plus.view-change-feed.v1", "protocol")
    target = p["target"]
    require(type(target["revision"]) is int and 1 <= target["revision"] <= 2**53-1, "revision")
    require(p["envelope"]["ownerDigest"] == target["digest"] and
            p["envelope"]["kind"] == "candidate" and p["envelope"]["nonce"] is None and
            p["envelope"]["error"] is None, "envelope")
    if p["kind"] == "replacement":
        require(p["base"] is None and p["upserts"] == [] and p["removals"] == [], "replacement")
        require(type(p["records"]) is list and p["order"] is not None, "replacement")
        rows = p["records"]
        old_order = []
        require(len({key(list(identity(r))) for r in rows}) == len(rows), "duplicates")
        table = {key(list(identity(r))): r for r in rows}
    else:
        require(p["kind"] == "delta" and previous is not None, "baseline")
        require(p["binding"] == previous["binding"] and p["streamId"] == previous["streamId"], "binding")
        require(p["base"] == previous["target"] and
                target["revision"] == p["base"]["revision"] + 1 and p["records"] is None, "base")
        table = {key(list(identity(r))): r for r in previous["rows"]}
        old_order = list(table)
        removes = [key(v) for v in p["removals"]]
        puts = [key(v["key"]) for v in p["upserts"]]
        require(len(removes) == len(set(removes)) and len(puts) == len(set(puts)) and
                not set(removes) & set(puts), "operations")
        for item in p["upserts"]:
            r = item["record"]
            require(key(item["key"]) == key(list(identity(r))), "record_key")
        for k in removes:
            require(k in table, "missing_removal")
            del table[k]
        for item, k in zip(p["upserts"], puts):
            table[k] = item["record"]
    order = old_order if p["order"] is None else [key(v) for v in p["order"]]
    require(len(order) == len(set(order)) and set(order) == set(table), "order")
    rows = [table[k] for k in order]
    native = restore(p["owner"], rows)
    require(digest(native) == target["digest"], "digest")
    return {"binding": p["binding"], "streamId": p["streamId"], "target": target,
            "rows": rows, "native": native}


def run(path=None):
    path = Path(path) if path else Path(__file__).with_name("vectors.json")
    fixture = json.loads(path.read_text())
    previous = None
    positives = []
    states = {}
    for case in fixture["positive"]:
        previous = reconstruct(previous, case["packet"])
        require(previous["native"] == case["expected"], case["name"])
        states[case["name"]] = copy.deepcopy(previous)
        positives.append(case["name"])
    negatives = []
    for case in fixture["negative"]:
        packet = copy.deepcopy(case["packet"])
        state = states.get(case["base"])
        saved = copy.deepcopy(state)
        try:
            reconstruct(state, packet)
        except (ValueError, KeyError, TypeError):
            negatives.append(case["name"])
        else:
            raise AssertionError("accepted " + case["name"])
        require(state == saved, "rollback")
    return {"positive": positives, "negative": negatives,
            "fixtureSha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
