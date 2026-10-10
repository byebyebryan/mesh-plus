# Mesh a8 reliability and measurements candidate

2026-10-10. This is an unreleased source/wheel candidate, not an operational
selection. Mesh a7 remains selected for shared authority/Tmux; Agent retains its
independent reader and resident bridge. No sibling source, managed selection or
operational provider state was changed by this pass.

The [updated plan](../../reliability-and-measurement.md) records the implementation
boundary and remaining adoption/optimization gates. The candidate rotates owned
Reader watches before the 4,096-handle lifetime cap and adds local cumulative
transport measurements. Frozen lock/schema and a7 authority bytes remain intact.

## Source and artifact validation

The source gate passed 103 runtime tests without skips, 116 Read oracles and 169
Delivery oracles, the lock check and Ruff. A later focused Reader pass covers the
final partial-measurement flag. Source validation's editable environment had
stale distribution metadata; its reported installed versions are not the source
versions. Exact runtime bytes are bound separately by the matrix reports.

The candidate wheel was built from a fresh copy of tracked inputs plus the
explicit new implementation files, excluding ignored build/cache outputs. Its
36 runtime/schema entries match source bytes exactly. Python 3.11 standalone
wheel acceptance passes 72 tests without either Observer installed, no skips.
Isolated Python 3.13 full wheel acceptance passes 104 runtime tests without
skips, Read/Delivery/lock checks and Ruff, using Tmux Observer 0.6.0a2 and Agent
Observer 0.5.0a15 wheels. Agent Mesh CLI and Tmux projection checks each pass
seven tests with that installed candidate. These verify pure integration
boundaries, not Tmux worker adoption or Agent collector acceptance.

[Gate inputs](gates.json) bind the wheel hash, producer wheel hashes, source base,
runtime digests and exact validation scopes. [Standalone acceptance](wheel-core.json)
records native dependencies absent and actual installed a8 metadata.
[Full runtime acceptance](wheel-native.json) binds the installed a8 and producer
tuple to runtime and test digests. The wheel
is retained locally for review and has not been released or deployed.

Regression scope includes 4,079 actual requests plus a live subscription at the
production admission boundary, concurrent admission races, preserved existing
work/credit/cancel, repeated both-domain IPC rotations, owned SSH rotations and
child reaping, paused-consumer revocation, and cancellation crossing retirement.
Native CLI tests preserve stdout and verify final stderr metrics on snapshot
and Ctrl-C watch. Original receipts, conservative nonce proofs and sibling-host
independence remain enforced by the full runtime suite.

## Owned measurement matrix

[IPC](reader-ipc.json) and [SSH](reader-ssh.json) each cover eight fresh-process
cases: Tmux/Agent, one/four readers, idle/one-second pushed replacements, a
one-second proof interval and five seconds of steady observation. Byte totals
include setup/cleanup. All measured connections retire with no cleanup failures,
no uninstrumented adapters and no active channels remaining.

These are short descriptive native-profile fixture measurements. They do not
rank production optimizations. The reports include current runtime/harness
digests, per-reader counters, worker CPU and a sampled owned descendant tree.
No ordinary fleet, large native inventory, prolonged soak, GUI, physical suspend,
producer collection, consumer rollout or operational rollback is certified.
Background development/validation may compete for resources; CPU/RSS figures
are observations, not thresholds or matched performance guarantees.

The one-reader idle SSH case carries six full proofs plus one pushed baseline:
Tmux result bytes are 13,344 versus 2,161 pushed bytes; Agent result bytes are
56,100 versus 8,710 pushed bytes. Four-reader SSH cases sample eighteen owned
processes versus six for one reader, including the disposable daemon/worker.
This exposes both repeated proof carriage and channel multiplication, without
establishing which dominates the ordinary fleet.

## Adoption and next gate

Tmux's a2 worker permits Mesh through a7; a8 adoption needs an explicit reviewed
pin/version update and paired artifact validation. Agent's own reader/bridge
selection likewise remains independent. No released artifact is overwritten or
promoted here. Wrapper clients must forward rotation/inspection methods to
participate in proactive ownership and complete local measurements.

Next, capture identical ordinary multi-reader and large-payload workloads, full
process-tree costs, outage/recovery and sustained rotation with the proposed
consumer tuple. Choose optional pooling or separately negotiated digest-proof
from those results. Both need their own proof/receipt/lifetime gates; WSS,
ordered replay and fleet-daemon authorization remain deferred.
