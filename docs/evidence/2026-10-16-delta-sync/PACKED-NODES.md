# Private paged-node source checkpoint

Status: **structural prototype, G1 qualification open**. Runtime
`18e95c1791e66d20a211aa7d96b44d49b7fb78b7` implements the independent private
storage work reviewed by RLCD `0aa5f5b0f967fc8dd9ce72f82d18a90dd982683d`.
Its density review SHA256 is
`8dac4913e166eaa8ffed30bf604a4777bf6712ed1eaab0155a4190a0d16f7b18`.
No factory, profile, package or route enables this backend. The checkpoint
does not settle the pending compact codec or relay contracts.

## Representation and ownership

`sync/_packed_nodes.py` contains an explicit `PackedNodeArena(ledger)` used only
by private diagnostics/tests. Under that opt-in, hash maps use 256-slot leaf
and branch pages, fixed numeric arrays and digest planes. The entire page,
including unused slots, array/list headers, free list and metadata, is prepaid.
High-water registry capacity remains charged until arena close. Canonical
payloads, digest planes, key dictionaries and independent temporary/copy buffers
also consume the same encoded ledger. The 64 MiB heap and 32 MiB encoded limits
are unchanged.

Each occupied branch owns its actual two child edges. Dropping a leaf releases
its atom and key credit immediately even if a sibling retains that page.
Handles bind arena epoch, monotonic page identity and 32-bit slot generation;
stale, foreign and exhausted handles reject without wrapping. Temporary node
loans retain their control charge until their objects retire. Arena close
rejects live maps/nodes/loans and is idempotent after their release.

Long non-record keys may use private lossless deflate storage with a bounded
per-space dictionary. Roots still hash the exact original canonical key and
value bytes. Point lookup decompresses only its requested key. A normalized key
that outlives its temporary node loan receives a separately prepaid immutable
copy. Record keys stay directly stored because generic touched-key registries
borrow them. This private prototype rejects keys over 16,384 bytes and more
than 64 compressed spaces; these are not advertised native/profile limits.
The arena reserves bounded codec/hash scratch. Native allocator/RSS and complete
process accounting remain unqualified.

Private baseline staging recreates its internal normalized operation on demand
from material tables. `PublicStageContext.operations` remains the same immutable
tuple of revocable public operation references. All four callbacks, expected-old
checks, semantic field-token derivation, eight logical table roots, cohort seals,
ordered indexes and authority checks retain their existing roles. Generic patch
scratch reservations remain conservative; a development shortcut that subtracted
callback credit was removed before this checkpoint.

## Density diagnostic

The final [r5 report](packed-node-density-r5.json), SHA256
`ef1ff847308f2ce3bdf72453e03c810e054f6ee27f0c8efa7da5fac42d4fb0ff`,
binds every runtime source file and `scripts/profile-sync-density.py` to the
committed checkpoint. Inputs stayed unchanged during the run. Cyclic GC was
disabled; no `gc.collect` is used. Each of two independent descriptors has nine
fields per record, minimal bodies and no declared domain indexes. Baseline and
two one-row changes reproduce independent roots. Changes each contain 14
logical operations. Current/predecessor retention and staging overlap are
included in the accounted peak.

| Records per view, two views | Final heap including reservations | Final encoded including reservations | Peak accounted heap |
| --- | ---: | ---: | ---: |
| 100 | 2,812,002 B | 995,344 B | 3,846,931 B |
| 500 | 11,759,229 B | 4,529,947 B | 16,696,199 B |
| 2,000 | 45,329,829 B | 17,818,566 B | 65,238,013 B |

The 2,000-row peak leaves 1,870,851 bytes beneath 64 MiB. Final encoded retention
is not a measured encoded peak; every reservation still enforces the 32 MiB
limit. After close, decoded, encoded, reserved, pending and allocation-unit
counters are all zero, without cyclic collection. The earlier unpacked r1
fixture could not stage its first 2,000-row view; its two 500-row baselines
retained 25,183,396 bytes with a 31,940,541-byte peak. Those historical samples
have different generation counts and are not a matched performance pair.

This is a cache-internal material diagnostic. Caller-owned normalized fixture
and oracle graphs are outside its ledger. Actual Agent indexes/bodies, source
receive/parse/output buffers, delivery pins, native frames, installed consumers,
RSS and plateau are excluded. Therefore this fit does not establish aggregate
Agent or transport capacity. The raw 500-row baseline samples are about 1.87 s
per view versus the historical unpacked 1.02–1.04 s: a CPU regression signal,
not a matched gate result. Cold, dense and whole-pipeline CPU gates remain open.

## Sparse work and correctness

The [sparse report](packed-node-sparse-work.json), SHA256
`ac5a784d47f60521bdfa49cf58cb343c3df78c2d6c7bac594b6f7fa37ff7504d`,
records actual packed-record accesses as well as logical work. Instrumentation
keeps only work meters, so it cannot pin an older material map.

