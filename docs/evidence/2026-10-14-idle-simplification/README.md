# Idle simplification execution

2026-10-14. In progress; this report certifies only the checkpoints stated below.
No deployment or released artifact replacement is part of this pass.

## S0: acquisition history race

The unchanged grouped-refresh success fixture was reproduced intermittently on
Python 3.13.7. The [bounded causal trace](refresh-race.json) identifies a cached
snapshot captured with `accepted=1` that completes after a watch publication with
`accepted=2`. CachedPublisher previously compared both against one shared receipt
history, rejected the valid earlier snapshot as `source_receipt_regression`, and
returned `source_unavailable`. The downstream control's stale-scope revocation
is correct after this artificial outage; its binding check is not the defect.
The failure requires neither a native gap nor a publisher/reader replacement.
The original hosted failure remains preserved in the prior idle-profile evidence.

Separate each watch's receipt history from the serialized snapshot/proof history.
Read serialization includes acquisition, not just completion, so two overlapping
queries cannot create the same false regression within their own history. Each
watch still rejects regressions and lease renewal in its ordered acquisition
stream. All operations retain source clock checks, independent validation and
original receipt times. Queued acquisition is covered by the caller's existing
absolute deadline. History is bounded by existing active-operation limits and is
retired with its watch; no replay or retained generations are introduced.

The same flaw existed in the reference ObserverAdapter and is corrected there.
Failed reference admission now also leaves history/sequence unchanged. Wrapper
sequence remains publisher-wide and advances only on successful admission;
independent source observations are not globally completion-ordered samples.
No schemas, normative text or public SDK signatures change.

Two deterministic tests fail on the pre-fix `a7f63dd` archive with the exact
`source_receipt_regression` cause: older snapshot after newer watch, and older
watch after newer proof. Additional coverage retains within-watch lease/counter
rejection and serial read ordering with cancellation. Existing integration cases
cover genuine gap, delivery rotation, publisher replacement and control settlement
requiring Mesh-confirmed post-request acquisition. Final gates are recorded below
when complete. Early local fixture error using a zero positive counter is excluded;
it was corrected to use valid counters 2 and 1 before acceptance.

S0 source acceptance: Mesh lock/read/delivery, full native runtime (186 tests,
zero skips) and lint pass on Python 3.13.7 with Tmux source a8 and the reviewed
Agent a16 wheel. Tmux's optional Mesh gate passes all 42 tests with zero skips.
The native-WSS wrapper deliberately rejects Tmux a8 because its independent
historical native tuple requires a5; this is recorded as an input-gate rejection,
not WSS runtime failure. Standalone WSS and the exact historical native-WSS tuple
are checked separately. A first full run against current Agent a3 is excluded:
its Service 4 facade does not validate the legacy Service 2 fixtures.
