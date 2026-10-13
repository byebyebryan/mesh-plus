# Opt-in prepared consumer interface 1

Reviewed implementation plan authorized on 2026-10-13 following the
[proposal](prepared-consumer-proposal.md) and explicit discussion of additive
API compatibility. This is a local Python extension through SDK 1, not a new
wire profile, transport capability, selected artifact or owner certification.
The frozen lock and packaged schemas remain byte-identical.

## Consumer

Import from `mesh_plus.api`:

```python
guard = PreparedReadGuard(
    "tmux", request_id, profile=profile, preparation=owner_preparation,
    host_ids=expected_hosts,
)
try:
    async for frame in reader.execute(request):
        guard.accept(frame)
        rows = guard.current(receiver_boottime_ms, receiver_clock)
finally:
    guard.disconnect()
```

The guard admits replacement **watch** frames using the same full response and
stream checks as ReadGuard. It is not a new snapshot-request parser. Polling
consumers retain `validate_response`/`current_sessions`; supporting a separately
owned prepared snapshot lifetime would be another additive API decision.

`accept(frame)` returns the input frame for compatibility with the legacy call
pattern. It copies the input, fully admits once, compiles rules from that admitted
native value, and publishes a sealed generation only after all checks pass.
No caller-supplied "already validated" flag exists. Any exception, including
`CancelledError`, clears positives and closes the prepared guard before it is
re-raised. A compilation failure cannot retain a preceding positive generation
or fall back. The existing ReadGuard's transactional error behavior is unchanged.

`current(now_ms, clock)` returns new dictionaries. It checks the exact admitted
reader clock, integer BOOTTIME not preceding original encoded time, and the
original minimum expiry across every required, originally positive native and
projected receipt. An eligible owner rule never overrides delivery or freshness.
Clock failure raises `ProtocolError` and permanently retires this guard. An
expired row is absent; queries and heartbeats cannot extend its lease.

`snapshot()` returns a fresh ordinary raw response, or `None` before baseline,
during a gap or after retirement. This is an export of admitted evidence, not
current authority; use `current` for current rows. Heartbeats retain the original
snapshot and lease timestamps. A gap clears it until a valid resync. Base error,
disconnect, and failed admission revoke it. Healthy siblings follow their own
admitted lease and delivery outcomes in replacement state.

Methods are synchronous and caller-serialized. There is no background task,
await boundary or transport ownership added here. The transport adapter still
must disconnect on EOF, liveness or framing failure and construct a new guard
on reconnect. Caller cancellation after accept must be covered by its `finally`.
No hard real-time cross-thread or instantaneous external revocation is promised.

## Owner preparation

`PREPARATION_INTERFACE_VERSION` is 1. Supply an explicit `StatePreparation`
with a frozen `PreparationDescriptor(interface_version, profile,
implementation_id)` and `prepare_rules(state)`. The profile descriptor must
exactly match the selected supported StateProfile, including native version and
schema digest. `implementation_id` is a nonempty string of at most 256 characters
identifying reviewed owner compiler/package semantics. It is a caller-selected
provenance label, **not** package attestation performed by Mesh.

Construction rejects missing/mismatched/unsupported interfaces before any I/O.
The guard binds the descriptor and callable and compares them before use and
after compilation. An observed change retires it with `preparation_binding`.
These comparisons cannot detect changes inside closures, globals or live code;
owners must explicitly retire guards before those semantics or installed bytes
change. No profile is automatically opted in, including ReferenceProfile.

`PreparationState` contains owner, records, clock, publisher, emitted_ms and
receipts from the fully admitted `NativeState`. Its JSON maps are recursively
read-only mappings, arrays are tuples, and records/receipts are tuples. All
nested values are copied into that immutable representation. It is a borrowed
compile input; owners should not retain it across generations. Mesh keeps
provider acquisition, domain policy, desktop actions and networking out of this
compiler boundary.

Return an exact tuple with one `PreparedRule(identity, required, eligible)` per
admitted record, preserving identity and order. Identity is the same tuple of
exact strings/integers supplied by StateProfile. `eligible` is an exact bool;
requirements are `None` or a frozenset of exact two-string receipt-key tuples.
Foreign receipt keys, invented/reordered identities, count mismatches and wrong
types fail closed. Known stale/unknown/unsupported receipts, missing requirements,
empty requirements, or false eligibility grant no positives. Mesh serializes
the original admitted rows; the compiler cannot supply replacement payloads.

Owners explicitly promise deterministic, nonmutating and lossless compilation
from these complete facts alone. No wall time, environment, callback mutable
state, provider access, I/O or actions may affect rules. Rules remain valid for
the entire generation; semantic changes need a new publication or retirement
and re-admission. This differs deliberately from legacy callbacks, which can
reject on subsequent reads. Owner golden, partial/missing, future timing and
version-invalidation certification is independent of ordinary profile adoption.
The test-only compiler used for Tmux qualification is not an owner facade release.

## Storage and errors

One immutable generation stores a serialized header and each original row once,
plus one optional derived expiry per row. It does not retain the admitted native
DTO, raw mutable view, requirement sets or duplicate full snapshot. Retained body
bytes are at most 16 MiB; transactional replacement can temporarily retain two
generations, at most 32 MiB of serialized bodies. Admission's original aggregate,
metadata and native limits remain mandatory. Native/copy/frozen/compiler inputs,
Python object overhead, decoded exports and caller-retained exports are additional
transient allocations; these byte ceilings are **not** a process RSS limit or a
global fleet memory pool. Peak and steady allocation evidence must be reported
separately. A trusted compiler can allocate memory; Mesh does not sandbox it.

Schema/native exceptions retain their existing exception types. Mesh preparation
checks raise `ProtocolError` with `preparation_descriptor`, `preparation_interface`,
`preparation_binding`, `preparation_rule_count`, `preparation_rule_identity`,
`preparation_receipt_keys`, `preparation_receipt_scope`, `prepared_capacity` or
`prepared_retired` or `prepared_reentrant`. Owner compiler exceptions are re-raised after retirement.
Do not translate an error into an unchecked success or reconnect the same guard.

Existing consumers need no migration. Opt in only after owner certification and
measured benefit for the actual read/publication ratio, including accept/setup,
allocation, exports and teardown. Publication and operational selection remain
later explicit gates with rollback to ReadGuard.
