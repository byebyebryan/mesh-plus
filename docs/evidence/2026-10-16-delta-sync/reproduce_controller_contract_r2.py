"""R2 toy range/receipt arithmetic; no producer, socket, ledger or authority."""

import argparse
import hashlib
import json
import runpy
from pathlib import Path

R1 = Path(__file__).with_name("reproduce_controller_contract_r1.py")
assert hashlib.sha256(R1.read_bytes()).hexdigest() == (
    "e27da225fe24f90cce41c4991e874c4dcc3f6174da494c0238eaa615e4f9e5e9"
)
BASE = runpy.run_path(str(R1))
REQUEST = BASE["REQUEST"]
UINT = 2**64 - 1


def check(condition, code):
    if not condition:
        raise ValueError(code)


def integer(value, maximum=UINT):
    check(type(value) is int and 0 <= value <= maximum, "integer")


class Stamp:
    """Toy metadata record, not a secure mint or real buffer/frame handle."""

    def __init__(self, owner, start, stop, floor):
        self.owner, self.start, self.stop, self.floor = owner, start, stop, floor
        self.closed = False

    def close(self):
        self.closed = True


class Ingress:
    """Counts/ranges only: this allocates no byte buffer and performs no I/O."""

    def __init__(self, *, capacity=65536, max_ranges=256):
        self.capacity, self.max_ranges = capacity, max_ranges
        self.ranges, self.offset, self.last_sample, self.held = [], 0, 0, 0
        self.identity = object()

    def admitted(self, count, floor, *, start=None):
        check(floor is not None, "provenance")
        integer(floor)
        integer(count, 4096)
        check(floor >= self.last_sample, "clock")
        check(start is None or start == self.offset, "offset")
        check(self.offset + count <= UINT, "offset")
        check(self.held + count <= self.capacity, "capacity")
        self.last_sample = floor
        if count:
            if len(self.ranges) == self.max_ranges:
                left, right = self.ranges[:2]
                self.ranges[:2] = [[left[0], right[1], min(left[2], right[2])]]
            self.ranges.append([self.offset, self.offset + count, floor])
            self.offset += count
            self.held += count

    def stamp(self, start, stop):
        integer(start)
        integer(stop)
        check(start < stop <= self.offset, "offset")
        for lo, hi, floor in self.ranges:
            if lo <= start < hi:
                return Stamp(self.identity, start, stop, floor)
        raise ValueError("provenance")

    def deadline(self, stamp, remaining, now, *, capsule=UINT):
        check(type(stamp) is Stamp and stamp.owner is self.identity, "provenance")
        check(not stamp.closed, "retired")
        integer(remaining, 15000)
        check(remaining > 0, "integer")
        deadline = min(capsule, stamp.floor + remaining)
        check(now < deadline, "deadline")
        return deadline


class Receipt:
    """Toy single-use metadata/outcome; no actual scheduling or drain/pins."""

    def __init__(self, operation, command, deadline, *, acquisition=1, channel="a" * 32):
        self.operation, self.command, self.deadline = operation, command, deadline
        self.acquisition, self.channel, self.request = acquisition, channel, REQUEST
        self.outcome, self.used, self.through = None, False, None

    def latch(self, phase, status, code):
        check(self.outcome is None, "latched")
        allowed = {
            "work": (self.operation in {"begin", "baseline", "changes", "head", "watch"}, "ok", "none"),
            "stop": (self.operation == "stop-watch", "ok", "none"),
            "end": (self.operation == "end", "ok", "none"),
            "cancelled": (self.operation in {"baseline", "changes", "head"}, "cancelled", "none"),
            "cancel": (self.operation == "cancel", "ok", "none"),
            "busy": (True, "failed", "busy"),
            "failure": (code in {"deadline", "source", "capacity", "output"}, "failed", code),
        }
        check(phase in allowed and allowed[phase] == (True, status, code), "outcome")
        self.outcome = phase, status, code

    def emit(self, now, *, channel_live=True, work_live=False, settled=True,
             through=0, kind="command-result", request=REQUEST, channel="a" * 32):
        check(kind == "command-result", "kind")
        check(request == self.request and channel == self.channel, "binding")
        check(not self.used and self.outcome is not None, "receipt")
        check(channel_live, "channel")
        check(now < self.deadline, "deadline")
        phase, status, code = self.outcome
        check(phase == "busy" or settled, "cleanup")
        check(phase not in {"work", "stop"} or work_live, "work")
        integer(through)
        self.through, self.used = through, True
        return {"protocol": "mesh.state-sync/1", "kind": kind, "request": self.request,
                "command": self.command, "operation": self.operation,
                "status": status, "code": code, "through": self.through}


