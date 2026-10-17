# Relay head deadline and failed-intake cleanup

This source correction addresses the coordinator's bounded relay review at
`ea25fcb`/`0b942c25`. It does not reopen A1, completion transfer or compact R2,
and is independent of the already closed m74 material-lifetime fix.

`head_after_nonce` captures the earlier of the original acquisition deadline and
call start plus two seconds. The same absolute bound covers challenge handling,
the source await, scanner/header materialization, output-lock waits and every
physical write/drain. The source return no longer starts a fresh two-second
window. A synchronous scanner can run past the deadline, but its result rejects
before further header copying or output. Exactly at the deadline also rejects.

Expiration before any fragment is written retires that acquisition without
closing an independent watch. A blocked watch retains its input/output credit,
buffer and configured transport limits. Once any write has been attempted,
failure closes the affected channel and keeps physical pins charged through
bounded cleanup, including repeated caller cancellation. No further fragment
is started after the deadline check fails.

The current completed-batch consumer already rejects excessive counts, mixed
types and non-tuples before transfer. New tests pin those existing guarantees:
the invalid wrapper's close method is never invoked as transferred ownership,
the owning source session cleans its own refs, and a sibling physical pin stays
charged and usable. A further case exposed a remaining gap when the source
raised after allocating an internal result but before returning it. That failure
now starts affected-channel cleanup even when no batch reached Mesh. The public
operation waits for the initiated scoped cleanup after its worker unwinds;
shared owners, sibling channels and the native provider are untouched.

The six new regression methods run unchanged against the exact prior runtime
`171f21c` with only their test file overlaid. Each Python version reports seven
expected failing checks: four source/scanner expiry cases, two queued-lock cases
and source failure before result delivery. Explicit malformed returned batches,
partial-write charged unwind and a blocked independent watch already pass there.
After the correction all 33 focused relay tests pass on Python 3.14.8 and
3.11.17, with cyclic GC disabled, retained errors and five final counters zero.

The coordinator's unmodified probe is also retained. On the prior current
runtime it observes one write at 2101 ms and zero complete proof frames. Its old
malformed-chain fixture now throws inside the newer fixture source before
returning a completed batch; this is not attributed as a returned-tuple failure.
The added explicit batch cases establish that boundary separately. Probe prose
is unchanged; the saved numeric fields determine its before/after observation.

The exact `docs/evidence/2026-10-16-delta-sync/relay-deadline-review.json`
record pins runtime, overlaid tests, commands, raw outputs and protected contracts.
These are synthetic source/scanner/transport ownership checks, not native
producer, Reader authority, aggregate capacity, RSS or performance acceptance.
Actual source completion and pin-tracking integration, controller request grammar,
packed 2,000-row delivery, dense/cold/recovery gates, populated IPC/fixed SSH and
an immutable installed pair remain open. No package, schema, encoding, route,
selected a7/a23, sibling, provider, service or rollout changes.
