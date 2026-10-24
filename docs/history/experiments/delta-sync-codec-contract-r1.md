# Compact codec reconciliation, revision 1

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **candidate contract for Observer/RLCD review, not agreed ABI or runtime**.
This refines the unchanged 5,238-byte proposal SHA256
`4187fd9befabba300e2f8a36a653f4d2b564c1c0157cc9e35089cd09f47f9f56`.
No shared implementation starts until owning agreement. G0 appendix `a376bc84…`,
old lock/schema bytes and all resource/performance gates remain unchanged.
A1 relay and the separately reviewed owned-source intake API remain distinct.

## Candidate pure API

```text
NativeCodec.spec: CodecSpec
CodecSpec(encoding_id, encoding_schema_digest, native_descriptor_digest,
          fields, alias_spec, required_profile_features)
SyncProfile.normalization_features: tuple[str, ...]
NativeCodec.open(raw: bytes, budget: BudgetRef) -> NativeInputPlan
NativeCodec.entries(plan, space, ctx: NormalizationContext)
    -> owned iterator[NormalizedEntry | MembershipGroup]
NativeCodec.operations(plan, space, ctx: NormalizationContext)
    -> owned iterator[NormalizedOperation | MembershipGroupChange]
NativeCodec.head(raw: bytes, budget: BudgetRef) -> NativeHeadTicket
NativeInputPlan.header: HeaderRef
NativeInputPlan.close() -> None
NativeHeadTicket.header: HeaderRef
NativeHeadTicket.close() -> None

NormalizationContext.before, after_records: PublicStateRef
NormalizationContext.aliases.before, after: AliasView
NormalizationContext.binding, descriptor, budget, visits
NormalizationContext.pack(value: JsonValue) -> CanonicalValueRef
CanonicalValueRef.close() -> None
AliasView.get(alias: int) -> RecordRef | ABSENT
AliasView.resolve(alias: int, birth: FrozenValue) -> RecordRef

NormalizedEntry(space, key, value: CanonicalValueRef)
NormalizedOperation(space, op, key, expected_old_v, value: CanonicalValueRef?)
MembershipGroup(cohort, after_ref: RecordRef, mask: int)
MembershipGroupChange(cohort, before_ref: RecordRef?, expected_old_mask: int?,
                      after_ref: RecordRef?, new_mask: int)

PublicStageContext.compact_memberships: bool
PublicStageContext.membership_mask(cohort, record_ref, *, side: "before"|"after") -> int
PublicStageContext.membership_changes() -> owned iterator[MembershipGroupIntent]
MembershipGroupIntent(cohort, record_ref, old_mask: int, new_mask: int)
```

Names/types here are exact **candidates**, requiring Observer confirmation.
Per-space operations replace the earlier undivided operation iterator so the
engine controls staging order independently of JSON property/array order.
`CodecSpec` fixes encoding ID/schema digest, expected native descriptor digest,
field order, and an AliasSpec. AliasSpec names the declared `aliases` index and
the structural slot alias/birth paths; identity comes from the exact record key.
Reference positions restored by the concrete codec are fixed local schema data,
never wire-supplied paths. Profile/codec selection is trusted configuration.
Unsupported encoding, schema or compact-profile capability fails explicitly.
The candidate required profile feature is `provisional-memberships/1` for this
mask path; ordinary expanded staging requires no feature. The locally captured
feature tuple is immutable and included in identity checks. An absent tuple
means no optional feature, not inferred compact support. This is a candidate
local API identifier, not an allocation in an old wire capability enum.

`pack` snapshots strict integer-only JSON immediately into a generic-owned
canonical value under the same ledger. It grants no schema/domain admission.
The opaque CanonicalValueRef is single-consume, stage/cache/descriptor/codec-
bound, closes deterministically and cannot be passed to the material/proof
admission API. The engine adopts its already owned value without a second
normalized roster/byte copy or validation memo. The codec prepays its input DTO
and restores one value at a time; it drops that DTO before releasing scratch.
This candidate replaces unowned returned canonical bytes in the early proposal.
It is an ownership decision for joint review, not an implemented new capability.

The four semantic profile callbacks stay unchanged. A trusted compact-capable
profile must explicitly support the provisional-mask queries. Compact staging
does not expose pretend final membership cells through `ctx.after.lookup`:
that space rejects with `sync_memberships_pending` until field-token patch
application. `ctx.before` cells remain real admitted material. In compact mode
`ctx.operations`/`changed("memberships")` contain no fabricated per-cell DTOs;
the profile uses membership_changes and its actual record/observation changes.
Expanded mode keeps its existing operation/cell API. No silent profile adaptation.