def outcome(operation, phase, status, code, *, command=2, deadline=3000):
    receipt = Receipt(operation, command, deadline)
    receipt.latch(phase, status, code)
    return receipt


def vectors():
    checks = []

    def positive(name, action):
        checks.append({"name": name, "outcome": "accept", "value": action()})

    def reject(name, code, action):
        try:
            action()
        except ValueError as error:
            check(str(error) == code, f"{name}:expected-{code}:got-{error}")
        else:
            raise AssertionError(name)
        checks.append({"name": name, "outcome": "reject", "code": code})

    ingress = Ingress()
    ingress.admitted(100, 1000)
    first, tail = ingress.stamp(0, 50), ingress.stamp(50, 100)
    positive("coalesced-second-frame-keeps-first-read-floor",
             lambda: {"first": first.floor, "tail": tail.floor,
                      "deadline": ingress.deadline(tail, 2000, 2999)})
    reject("dequeue-at3500-does-not-mint5500", "deadline",
           lambda: ingress.deadline(tail, 2000, 3500))
    reject("at-ingress-deadline", "deadline", lambda: ingress.deadline(tail, 2000, 3000))
    ingress.admitted(100, 2500)
    fragmented = ingress.stamp(90, 150)
    positive("fragmented-first-byte-not-completion-time",
             lambda: ingress.deadline(fragmented, 2000, 2900))
    reject("fragmented-tail-not-renewed", "deadline",
           lambda: ingress.deadline(fragmented, 2000, 3500))
    positive("new-frame-after-resume-uses-new-admission-range",
             lambda: ingress.deadline(ingress.stamp(150, 200), 2000, 3500))
    positive("capsule-bound-still-smaller", lambda: ingress.deadline(tail, 2000, 2200, capsule=2300))
    reject("no-provenance-cannot-use-now", "provenance", lambda: ingress.admitted(10, None))
    reject("range-offset-gap", "offset", lambda: ingress.admitted(10, 2600, start=201))
    reject("range-offset-overlap", "offset", lambda: ingress.admitted(10, 2600, start=199))
    reject("clock-regression", "clock", lambda: ingress.admitted(10, 2400))
    reject("oversized-single-read", "integer", lambda: ingress.admitted(4097, 2600))
    reject("foreign-carrier-stamp", "provenance", lambda: Ingress().deadline(first, 2000, 2000))
    reject("raw-timestamp-is-not-stamp", "provenance", lambda: ingress.deadline(1000, 2000, 2000))
    tail.close()
    reject("closed-frame-stamp", "retired", lambda: ingress.deadline(tail, 2000, 2000))
    merged = Ingress(max_ranges=2)
    merged.admitted(10, 1000)
    before = merged.stamp(0, 5)
    merged.admitted(10, 2000)
    merged.admitted(10, 3000)
    positive("range-pressure-merges-only-earlier",
             lambda: {"ranges": merged.ranges, "oldMintedFloor": before.floor,
                      "laterExtractedFloor": merged.stamp(10, 15).floor})
    reject("merged-floor-never-forward", "deadline",
           lambda: merged.deadline(merged.stamp(10, 15), 2000, 3500))
    small = Ingress(capacity=4)
    small.admitted(4, 1000)
    reject("capacity-before-next-count", "capacity", lambda: small.admitted(1, 1100))
    positive("capacity-refusal-leaves-range-state", lambda: {"held": small.held, "ranges": small.ranges})
    eof = Ingress()
    eof.admitted(0, 1000)
    positive("zero-transfer-has-no-range", lambda: eof.ranges)

    positive("cancelled-head-receipt-survives-work-retirement",
             lambda: outcome("head", "cancelled", "cancelled", "none").emit(2500, through=4))
    positive("cancel-ack-survives-capsule-retirement",
             lambda: outcome("cancel", "cancel", "ok", "none", deadline=16000).emit(4000, through=4))
    positive("end-ack-survives-capsule-retirement",
             lambda: outcome("end", "end", "ok", "none").emit(2500))
    positive("stop-watch-still-needs-live-capsule",
             lambda: outcome("stop-watch", "stop", "ok", "none").emit(2500, work_live=True))
    positive("busy-denial-does-not-need-retired-work",
             lambda: outcome("head", "busy", "failed", "busy").emit(2500, settled=False))
    positive("failed-source-after-scoped-cleanup",
             lambda: outcome("changes", "failure", "failed", "source").emit(2500))
    positive("ordinary-work-success-before-revocation",
             lambda: outcome("changes", "work", "ok", "none").emit(2500, work_live=True, through=9))
    reject("ordinary-success-after-revocation", "work",
           lambda: outcome("head", "work", "ok", "none").emit(2500))
    reject("stop-watch-with-retired-capsule", "work",
           lambda: outcome("stop-watch", "stop", "ok", "none").emit(2500))
    reject("cancel-before-physical-cleanup", "cleanup",
           lambda: outcome("cancel", "cancel", "ok", "none").emit(2500, settled=False))
    reject("end-before-physical-cleanup", "cleanup",
           lambda: outcome("end", "end", "ok", "none").emit(2500, settled=False))
    reject("receipt-after-channel-retirement", "channel",
           lambda: outcome("end", "end", "ok", "none").emit(2500, channel_live=False))
    for name, receipt in [
        ("end", outcome("end", "end", "ok", "none")),
        ("cancelled-original-head", outcome("head", "cancelled", "cancelled", "none")),
        ("busy", outcome("head", "busy", "failed", "busy")),
        ("failure", outcome("head", "failure", "failed", "deadline")),
    ]:
        reject(f"{name}-at-original-deadline", "deadline", lambda receipt=receipt: receipt.emit(3000))
    reject("cancel-original-expired-even-if-cancel-ack-live", "deadline",
           lambda: outcome("head", "cancelled", "cancelled", "none").emit(4000))
    reject("cleanup-permit-cannot-forward-proof", "kind",
           lambda: outcome("cancel", "cancel", "ok", "none").emit(2500, kind="proof"))
    reject("cleanup-permit-cannot-forward-material", "kind",
           lambda: outcome("end", "end", "ok", "none").emit(2500, kind="material"))
    reject("wrong-request-receipt", "binding",
           lambda: outcome("end", "end", "ok", "none").emit(2500, request="0" * 64))
    reject("old-channel-receipt", "binding",
           lambda: outcome("end", "end", "ok", "none").emit(2500, channel="b" * 32))
    reject("failure-cannot-be-relabelled-success", "outcome",
           lambda: outcome("head", "failure", "ok", "none"))
    latched = outcome("head", "failure", "failed", "source")
    reject("failed-target-cannot-be-relabelled-cancelled", "latched",
           lambda: latched.latch("cancelled", "cancelled", "none"))
    single = outcome("end", "end", "ok", "none")
    positive("through-latched-after-prior-native-deliveries", lambda: single.emit(2500, through=7))
    reject("no-second-receipt-or-through-refresh", "receipt", lambda: single.emit(2501, through=8))
    reject("bool-through-is-not-watermark", "integer",
           lambda: outcome("end", "end", "ok", "none").emit(2500, through=True))
    reject("unlatched-outcome-cannot-send", "receipt", lambda: Receipt("end", 2, 3000).emit(2500))

    old = BASE["vectors"]()
    return {"classification": "toy metadata/state/arithmetic only; no runtime/resources/actual transport",
            "r1SourceSha256": hashlib.sha256(R1.read_bytes()).hexdigest(),
            "r1Positives": old["positives"], "r1Rejects": old["rejects"],
            "r2Positives": sum(x["outcome"] == "accept" for x in checks),
            "r2Rejects": sum(x["outcome"] == "reject" for x in checks), "checks": checks,
            "exclusions": "No byte buffers/native data/mint security/strict R2 bootstrap-result parser/event-loop concurrency/physical cleanup/clock or credit proof."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = vectors()
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"R1 {report['r1Positives']} positive/{report['r1Rejects']} reject; "
          f"R2 {report['r2Positives']} positive/{report['r2Rejects']} reject")
