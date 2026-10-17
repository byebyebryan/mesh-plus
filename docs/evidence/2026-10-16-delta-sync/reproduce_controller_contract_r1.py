"""Toy controller shapes/state/deadlines only; imports neither producer/runtime."""

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

PROTOCOL = "mesh.state-sync/1"
UINT = 2**64 - 1
FIELDS = {
    "begin": "remainingMs",
    "baseline": "acquisition",
    "changes": "acquisition base target maxTransactions maxBytes",
    "head": "acquisition challenge remainingMs",
    "watch": "acquisition cursor",
    "stop-watch": "acquisition watch",
    "end": "acquisition",
    "cancel": "acquisition command",
}
BINDING = {
    "readerEpoch": "a" * 32, "requestId": "toy-read", "catalogRevision": "toy",
    "hosts": ["fixture"], "route": "toy-only", "channelEpoch": "b" * 32,
    "bridgeId": "c" * 32, "role": "transport-relay", "encodingDigest": "d" * 64,
}


def check(value, code):
    if not value:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


REQUEST = hashlib.sha256(canonical(BINDING)).hexdigest()
TAG = ["e" * 64, 2, "f" * 64]
CURSOR = ["toy-owner", 2, "f" * 64]
CHALLENGE = {"nonce": "0" * 64, "request": REQUEST, "target": "1" * 64}


def integer(value, minimum=1, maximum=UINT):
    check(type(value) is int and minimum <= value <= maximum, "integer")


def digest(value):
    check(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "digest")


def shape(value, depth=0, nodes=None):
    nodes = [0] if nodes is None else nodes
    nodes[0] += 1
    check(depth <= 8 and nodes[0] <= 512, "tree")
    if type(value) is dict:
        check(len(value) <= 32, "tree")
        for key, child in value.items():
            check(type(key) is str, "tree")
            shape(key, depth + 1, nodes)
            shape(child, depth + 1, nodes)
    elif type(value) is list:
        check(len(value) <= 32, "tree")
        for child in value:
            shape(child, depth + 1, nodes)
    elif type(value) is str:
        check(len(value) <= 4096 and not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "tree")
    else:
        check(type(value) in (int, bool, type(None)), "tree")


def parse(raw):
    check(type(raw) is bytes and len(raw) <= 8192, "capacity")
    check(raw.endswith(b"\n") and b"\n" not in raw[:-1] and b"\r" not in raw and
          not raw.startswith(b"\xef\xbb\xbf"), "framing")

    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "duplicate")
            result[key] = value
        return result

    def number(text):
        check(text != "-0", "number")
        return int(text)

    def invalid(_):
        raise ValueError("number")

    value = json.loads(raw[:-1].decode(), object_pairs_hook=pairs, parse_int=number,
                       parse_float=invalid, parse_constant=invalid)
    # This reference decodes before shape checks: deliberately NOT an intake
    # allocator, streaming preflight or hostile-input memory qualification.
    shape(value)
    return value


def tag(value):
    check(type(value) is list and len(value) == 3, "tag")
    digest(value[0])
    integer(value[1], 0)
    digest(value[2])


def command(sequence, operation, **fields):
    return {"protocol": PROTOCOL, "kind": "command", "request": REQUEST,
            "sequence": sequence, "operation": operation, **fields}


def validate(value):
    check(type(value) is dict and type(value.get("operation")) is str and
          value["operation"] in FIELDS, "variant")
    operation = value["operation"]
    check(set(value) == set("protocol kind request sequence operation".split()) |
          set(FIELDS[operation].split()), "variant")
    check(value["protocol"] == PROTOCOL and value["kind"] == "command", "variant")
    check(value["request"] == REQUEST, "request")
    integer(value["sequence"])
    for name in ("acquisition", "watch", "command"):
        if name in value:
            integer(value[name])
    if operation in ("begin", "head"):
        integer(value["remainingMs"], 1, 2000 if operation == "head" else 15000)
    if operation == "changes":
        tag(value["base"])
        tag(value["target"])
        integer(value["maxTransactions"], 1, 4)
        integer(value["maxBytes"], 1, 8388608)
    if operation == "head":
        challenge = value["challenge"]
        check(type(challenge) is dict and set(challenge) == {"nonce", "target", "request"}, "challenge")
        for child in challenge.values():
            digest(child)
        check(challenge["request"] == REQUEST, "request")
    if operation == "watch":
        cursor = value["cursor"]
        check(type(cursor) is list and len(cursor) == 3 and type(cursor[0]) is str and
              0 < len(cursor[0]) <= 256, "cursor")
        integer(cursor[1], 0)
        digest(cursor[2])


