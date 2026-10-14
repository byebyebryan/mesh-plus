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

## S1/S2 scheduling prototype (value gate pending)

A 30-second two-session-per-host counter run records 2,755 Fleet loop turns,
2,166 ready callbacks and 1,059 timer registrations. The prototype records 1,359
turns, 1,308 ready callbacks and 373 timers with the same 15 accepted samples per
host. Remote bridge turns decrease from 1,252 to 931. These count runs include
setup/cleanup and instrumentation, so their CPU figures are not savings evidence.
The initial baseline counter run used the preceding diagnostic script; both script
hashes are retained in raw records. Timing comparisons use one fixed harness.

The prototype has one owned BOOTTIME recheck timer per active event loop. Each
operation wakes on its own IO completion or expiry, not a broadcast tick. The
last waiter removes the timer/loop attachment. Reader proof boundaries retain
the pending subscription read; final retirement cancels it. Existing 100 ms
suspend recheck responsiveness and absolute budgets remain. Focused tests cover
BOOTTIME-only advance, earlier registration, simultaneous/late completion, ordinary
proof-boundary ownership, cancellation and repeated cancellation during cleanup.
Mesh native runtime passes 191 tests before the final repeated-cancellation case;
Tmux Mesh integration passes 42 tests. Final complete gates follow qualification.
This commit is a source prototype, not a promoted artifact or measured win.

## Qualification and package boundary

Empty headless two-host Fleet is the primary current rare-session workload.
Before long-run results, declare two ABBA blocks of 300 seconds per run with
fixed S0 (`7f5e26c`) versus S2 (`ef4d4cc`) source archives and Tmux `31e3625`.
Two-session fleets receive a separate 120-second ABBA screen; desktop-on, larger
roster and active updates have distinct compatibility/resource checks. Initial
short-screen cases overlap source tests or the projection study; record that
interference and do not promote their short timings into final acceptance.
Long timing fixtures run serially and contain no counters/profiler. Other desktop
activity and host frequency/load remain uncontrolled and are explicit limits.

Allocate a new private Mesh a19 candidate for changed runtime bytes. Its version
banner and distribution metadata agree. This allocation is not a release or live
selection; performance promotion remains conditional on the predeclared gate.
Tmux's matching private a9 package accepts a19 explicitly. Existing a18/a8 wheels,
managed a15/a7 services and Agent/RLCD independent selections are unchanged.

## Private wheel acceptance (performance gate still running)

Mesh a19 source freeze `6e2e7e8` builds from a clean Git archive into a new private
artifact directory. [Wheel manifest](wheel-manifest.json) binds SHA256
`b3a1d00c06abcba4548a6f9894f51931dde517b80bc905d5d991e498834546ec`;
all 63 runtime/schema/data members match source. The measured S2 archive matches
62 members exactly; only the deliberate version banner differs. Build generator
and source epoch are recorded; no existing artifact was overwritten.

The isolated wheel first passes canonical standalone checks with no Observer
packages: 154 core tests and 34 optional WSS tests, zero skips. The external
[installed conformance caller](standalone-conformance.json) passes 35 cases with
actual owned SSH and confirms both Observer packages absent. Then install the
independent Tmux a9 / legacy Agent a16 packages into that disposable environment:
full Mesh native acceptance passes 192 tests, zero skips; installed Tmux acceptance
passes 42 tests, zero skips. Compressed logs bind each stated checkpoint.
Python 3.11.10 standalone core/WSS passes 154+34 with zero skips; Python 3.14.8
installed deadline/publisher-focused acceptance passes 15 tests. Tmux's own source
gate passes 404 tests and lint with unchanged collection/runtime policy.

Historical native WSS acceptance is separate: its wrapper requires exactly Tmux a5
and Agent a16. That explicit tuple passes 43 cases on Python 3.13.7. Its report
predates the a19 version banner, binds the same runtime bytes except that banner,
and does not certify Tmux a9 as the wrapper's historical native input. A rejected
a8/a9 wrapper tuple is an input-gate rejection, not a skipped runtime test.

Installed Python 3.14 fixtures observe controlled native updates under four cached
readers and a 12-session/desktop/one-reader case, with bounded cleanup and unchanged
native identities/attachment counts. These are short compatibility/resource
checks, not matched CPU savings or physical suspend/GUI acceptance.

## Long empty-fleet result (secondary gates pending)

Both predeclared ABBA blocks complete all eight 300-second windows. The
[raw long runs](empty-long-runs.json) and [block summary](empty-long-summary.json)
record Fleet means of 2.2133 -> 1.8233 and 2.4500 -> 1.9617 CPU percent of one
core: savings of 0.3900 and 0.4883 percentage points, or 17.6% and 19.9%.
Every window accepts exactly 149 samples per host with unchanged native facts
and complete cleanup. Each block's saving exceeds its baseline range; block 1's
baseline range is 0.3267 points, block 2's is 0.0200. The initial 20% target is
not strictly reached across both blocks; the repeated smaller saving is reported
without rounding it into a target pass. Other-host activity/frequency remain
uncontrolled, and these are observed block spreads rather than confidence bounds.

Performance acceptance remains conditional on the predeclared secondary small-
roster/active-update matrix and separate acquisition/traffic counters. No CPU
saving is claimed for installed/live services, SSH daemon helpers or tmux servers.
[Host inputs](host-start.json) and [runtime members](runtime-members.json) bind
explicit power-state and runtime/dependency snapshots; final parity is checked
after the study. Memory sampling is separate process RSS/PSS plus kernel peak RSS,
not cgroup or peak-PSS accounting.

## Expiry-registration refinement after a19 qualification

A deterministic review test exposes an a19 edge case: after one expiry future is
completed but before its waiting coroutine retires, registration still includes
that expired entry when choosing the earliest deadline. A new 10 ms waiter can
therefore inherit the existing 100 ms timer. Completed IO is still checked against
BOOTTIME and cannot grant late validity, but short-deadline notification can be
postponed. The regression test fails on a19 by approximately 80 ms.

Ignore completed expiry futures when choosing the earliest live registration.
The 100 ms suspend recheck, per-operation absolute deadline and ownership remain.
All seven deadline cases pass after this one-expression fix. Preserve the a19
wheel and long measurements as their own prototype checkpoint. Allocate a new
Mesh a20 / Tmux a10 private pair; do not overwrite a19/a9. Qualification now adds
a bounded final empty/active ABBA screen on corrected installed bytes, plus new
traffic and installed gates. Old a19 measurements are not attributed to a20.