| Rows | Logical node reads, generations 2/3 | Branch hashes, generations 2/3 | Actual packed accesses, generations 2/3 |
| --- | ---: | ---: | ---: |
| 100 | 494 / 488 | 224 / 223 | 8,902 / 9,193 |
| 500 | 588 / 591 | 281 / 279 | 10,919 / 11,335 |
| 2,000 | 697 / 706 | 332 / 333 | 12,822 / 13,441 |

All six changes have 14 logical keys, 132 new allocation visits, 12 callback
lookups and one callback iteration. The only enumerated table entry is the
single bounded cohort head. Generation 3 includes retirement of the older
material root; reclamation is outside nonce confirmation. All independent
NativeRoots match and all ledgers close to zero.

Nine GC-disabled Mesh regressions cover 720 insertion permutations and bulk
roots, sparse update/query work, per-node atom retirement while its page stays
live, stale slot/foreign epoch rejection, failure before page allocation,
partial bulk duplicate and callback rejection with held public errors,
independent decompressed-copy ownership, repeated close and current/predecessor/
stage lifetimes. Fresh confirmation releases zero material nodes in the proof
operation. The selected 3.14.8 canonical gate passes 286 tests with no skips,
116 design and 169 delivery checks, Ruff, and the unchanged 33-input/25-schema
lock check. Python 3.11.17 passes 42 focused Mesh tests.

## Independent source compatibility

[Source checks](packed-node-source-checks.json), SHA256
`2b14d97333e29a0200bd5e92779bc8ab0906440fd33dbb8c978ddf5ce6c71631`,
bind both repositories' source/test/schema inputs, stable before/after. Observer
head `384d0cb1eeb98bd2784e42e4b73e90ef9a1f3e85` has the same runtime/tests as
`4030d50c0d21c1e34daad45c29e2373502a3413a`. No sibling files were edited.

Both Python 3.14.8 and 3.11.17 pass 99 default source/acquisition/profile/read
checks. Each also passes 30 Agent profile cases with the private storage opt-in,
cyclic GC disabled and every arena explicitly closed. These include actual
full/active semantic admission, eight domain indexes, ordering, mutation,
partial support, retirement/reinsertion, original expiry, failed proofs and
revoked public references. They use disposable fixtures, not ordinary services.

The initial reused harness ran all 31 profile cases and failed seven resource
assertions because it did not own/close the separately created arena. The final
owning harness closes stores/caches and then their arenas before the original
teardown checks. One in-method test assumes `reserved == 0` while that external
arena is intentionally live; it is explicitly excluded from private runs and
passes in both complete default suites. It is not counted as a private pass or
skip. The first report/logs and runner are retained as `*-harness1.*`; their raw
report's original log names map to those retained filenames. No Observer
assertion was edited. Arena retirement is checked independently after every
private case and again at the end.

## Reproduction and remaining gates

Use a fresh isolated checkout/output to preserve dated files:

```sh
rtk proxy .venv/bin/python scripts/check.py
rtk proxy .venv/bin/python -c 'import gc, runpy; gc.disable(); runpy.run_path("scripts/profile-sync-density.py", run_name="__main__")' --packed-nodes --generations 3 --output docs/evidence/2026-10-16-delta-sync/packed-node-density-r5.json
rtk proxy .venv/bin/python docs/evidence/2026-10-16-delta-sync/verify_packed_sparse.py
rtk proxy .venv/bin/python docs/evidence/2026-10-16-delta-sync/verify_packed_source.py
```

`packed-node-manifest.json` binds the reviewed inputs, final results, scripts,
logs and retained development diagnostics. Density r1–r4 are uncommitted-source
development samples, not results for the frozen runtime. R3/r4 used the removed
callback-credit shortcut and are superseded. The earlier sparse diagnostic that
kept baseline map references is explicitly named `held-baseline`; only the
unpinned final report supplies the sparse counts above.

G0 appendix `a376bc84...`, LOCK `11736752...`, agreed input API `7f7751ec...`,
codec candidate `a67f11ae...`, relay r2 `8616bfba...` and lifecycle r3
`eb5c217c...` remain unchanged. Root has resolved the r2/r3 lifecycle questions
at contract level; Observer same-byte agreement and explicit A1 closure still
precede dependent relay work. Compact masks/aliases and source/codec plans also
retain their joint-review gate.

Actual Agent full/active aggregate resources, all intake/output/pins, encoded
peak, native frames and packed recovery, CPU/RSS/plateau, installed artifacts,
native IPC/fixed SSH and end-to-end gates remain open. No new wheel/version,
artifact selection, service/provider action, sibling mutation or rollout occurs.
