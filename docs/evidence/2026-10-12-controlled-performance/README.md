# Controlled cached delivery assessment

2026-10-12 local date; measurements completed 2026-10-13 UTC.
**Keep released Mesh a15/SDK 1 and ordinary SSH selections.** This pass delivers
a reproducible Mesh-owned benchmark and rejects a copying prototype. It makes
no Mesh runtime, schema, lock, authority, release or deployment change.
Agent Observer development is excluded from imports, source edits and live tests.

## Inputs and method

The [plan](../../controlled-performance-plan.md) and
[runner instructions](../../../studies/controlled/README.md) define the scope.
Released Mesh a15 wheel SHA256
`42b25045f8f89afda61e56525f443a189dcc6769637aee5bcab959f096527f0f` and Tmux a7 wheel
`e73a88f89b38242631766dd45f6e669f43c54e36857e5716595c0a56321e5091`
run in isolated Python 3.13.7 with the exact dependencies and installed runtime
fingerprints in [the reviewed input manifest](../../../studies/controlled/inputs.json).
No sibling checkout is a benchmark input. Tmux's supported pure profile checks
every synthetic native frame; no ordinary native source or collector is used.

The decision-driving matrix uses the study harness at commit `8e6e9c4`, with
per-file digests retained in [raw metadata](matrix.json.gz). All **192 cases and
48 ABBA blocks pass** exact trace, proof/push/native-acquisition and consumer
admission matching. Each case executes forty replacements of a 32-row cache,
with one, two or four independent upstream readers. Original receipts remain
unchanged; each source replacement is consumed before the next step. A 50 ms
minimum interval permits backpressure rather than dropping steps. This is a
fixed-work synthetic workload, not ordinary proof or collection cadence.

Poll uses a persistent Client, Reader admission/composition and consumer guard;
push uses Reader.watch with its two baseline proofs settled before timing.
Every measured step requires one nonce proof per reader. All carriers use the
same cached-source proxy interface and generic CachedPublisher. IPC/WSS share
a publisher process; SSH has a publisher process per independent channel.
Actual SSH runs an owned same-user daemon/forced command with StrictModes.
WSS uses private disposable mTLS and loopback. No operational network policy changes.

CPU is own ticks with PID birth. Fixture source, publishers, reader/driver,
owned SSH roles and sampler are separately reported. The primary total includes
reader/driver and carrier/publishers; fixture source is separate. Reader/driver
also includes the independent native oracle, control and sampler RPC overhead.
CPU per delivered step is more useful here than utilization when backpressure
changes elapsed time. Memory is sampled PSS, not an observed transient bound.
The matrix driver keeps module/allocator caches; all source owners, publishers,
clients and carrier resources are fresh per case. These limits prevent a pure
carrier or production-budget claim. Full details are in [the summary](summary.json).

## Transport findings

Mean primary CPU milliseconds per delivered step per reader and accessible PSS,
averaged over four balanced blocks:

| Mode | Upstream readers | SSH / WSS CPU ms | SSH / WSS PSS MiB |
| --- | --- | --- | --- |
| Poll | 1 | 19.75 / 20.28 | 56.2 / 51.7 |
| Push | 1 | 26.94 / 27.19 | 58.8 / 54.0 |
| Poll | 2 | 14.95 / 15.38 | 82.3 / 52.8 |
| Push | 2 | 22.84 / 20.80 | 83.9 / 54.3 |
| Poll | 4 | 14.61 / 14.52 | 132.3 / 54.1 |
| Push | 4 | 23.06 / 21.24 | 133.8 / 55.6 |

Single-reader CPU is mixed, with no repeated >=15% improvement. At two/four
upstream readers, WSS's shared publisher reduces primary sampled PSS about
35–36%/58–59% in every block. Push CPU falls about 8–9%; poll CPU is roughly flat
or slightly higher. This is a **topology/sharing benefit**, not proof that TLS
WebSocket framing itself saves that memory. IPC already has the same shared
publisher topology and remains the local baseline.

Four raw upstream connections do not certify Tmux's prepared downstream-reader
capacity. A prepared service may already share a single SSH upstream, so these
savings cannot be applied to every ordinary consumer. Loopback results also do
not supersede or reproduce the prior
[ordinary-fleet observations](../2026-10-12-performance/decision.md). Background
host activity and 10 ms tick quantization remain explicit; no significance claim.

## Cost hypothesis and disposition

[Pure-boundary attribution](attribution.json) exercises 24 rounds through
publisher, Bridge result validation, pure Client callback, Reader composition
and consumer guard. It is instrumented, without carrier or cached-source I/O;
inclusive function timings overlap. External deepcopy caller edges show most
copying belongs to the pinned Tmux projection/reconstruction facade. The two
Mesh-owned wrap/compose copy sites are a small part of that cost.

The [private copying screen](copy-screen.json) compares an exact-built-in JSON
clone at those two Mesh sites. It preserves aliases, independent ownership and
the internal host/rows pair; cycles, subclasses and unusual Python objects use
the original deepcopy behavior. All twelve differential ownership cases and
the full existing admission path pass. Four ABBA fixed expired-frame blocks
are flat or slower (CPU reductions -1.64%, -0.05%, -0.53%, -0.35%). The extra
plain-data scan does not justify replacing the existing implementation.
**Reject the prototype; no packaged runtime candidate is built.** No check,
receipt, deadline, proof cadence or native validation is removed.

The study source remains reviewable for reproducibility. Its module-local
prototype patch is never installed, selected or used by the transport matrix.
Tmux's native copy semantics belong to its own project and are not changed here.

## Validation, refinement and preservation

[Gates and cleanup](gates.json) record 113 standalone core tests, 34 independent
WSS tests and 15 trace/pure-Tmux networking cases, without skips. The Tmux suite
includes update/restart/resync, forged evidence, expiry, healthy siblings,
cancellation and ownership. Additional current/expired actual IPC/SSH/WSS pilots
pass, including two/four raw upstream readers. Twelve candidate-copy differential
cases certify their narrow study scope only.

After the frozen matrix, the harness was hardened to retain subprocess creation
ownership on cancellation and continue all child retirement if a stream/client
close fails. A cancellation test and fresh carrier/current/expired pilots bind
that final harness; they do not retrospectively change the earlier matrix pin.
The attribution helper was renamed to avoid shadowing Python's stdlib profile
module. Initial interrupted/failed pilots remain private discarded attempts.

No Agent code or ordinary service was queried. Temporary sockets, SSH/TLS keys,
listeners and child processes are retired; no fixture directories remain.
No chezmoi/dotfiles, ordinary launcher, collector, source cadence or transport
selection was changed. No new release, schema/lock regeneration or packaging
acceptance is claimed; runtime packaging was unchanged.

## Next steps

1. Observer development continues independently against SDK interface 1. There
   is no new Mesh API, factory or artifact prerequisite.
2. Reuse the controlled runner when a specific Mesh optimization is proposed;
   pin new artifacts explicitly and retain fixed-work comparisons and failures.
   The rejected clone is not a reason to weaken native admission or ownership.
3. If multiple independent upstream readers are a concrete deployment need,
   compare the actual prepared-service topology before selecting WSS. Then close
   current-owner capacity, real-host authority/credential lifecycle, network
   recovery and coordinated suspend gates. Ordinary SSH remains selected.

The completed pass establishes repeatable measurement and bounded transport
evidence. It does not require a new TCP/gRPC/UDP backend or a core rewrite.