## Alias sides, definitions and births

RecordRef is exact `[fivePartIdentity,[ownerEpoch,creationGeneration]]`.
Identity order remains hostScope/provider/namespace/nativeIdKind/nativeId.
An integer native alias is 1..2^64-1, never boolean, null or zero. It is scoped
to the complete native binding, including view, owner and original contexts;
it is unrelated to a configured Mesh source alias. Every encoded reference
carries a birth guard (epoch may be implied only by the exact message binding).
Its side is explicit or fixed unambiguously by its typed schema position.

| Reference / edit | Resolution rule |
| --- | --- |
| removal key or expected-old reference | BEFORE only, including removed records |
| inserted/replacement value referring to a live record | AFTER only |
| surviving slot with changed body/order | same identity, alias and birth; other changes reject |
| removed A and inserted distinct B sharing alias | BEFORE resolves A; AFTER resolves B with B's new birth |
| same record key remove plus put | duplicate logical operation rejects; no order-dependent rebirth |
| two surviving/new records defining one alias | conflicting definition rejects, even identical duplicate input |
| unknown alias, stale birth, foreign binding/view/context | rejects; no fallback to the other side |

The engine first validates every record operation and expected-old token, with
at most one operation per canonical record key. It extracts alias retirements
and additions from those records, validates their shapes, and constructs a
provisional overlay: retire all removed slots, then add all new slots together.
Adding an alias still owned by an unchanged slot rejects. Surviving slots cannot
change alias/birth. The resulting bijection is independent of input order.
Baseline defines it from all records; sparse deltas visit changed definitions
and indexed alias collisions only. No scan or copied dictionary of all aliases
is allowed for sparse reads/updates.

The semantic callback still validates identities, bodies, new-birth generation
and native scope. Its final declared alias-index patch must match the overlay
at every touched alias. Missing/extra/conflicting alias edits reject. Baseline
checks the whole declared index; sparse checks use changed aliases plus prior
admitted invariants. An overlay never commits by itself or authorizes a query.

Removing and reinserting the same identity across two accepted generations is
a new birth. An unobserved intermediate removal inside one atomic generation
is not inferred. This preserves Observer's current `_slot`/`_retire_alias` rules.
Scope/uncertainty identities without a live slot retain their full exact identity;
the codec cannot invent a live alias for them or infer absence from alias lookup.

## Masks: absence, null, zero and conflict

Agent bit i is exactly the G0 order runtime, phase, kind, savedIdentity, activity,
outcome, workspace, lastUpdated, latestTurn. Range is nine bits, 0..511; no
negative, boolean, float, string or high bit is accepted. An ordinary field's
null/absence remains lossless native data and is unrelated to these mask rules.

| Position | Accepted form and meaning |
| --- | --- |
| baseline group | nonzero mask 1..511 and AFTER ref; absent group means no cells |
| expected_old_mask | null means exact group absence; 1..511 means exact BEFORE mask; 0 rejects |
| before_ref | null iff expected_old_mask is null; otherwise resolves BEFORE |
| new_mask | 0 removes group; 1..511 retains/inserts; null or omission rejects |
| after_ref | null iff new_mask is 0; otherwise resolves AFTER |
| null old plus zero new | rejects as empty/no-key operation |
| nonzero old equal new | allowed assertion; supplies no reobservation/renewal authority |

When both refs are present their resolved identity AND birth must match. A
reused alias naming A before and B after needs two distinct group operations,
remove A and insert B. Duplicates are detected by resolved canonical
`[stableCohortID,identity,birth]`, not raw alias or input order; identical repeats
also reject. Compact membership input contains groups only; explicit cell input
in that encoding rejects rather than interleaving two writers of one cell.

Expected-old masks are derived from validated BEFORE cells, using bounded field
point lookups or its tag-bound exact group index. Provisional AFTER masks never
satisfy this check. Queries return 0 for no cells, although wire expected-old 0
is rejected as above. New mask bits remain assertions until semantic validation.

## Expansion, equivalence and rollback

The profile validates after bodies/observations/supports and returns the normal
data-only field-token/index patch. A JSON null field value hashes as C(null);
FieldTokenWrite.token=None means removal of a token and is a different operation.
No set mask bit may survive without its exact validated after field token.