class Model:
    """Synchronous toy state; no tasks, physical storage, I/O or authority."""

    def __init__(self):
        self.next = 1
        self.capsule = self.deadline = self.watch = self.active = None

    def send(self, value, *, first=1000, now=1001):
        validate(parse(canonical(value) + b"\n"))
        check(value["sequence"] == self.next, "sequence")
        self.next += 1  # A typed busy request still consumes its command sequence.
        operation = value["operation"]
        if operation != "begin":
            check(value["acquisition"] == self.capsule and self.capsule is not None, "capsule")
            check(now < self.deadline, "deadline")
        if operation == "cancel":
            check(self.active is not None and value["command"] == self.active, "active")
            self.active = self.capsule = self.deadline = None
        else:
            check(self.active is None, "busy")
            if operation == "begin":
                check(self.capsule is None, "busy")
                deadline = first + value["remainingMs"]
                check(now < deadline, "deadline")
                self.capsule, self.deadline = value["sequence"], deadline
            elif operation in ("baseline", "changes", "head"):
                check(operation == "head" or self.watch is None, "busy")
                if operation == "head":
                    check(now < min(self.deadline, first + value["remainingMs"], first + 2000), "deadline")
                self.active = value["sequence"]
            elif operation == "watch":
                check(self.watch is None, "busy")
                self.watch = value["sequence"]
            elif operation == "stop-watch":
                check(value["watch"] == self.watch and self.watch is not None, "watch")
                self.watch = None
            elif operation == "end":
                self.capsule = self.deadline = None
        return {"next": self.next, "capsule": self.capsule, "deadline": self.deadline,
                "watch": self.watch, "active": self.active}


