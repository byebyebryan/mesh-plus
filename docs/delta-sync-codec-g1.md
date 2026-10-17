# Compact normalization G1 source checkpoint

This is an opt-in generic implementation of the jointly agreed
[compact R2 interface](delta-sync-codec-contract-r2.md). It is source work, not
an accepted Agent codec, encoding/schema allocation, artifact or rollout.
`native_codec=None` continues the existing strict expanded route. A configured
codec never falls back to that route after failure.

`OwnedSyncCache(..., native_codec=codec)` captures the codec's frozen `CodecSpec`,
`AliasSpec`, method identities and the profile's explicit normalization feature
tuple. The public DTOs and context types are exported by `mesh_plus.sync`.
Replacement of a captured identity retires the cache. Configuration and payload
bytes cannot select a different codec, source or profile.

The engine opens one plan, copies its prepaid bounded structural header, then
exhausts one owned iterator per space in R2 order. It snapshots values through
`ctx.pack` into single-consume `CanonicalValueRef`s. Records establish a sparse,
simultaneous alias overlay; its final declared index patch must match. Removed
and replacement records resolve on distinct sides, with full identity/birth
guards. Sparse updates use indexed point lookups and changed definitions.

Membership groups independently check expected old masks against admitted
cells. The callback sees revocable, metered intents and provisional mask queries;
after-cell/token lookups remain blocked. Compact callback
`membership_expansion` must be exactly `()`. Generic expansion alone writes the
cells from validated field tokens, including retained bits in omitted or equal
masks. The existing body/link, token, index, seal and native-root checks complete
the stage atomically. Failure grants no candidate/current authority.

Raw transaction IDs are recomputed from canonical original encoded values,
including message-local receipt dictionaries, without retaining a second roster.
This reference implementation decodes one raw operation for each hashing pass;
its CPU cost belongs to future whole-pipeline measurements. Head confirmation
calls only `codec.head` with a native LF frame, compares the detached header
with independently parsed native head bytes, and preserves all ordinary nonce,
root, receipt, clock and deadline checks. It never constructs a body plan.

All new allocations use the existing shared ledgers and unchanged caps. Codec
leases expose reserve/close without a ledger or grow capability. Closing a lease
inside a codec call defers its refund until that call unwinds. Input and material
pins remain charged across foreign callbacks and plan cleanup; provisional
overlay/callback credit survives root assembly. Failure clears private exception
frames before owning cleanup. Public refs retain permits rather than roots.

The 25 focused tests in
[test_sync_compact.py](../tests/test_sync_compact.py) run with cyclic GC disabled
and retained public errors. Each test closes with all five ledger/pending
counters zero. They cover expanded/compact eight-table and index equality,
omitted/equal-mask token changes, mask null/zero/bool/range and duplicate rules,
competing callback writers, alias reuse/rebirth/duplicate operations, missing
alias patches, raw transaction IDs, root/callback/plan failures, intake retirement
and sibling isolation, material credit through reentrant plan close, stale handles, header preallocation refusal, scratch credit,
single consumption and sparse no-roster-scan behavior. Their codec deliberately
uses a whole small fixture DTO. It supplies no production streaming, capacity,
CPU, native-schema or transport acceptance evidence.

Mesh compatibility review of Observer `c161090` accepts the exact raw/native
convention for dependent integration: proposal SHA256
`585d4172400d628737ad68064ab8ecdd768fe7ef29456197c2671722f817c5c2`,
schema `cad76406eceab62bb5ba982f3472258b0f604d05dc890a865c7cd2acb43fb23e`,
vectors `a45ad79025dd8ae606db52735d9c63fa018c6d9640f5b2e81f31b01f43c387b5`,
verifier `9d925a96aa661a2b5ef90a8e5529f15c8591e7949c204fdbe697b94ecc440850`.
The four files match immutable commit bytes. Its stdlib verifier replay agrees
on Python 3.14.8 and 3.11.17: eight baselines, ten transactions, 144 field tokens,
seven joined rows and eight model rejection outcomes. This is counterpart
arithmetic/compatibility evidence, not independent native/runtime admission.
No schema/encoding ID is allocated or frozen here.

Actual Observer plan/profile integration, joined raw-to-admitted vectors,
complete streamed allocation/pin peaks, packed 2,000-row delivery, dense/cold and
recovery CPU/bytes, RSS/plateau, populated IPC/fixed SSH and an immutable installed
pair remain required. Existing failed performance evidence stays failed. A1,
relay completion transfer and deployed a7/a23 remain separate.
