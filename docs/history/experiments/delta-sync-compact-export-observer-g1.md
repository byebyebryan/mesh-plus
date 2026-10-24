# Native compact export with current Mesh source

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

This bounded G1 check pairs immutable Observer
`fc7579bd2e3e6b020b4e66958e8e425e60889b93` with Mesh
`cdb8cd0e3c5f11e65728d2de7c157e89ca26d819` / runtime `f32218b`.
It adds no production source, public API, encoding/schema allocation or route.
The producer's earlier `05ad6fc` results retain their exact source provenance.

On Python 3.14.8 and 3.11.17, all 196 focused tests pass without skips, errors or
failures, with cyclic GC disabled before imports/operations. These are ten
unchanged owning serializer tests plus 186 owning codec, parser, source,
completion, profile and Reader component tests. This is independent execution
and source review of owning tests, not an independently designed producer suite
or a rerun of Observer's full 924-test gate.

The explicit `ServiceState(sync_serialization="compact")` writer emits native
compact baselines and journal transactions. Small full/active outputs restore
the same logical eight tables and native roots as separate expanded owners.
Receipt refreshes, token changes under omitted/equal masks, row insertion/removal,
canonical raw transaction IDs and unchanged original heads/control are checked.
The compact option requires the encoded backend; normal defaults stay expanded
and a journal refusal reports explicit baseline recovery without another format.

The actual compact Reader consumes those writer bytes through its normal public
admission/staging APIs. A fresh head then passes normal proof confirmation and
the public export equals the owner's native DTO. Expected-old/root faults reject;
a valid retry reaches the expected target. Only the already disclosed test-owned
nonce builder and native fixture retirement use private scaffolding. No private
Observer state is used by Mesh runtime. Fixture source names and encoding IDs
remain explicit unallocated test configuration.

Serializer-only tests forbid a whole record/body/membership walk for the selected
100-row sparse change and bound receipt scans. That does not qualify the owner
normalizer's total work or the failed matched dense CPU gate. Frame/preallocation
and optional journal refusal retain their owning accounting assertions. Generic
Reader teardown checks all six ledger counters zero; native owner tests retain
their separately charged fixed account base and clear encoded staging. Neither
assertion measures one aggregate process ledger or physical RSS.

The actual source is still explicitly configured for expanded acquisition.
Direct compact writer-to-Reader checks and expanded component socket tests do
not demonstrate compact source dispatch, source-to-relay splicing, controller
negotiation, populated IPC or fixed SSH. The detached-head source ref tracking
finding and its exact public-query coordination remain separate.

The [byte-bound receipt](../../evidence/2026-10-16-delta-sync/compact-export-pair-review.json)
pins the exact runner, loaded modules, source manifests, commands, results and
logs. Producer cold 100/500/2,000-row screens are not rerun or promoted here;
their membership fixtures are not nine current fields on every identity.
Current/predecessor/stage/slow-peer aggregate 32/64-MiB accounting, deliverable
2,000-row recovery, dense/cold/recovery CPU and bytes, RSS/plateau, native provider,
installed immutable pair and consumer acceptance remain open. No artifact,
package/version, selected a7/a23, service/provider, sibling or rollout change
occurred. Earlier evidence remains bound to its original inputs and exclusions.
