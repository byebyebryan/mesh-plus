# Validation/copy hypothesis review

2026-10-12. Scope: installed Mesh a15, Tmux a7 and Agent a20 pure profiles;
source acquisition and collection remain unchanged. Four publisher and four
reader profile reports use original private origin-host frames. Instrumentation
is diagnostic only; cumulative timings overlap.

## Ranked costs and boundaries

Agent publisher proof plus Bridge admission makes five full native validations:
one at copied-frame inspection, two at publisher envelope admission and two at
the Bridge's result boundary. Tmux makes three because its bridge callback
checks binding while native inspection validates the frame. Agent's recursive
native shape validation dominates this diagnostic at 94/391 rows. Generic JSON
tree/encoding, reconstruction and copying recur in both profiles.

Reader replay includes the direct Client domain callback, Reader host admission,
composition, guard admission and current-row calculation. For twelve operations,
Agent records 72 native validations and 48 generic inspections; Tmux records 48
native inspections. Snapshot acquisition, publisher preparation, network and
collector costs are excluded. The captured evidence may already be expired:
replay preserves original receipts and does not manufacture positive currentness.
An initial replay incorrectly supplied a snapshot to a watch-only guard; that
failed diagnostic produced no acceptance report. Corrected replay uses watch
composition and independent one-frame guards.

These are not all interchangeable checks over an immutable admitted object.
Client callbacks are public standalone entry points. Publisher/Bridge/consumer
boundaries receive mutable dictionaries. Composition reconstructs native frames
from aggregated rows. Reusing an identity or earlier acceptance across these
boundaries could miss mutations, rebinding, altered receipt scope or expiry.

## Current P3 disposition: no runtime candidate selected

Do not weaken `AgentCodec.validate_bridge`: direct clients rely on its full
native validation. Do not skip `inspect_state`, use a raw-object identity cache,
or remove generic schema/proof/receipt/clock checks. No public API, schema,
collector or publisher runtime change is made at this checkpoint.

A separate optional scope-only callback, followed by compulsory full native
inspection, could remove duplicate native validation inside generic admission
while retaining the existing direct callback. That is an explicit owner opt-in
and SDK maintenance proposal, not a private optimization automatically applicable
to arbitrary codecs with extra bridge rules. Before adoption it needs review of
standalone callback compatibility, custom codec fallback, post-callback mutation,
generic proof/receipt/clock checks and differential invalid cases. This pass
first measures the unchanged carriers; it will not add an API merely to fill
the candidate cells. If no safe measured candidate emerges, the accepted plan
explicitly permits a no-change conclusion and omitted candidate comparisons.

## Measurement review

`studies/performance/measure.py` and `coordinator.py` use accepted owner profiles
and both static lazy factories. The private SSH launcher retains the fixed
`mesh-plus bridge --source SOURCE --stdio` suffix and genuine reached nonce;
an operator-owned PATH and case marker isolate process accounting. No executable
or module is selected through the wire. Ordinary source configuration is read
without writes. WSS uses the same owner factories through isolated listeners.

The primary scope is one remote cached endpoint watch with unchanged 3/10-second
proof cadence, full consumer guard and current-row calculation. This isolates
carrier cost; it is not the previous complete fleet budget scope. Native owner
and collector CPU are reported separately. Two dedicated sampler processes use
500 ms snapshots with PID/birth checks and own CPU counters; sampled child CPU
is never added again through parent reaped-child counters. Root SSH-session PSS
is unavailable, explicitly null, so summed accessible PSS is a lower bound.
Sampler SSH/control costs are excluded from the attributable trial total and
must remain a measurement limitation, not zero-cost infrastructure.

Short pilots qualify harness plumbing only. Failed pilots remain privately
retained: canonical Mesh IDs differ from kernel/Tailscale HostName on Snap;
the route guard now uses the reviewed tailnet IP binding. A subsequent syntax
error in that guard was caught before measurements and corrected. Final pilots
pass both directions. These attempts prove no performance gain. Clean windows
must preserve controls/incarnations/route and inventory identities; excluded
windows remain visible. Even stable row identities do not freeze ordinary native
activity, payload content or external host load, so their results remain
descriptive unless matched workload comparability is independently established.

Before primary acceptance, the retained capacity-warmed WSS listeners were
identified as incompatible with fresh-publisher window ordering. The initial
run was stopped before a complete pair; it certifies no gain. All four first
trial listeners retired through verified PID/birth SIGTERM and their foreground
handles exited successfully. The coordinator now owns a fresh listener per WSS
window and verifies its exact private ready-receipt command and birth before
retirement. This keeps allocator/process history comparable to fresh SSH
publishers. Standing-listener cold acquisition receipts retain their separate
scope and cannot be substituted for normal watch cost.
