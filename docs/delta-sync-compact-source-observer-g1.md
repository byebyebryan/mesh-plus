# Compact source compatibility checkpoint

Observer `7213084557ed4dd63361567bb75bd262b2e517bc` passes its unchanged compact
source and related component tests against Mesh runtime
`6fce5ed0e997d021e7532051fe985c3693962c3e`, exported from evidence checkpoint
`2ec7bcf3a3422a68bd522502928a648954932e1d`. The
[receipt](evidence/2026-10-16-delta-sync/compact-source-pair-review.json) pins both
exports, the producer's declared inputs and logs, and the independently executed
results. No runtime code changes in either repository belong to this review.

The explicit `CachedCompactAgentSyncSource` chooses the compact structural
parser through the existing prepaid owned session. It captures a static parser
function without retaining a bound parent callback. Full and active native
material stays opaque until independent Reader normalization. Original nonce
heads use the original parser. The expanded source remains the default strict
expanded route, and unowned compact byte methods reject before I/O. There is no
format sniffing, fallback, new request grammar or schema/encoding ID allocation.

The [runner](evidence/2026-10-16-delta-sync/verify_compact_source_pair.py) independently
executes **203 tests on each Python 3.14.8 and 3.11.17**, with cyclic GC disabled:
seven unchanged compact-source methods and 196 related owning component tests.
Both runs have zero failures, errors or skips. All loaded project modules match
the corresponding immutable export; the subprocess import check receives the
same explicit source paths. Producer canonical results are hash-verified saved
evidence, not independently rerun here. Mesh's prior 355-test gate retains its
original source provenance and is not reattributed to this documentation change.

The new methods use the actual disposable native `Runtime` Unix dispatcher with
synthetic `ServiceState` and collection disabled. Six full/active zero/one/four
transaction cases compare sealed bytes to the exact dispatcher return, stage
through the ordinary compact Reader, obtain fresh original native heads and
check lossless DTO equality. Other cases reject wrong source encoding without
fallback, forward a 200,000-character invalid opaque body before independent
Reader rejection, prohibit compact scanner/schema work in the head path and
revoke a delivered watch update while preserving a prior baseline ticket.

The tests disclose private Reader nonce setup, a native-byte pin and a test-owned
proof carrier. They exercise source IPC and Reader composition without a relay
or authenticated controller. They do not qualify populated native providers,
fixed SSH, an immutable installed pair, selected routes or rollout. Native owner,
test oracle and Reader accounts are separate; final zero counters do not prove
aggregate 32/64 MiB peaks, RSS, dense nine-field capacity, predecessor/stage/pin
overlap, CPU savings or 2,000-row delivery/recovery.

The source's consuming-ref pruning code is unchanged at this Observer checkpoint.
The [committed public retirement query](delta-sync-ref-retirement-g1.md) is
available, but the separate Observer adoption and final paired original/hardened
pin-retirement, physical-credit and sibling checks remain open. Controller/carrier
runtime work also retains its independent owning contract and execution gates.

To reproduce using immutable exports and fresh output paths:

```sh
rtk proxy /path/to/python -B docs/evidence/2026-10-16-delta-sync/verify_compact_source_pair.py \
  --mesh /path/to/mesh-2ec7bcf-export \
  --observer /path/to/observer-7213084-export \
  --output /path/to/fresh-result.json --log /path/to/fresh-unittest.log
```
