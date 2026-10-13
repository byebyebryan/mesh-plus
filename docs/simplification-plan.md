# Admission and ownership simplification

2026-10-13. Current accepted source is `c4ec7ca`, version 0.1.0a16,
SDK 1 / lock 3. Published a15 and its preceding transport/copy measurements
remain separate evidence. No older lock is restored or new capability advertised.

## Review findings

The supported profile DTO is shallowly frozen: its dictionaries/records remain
mutable. `ReadGuard.view` is also exposed and mutable. Static schema success
already has a complete-byte digest cache; native admission, proof/receipt checks
and owner callbacks intentionally continue at public boundaries. Replacing that
with a global “already validated” flag would require new ownership/compatibility
semantics. This pass does not make that change.

| Boundary | Checks retained | Work eligible for simplification |
| --- | --- | --- |
| Native source to publisher | New checked acquisition after nonce, original receipts, clock, profile, reconstruction, owned copy | Owner-facade integration proposal only; current hooks return mutable JSON |
| Delivery to Reader | Framing, binding, callback/native admission, proof and lease rules | No trusted-wire shortcut |
| Aggregate admission | Packaged schema, owner projection, scope/order/identity, native admission, original receipts/digest/expiry | One per-operation grouping of records; reuse grouped rows through checks |
| Guard accept/current | Transactional stream admission, input/result mutation isolation, new validation for mutable view, fresh clock/expiry evaluation | Cache only fixed error/control schema validators; no retained-state admission cache |

Aggregate admission repeatedly filters all fleet records for each host:
reconstruction, owner-projection equality, owner-less and warming checks repeat
that traversal. Grouping once within one synchronous admission removes those
repeated scans without retaining a body cache or weakening native validation.
Pass a fresh records list to the owner reconstruction callback so its mutation
cannot alter the grouped comparison input. Standalone `reconstructed()` retains
its existing public behavior. Pure callback invocation counts are not authority;
callbacks and scope/identity outcomes still run on each public admission.

Error and heartbeat/gap schemas are immutable packaged inputs. Their validator
objects can be reused like existing Delivery/profile schema validators, without
caching input success or current authority.

## Ordered loop

1. Pin current source and private baseline wheel, Python/dependencies and Tmux
   pure facade input. Keep installed-copy and wheel evidence distinguishable.
2. Capture before/after call counts and an independent expected-row oracle for
   1/4/16 hosts with ordinary/larger row sets. Measure grouped admission and the
   full local publisher/Reader/Guard path with profiling disabled.
3. Implement per-operation grouping and fixed schema reuse. Do not reopen the
   rejected generic cloning experiment, compact identity, TCP or binary wire.
4. Validate local/remote outcomes, empty/warming/unavailable hosts, record order,
   malformed proof/receipt/scope, reconstruction callback list mutation, source
   and returned-row mutation, guard-view mutation, expiry, gap/resync and EOF.
   Cover Tmux and independent Agent v1/v2 fixtures without active Agent imports.
5. Four fresh ABBA blocks compare separately installed baseline/candidate wheel
   processes, same public workload and exact work. Profiler results explain work;
   unprofiled CPU time decides benefit. Include IPC/owned SSH acceptance and
   optional WSS gates. No numerical carrier-only gain is inferred.
6. Canonical source gate, isolated installed wheel/core/conformance/SSH gates,
   pinned Tmux-only conformance, schema/source parity and owned fixture cleanup.
7. Commit/push implementation and dated evidence if correct and non-regressing;
   retain simpler code for demonstrated work reduction even if a 15% total CPU
   threshold is missed, but make no material-performance claim in that case.
   A correctness failure or reproducible >5% total CPU regression rejects it.

## Measurement rules

Report CPU per completed operation and phase, callback counts, latency, sampled
memory and fixture/consumer/oracle cost scopes. Use fresh subprocesses, separate
wheel directories and explicit manifests; never rewrite old inputs to accept a
new source. Four ABBA blocks, ordinary 32-row workload and fleet-heavy cases,
plus mutation/expiry controls. Keep setup/import/schema warmup outside timing;
fit current samples inside original leases or explicitly test expired samples.
Original receipts never renew because of repeated validation or transport.

An optional real Tmux native acceptance owns a private TMUX_TMPDIR/default-server
namespace. Tmux's selected installed a7 pure package can be snapshotted read-only
into a private test environment, with exact file fingerprints and installed-copy
provenance; it is not evidence of an independently downloaded immutable wheel.
No Agent source/service imports or sibling edits, live artifact selection,
release overwrite, authority changes, dotfiles, provider/desktop/action work,
physical suspend or ordinary fleet acceptance.

The full private admitted-state/validate-once concept remains a separate proposal
until public mutation behavior, callback guarantees and owner hooks are reviewed.
The current loop deliberately removes repeated work inside supported boundaries.
