# Owned admission and selected prepared reads

These optional local APIs were introduced in a22 and are retained by the
published a25 prerelease under SDK 1. Admission interface
1, selection interface 1 and preparation interface 1 are independent descriptors;
their introduction preserved lock-4 schema bytes; subsequent additive profile
locks have independent provenance. There is no new transport
capability, owner policy, default selection or deployment.

## Owned Reader handoff

`Reader.watch_admitted(...)` takes the same keyword arguments as `watch(...)`.
`execute_admitted(request)` validates the same Read request as `execute(request)`;
snapshot requests still return ordinary JSON. Full watch replacements are
`AdmittedResponse`; terminal errors remain ordinary dictionaries. Reader still
performs complete aggregate/schema/native/proof admission before producing a token.
`compose_admitted(...)` is the corresponding synchronous composition entrypoint.

`PreparedReadGuard.accept(token)` checks the exact admitting profile instance,
descriptor and captured callback binding, then performs the ordinary per-request
order, request, scope, catalog, reader incarnation, epoch and resync checks. It
reuses the already checked native projection. It does not repeat aggregate or
native validation. Changed profile bindings fail closed. Construct a new stream
and guard after installing a changed profile/preparation implementation.

The token owns serialized immutable JSON bytes, including the receipt projection;
it never caches an exposed mutable dictionary or treats a revision/digest as
current proof. It is process-local, not a serializable wire authority or sandbox
against installed code using private internals. `snapshot()` returns a detached
raw aggregate; `context()` returns a detached header with `sessions=[]`. These are
exports, not current-state queries. Prepared read-time expiry remains mandatory.

Ordinary `watch`, `execute`, `compose`, `validate_response`, `current_sessions`,
`ReadGuard` and raw `PreparedReadGuard.accept(dict)` retain their validation and
mutable-export semantics. A raw exported token must pass those strict entrypoints
again. Transports retain disconnect/EOF/liveness ownership; a token does not
detect loss of an external connection.

## Row-free context

`PreparedReadGuard.context()` returns the current generation header with
`sessions=[]`, or `None` before baseline and after gap, terminal or disconnect.
It decodes no row bodies. Like `snapshot()`, it reports admitted evidence;
receipt expiry must be assessed using the current reader clock. Heartbeats
retain the original generation and never extend its leases.

## Whole-roster selection and summaries

```python
from mesh_plus.api import SelectionRule

def classify(row):
    # Domain and product policy belongs to Observer/the consumer.
    selected = consumer_eligible(row)
    summary = None if selected else {
        "identity": dict(row["identity"]),
        "reason": consumer_exclusion(row),
    }
    return SelectionRule(selected, summary)

selection = guard.select(classify)
selected_rows, summaries = selection.current(now_ms, reader_clock)
context = guard.context()
```

`classify` receives every deeply immutable native record, including historical
and ineligible records, once per admitted generation on its first selected read.
Its decision must be static for that generation. The returned `SelectionRule`
requires an actual boolean and optional plain JSON dictionary. Summary meaning
and any product cap belong to the caller. Classify the complete roster before
applying a display cap; Mesh applies none.

Both returned lists contain only rows with the original eligible, positive,
unexpired dependencies. Each summary shares exactly its original row's expiry;
an independently expired host/provider cannot survive in the summary list.
Unselected current records beyond the selected display limit remain available
as summaries for positive exclusion bookkeeping. Native bodies are decoded on
each read only for selected rows; summaries are decoded from their smaller
privately owned bytes. All returned data is detached mutable JSON. Full
`snapshot()` retains all rows regardless of selection. Replacement recompiles;
heartbeat does not; gap/disconnect revokes both lists. Classifier exceptions,
bad shapes, changed clock, reentrancy and retirement during classification close
the guard. Retained summary bytes are bounded separately to sixteen MiB per
explicit selection. Callers serialize synchronous methods and own the number
and lifetime of selection objects.

## Combined owner codec admission

A bound codec may explicitly implement `admit_bridge(payload) -> NativeState`.
That optional interface performs full owner/native validation and returns its
checked projection in one operation. Mesh still independently validates bridge
schema, fixed host/source/profile, native capacity/shape/roundtrip, digest,
clock, chronology and proof receipt arithmetic. Existing codecs without this
method retain `validate_bridge(payload)` followed by `inspect_native(frame)`.
The returned state is borrowed for that synchronous operation, never cached as
mutable authority. Standalone `inspect_native` and `validate_bridge` remain
strict. Client's ordinary validation boundary remains independent.

## Acquisition boundary

This pass preserves snapshot/proof requests, source cadence, transport bytes,
nonce correlation and timeouts. Frozen Read rules require a changed subscription
candidate to acquire a fresh correlated full reply. Local watch-body reuse and a
notification-only wire format are deferred pending explicit contract review.
No historical acceptance is attributed to these changed candidate bytes.