def vectors():
    passed = []

    def positive(name, action):
        passed.append({"name": name, "outcome": "accept", "value": action()})

    def reject(name, code, action):
        try:
            action()
        except ValueError as error:
            check(str(error) == code, f"{name}:expected-{code}:got-{error}")
        else:
            raise AssertionError(name)
        passed.append({"name": name, "outcome": "reject", "code": code})

    begin = command(1, "begin", remainingMs=15000)
    positive("request-digest", lambda: REQUEST)
    positive("begin-first-byte-anchored", lambda: Model().send(begin, first=1000, now=1100))
    for op, fields in {
        "baseline": {}, "changes": {"base": TAG, "target": TAG, "maxTransactions": 4, "maxBytes": 8388608},
        "head": {"challenge": CHALLENGE, "remainingMs": 2000}, "watch": {"cursor": CURSOR}, "end": {},
    }.items():
        def action(op=op, fields=fields):
            model = Model()
            model.send(begin)
            return model.send(command(2, op, acquisition=1, **fields))
        positive(f"variant-{op}", action)

    model = Model()
    model.send(begin)
    model.send(command(2, "watch", acquisition=1, cursor=CURSOR))
    positive("head-beside-watch", lambda: model.send(command(3, "head", acquisition=1,
                                                           challenge=CHALLENGE, remainingMs=2000)))
    positive("cancel-keeps-watch", lambda: model.send(command(4, "cancel", acquisition=1, command=3)))
    positive("new-read-after-cancel", lambda: model.send(command(5, "begin", remainingMs=15000),
                                                       first=30000, now=30001))
    positive("stop-watch-in-new-read", lambda: model.send(command(6, "stop-watch", acquisition=5, watch=2),
                                                         first=30001, now=30002))
    positive("proof-cap-less-than-two-seconds", lambda: min(16000, 15000 + 2000, 15000 + 500))
    positive("synchronous-overrun-prewrite-rejects", lambda: {"deadline": 3000, "now": 3101,
                                                            "mayWrite": 3101 < 3000})
    positive("watch-outlives-ended-capsule", lambda: _ended_watch(begin))
    for name, raw, code in [
        ("duplicate", b'{"kind":1,"kind":2}\n', "duplicate"),
        ("negative-zero", b'{"n":-0}\n', "number"),
        ("float", b'{"n":1.0}\n', "number"),
        ("nonfinite", b'{"n":NaN}\n', "number"),
        ("bom", b'\xef\xbb\xbf{}\n', "framing"),
        ("cr", b'{}\r\n', "framing"),
        ("no-lf", b'{}', "framing"),
        ("two-lf", b'{}\n\n', "framing"),
        ("over-bound", b" " * 8192 + b"\n", "capacity"),
        ("surrogate", b'{"n":"\\ud800"}\n', "tree"),
    ]:
        reject(name, code, lambda raw=raw: parse(raw))
    for name, updates, code in [
        ("bool-sequence", {"sequence": True}, "integer"),
        ("zero-sequence", {"sequence": 0}, "integer"),
        ("overflow-sequence", {"sequence": UINT + 1}, "integer"),
        ("gap-sequence", {"sequence": 2}, "sequence"),
        ("wrong-request", {"request": "0" * 64}, "request"),
        ("unknown-field", {"extra": 1}, "variant"),
        ("unknown-operation", {"operation": "fallback"}, "variant"),
        ("null-duration", {"remainingMs": None}, "integer"),
        ("bool-duration", {"remainingMs": True}, "integer"),
        ("zero-duration", {"remainingMs": 0}, "integer"),
        ("renew-duration", {"remainingMs": 15001}, "integer"),
    ]:
        reject(name, code, lambda updates=updates: Model().send({**begin, **updates}))
    reject("at-acquisition-deadline", "deadline", lambda: Model().send(begin, first=1000, now=16000))
    reject("past-acquisition-deadline", "deadline", lambda: Model().send(begin, first=1000, now=16001))
    for name, updates, code in [
        ("old-capsule", {"acquisition": 3}, "capsule"),
        ("bool-capsule", {"acquisition": True}, "integer"),
        ("head-extended", {"remainingMs": 2001}, "integer"),
        ("head-null-challenge", {"challenge": None}, "challenge"),
        ("head-request-substitution", {"challenge": {**CHALLENGE, "request": "0" * 64}}, "request"),
    ]:
        def action(updates=updates):
            state = Model()
            state.send(begin)
            state.send({**command(2, "head", acquisition=1, challenge=CHALLENGE, remainingMs=2000), **updates})
        reject(name, code, action)
    for delta in (2000, 2101):
        def action(delta=delta):
            state = Model()
            state.send(begin)
            state.send(command(2, "head", acquisition=1, challenge=CHALLENGE, remainingMs=2000),
                       first=1000, now=1000 + delta)
        reject(f"head-prewrite-{delta}", "deadline", action)
    for name, field, value in [("fifth-transaction", "maxTransactions", 5),
                               ("extra-material-byte", "maxBytes", 8388609)]:
        value = command(2, "changes", acquisition=1, base=TAG, target=TAG,
                        maxTransactions=4, maxBytes=8388608) | {field: value}
        reject(name, "integer", lambda value=value: validate(value))
    old = Model()
    old.send(begin)
    reject("duplicate-command", "sequence", lambda: old.send(begin))
    malformed = copy.deepcopy(command(2, "changes", acquisition=1, base=TAG, target=TAG,
                                      maxTransactions=4, maxBytes=8388608))
    malformed["base"][1] = True
    reject("bool-native-generation", "integer", lambda: validate(malformed))
    return {"classification": "toy shapes/state/deadlines only; no runtime/imports/I/O/resources/authority",
            "binding": BINDING, "requestDigest": REQUEST, "checks": passed,
            "positives": sum(x["outcome"] == "accept" for x in passed),
            "rejects": sum(x["outcome"] == "reject" for x in passed)}


def _ended_watch(begin):
    model = Model()
    model.send(begin)
    model.send(command(2, "watch", acquisition=1, cursor=CURSOR))
    model.send(command(3, "end", acquisition=1))
    return {"watch": model.watch, "capsule": model.capsule, "atMs": 30000}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = vectors()
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"{report['positives']} positive / {report['rejects']} reject toy checks")