For changed groups, the generic engine changes only differing cells and cells
whose field token actually changed. Changed field tokens also update incident
unchanged-mask groups under the bounded cohort registry/reverse index. Equal
tokens do no membership work. A removed token with an after bit still set
rejects. No old-context support is converted to a current cohort binding; the
existing Observer actual-reobservation/support predicate still decides that.
A receipt key, mask assertion, proof or token change alone cannot renew evidence.

The final memberships map equals an explicit operation set on the exact logical
keys and values. The grouped cohort-members maps and immutable seals must also
equal the explicit result. Same member root/count keeps its prior seal version;
a changed set uses the proposed generation under the same stable logical ID.
All eight tables, counts, body IDs, native root and source wrapper are checked
independently after the semantic patch. A codec-returned hash is never this
independent calculation. Native transaction ID remains H over C of the original
encoded transaction excluding its ID, independently scanned/hashed; it is not
the hash of expanded operations. Different encodings may have different IDs.

Explicit-vs-compact equivalence uses the SAME complete native descriptor/schema
and generation. A descriptor change changes body IDs/tokens and requires the
normal new binding/baseline path; no old-descriptor acceptance is transferred.

Alias overlays, group assertions, canonical values, derived cells, index edits,
cohort maps and root candidates form one stage. Callback/shape/root/budget failure
discards every provisional component, preserving the prior material/indexes and
never publishing current authority. A failed multi-transaction acquisition keeps
the existing candidate retirement behavior. Held errors and retired handles
cannot retain staged graphs, buffers or credit after owned cleanup.

## Identity, lifetime, budget and sparse work

Refs/candidates/input owners bind the exact profile and callback identities,
codec object/callback identities, immutable CodecSpec/encoding/schema, source,
descriptor, native binding and request/channel/cache epochs at their applicable
stage. Mutation/replacement retires the dependent scope. A ref's native identity
is independently checked during admission; no opaque ref skips those checks.

Plans, iterators, header/context/alias refs and CanonicalValueRefs are owned by
one admission scope and revoke on success, rejection, cancellation or replacement.
Close each iterator before its plan, clear exception chains, then release input
pins/credits. Access after retirement rejects, including saved iterator next().
Detached DTO creation is explicit and prepaid. A profile cannot retain a private
tree through a public ref. GC-disabled held-error tests are a runtime freeze gate.

Head uses NativeCodec.head only and validates a closed <=49,152-byte native head.
It never calls open/entries/operations/pack or creates a body plan. Head ticket
storage stays prepaid until checks retire; the unchanged complete proof cap,
2-second head-only deadline, separate catch-up and 15-second budget still apply.

Prepay all raw/framing/header scratch, parsed rows, alias/group overlays, encoded
canonical buffers, masks, expanded nodes, callback/DTO copies, persistent indexes,
iterators, controls and pins under the same 64 MiB heap/32 MiB encoded aggregate.
The owned-intake seam supplies source buffers; it is not an extra pool. Every
physical encoded copy counts in both caps. Adoption transfers existing ownership
without refunding a live allocation or charging a shared node as a new copy.

Baseline may do explicit O(N) normalization and bulk builds. Sparse work is
bounded by changed definitions/groups/field tokens, F=9, P<=32 and tree paths;
no roster/body scan or full alias/group map rebuild is permitted. Cohort renewal
does not enumerate its members. New indexed/packed storage still needs its own
quota/cleanup proof and the original cold/sparse/CPU/bytes/RSS gates.

## Vector and owning agreement gate

The accompanying stdlib review oracle/fixtures pin C/H, alias-side and mask
arithmetic, expected logical cell changes and eight-table/seal equivalence on
small synthetic data. They do not execute the future codec/cache or validate
Agent API 4 domain rows. Observer must independently reproduce them, supply/
confirm joined native field/body/observation cases, and agree these exact API
bytes before shared implementation. Exact encoding/frame schema IDs remain
unallocated until that review.

Runtime freeze must additionally run the same fixtures through strict raw
expanded/compact admission: alias conflicts/reuse/birth/foreign refs, mask
absence/null/zero/range/duplicates, token-only expansion, callback and each root
failure, no-body head path, codec/schema/callback replacement, plan/iterator
retirement, at-limit prepayment and GC-disabled held-error cleanup. Measure real
sparse visit/key counts and inclusive intake/stage peaks. These tests and joined
domain vectors are pending, not implied by arithmetic success. Draft 50-test/
33 MB experiments and preserved `68fb8a4`/220-test evidence remain separate.
