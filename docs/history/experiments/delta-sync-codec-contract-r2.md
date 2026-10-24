# Consolidated compact normalization contract, revision 2

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **Mesh agrees with Observer's normalization decision; concrete r2
reference completion is submitted for joint same-byte review**. This document
is the complete intended next generic API/reference contract, not an implemented
codec, encoding/schema allocation, G1 freeze or artifact acceptance. Shared
compact-mask/alias/plan implementation still waits for owning agreement on this
completion and its raw-reference interpretation. A1 relay is a separate packet.

Reviewed immutable inputs:

- Mesh original proposal SHA256
  `4187fd9befabba300e2f8a36a653f4d2b564c1c0157cc9e35089cd09f47f9f56`.
- Mesh r1 at `3342d85`, SHA256
  `a67f11aee6c4b9f50048fbda55bdd4f82c6766ec69cd07abf31b749c3ba5b0b8`.
- Observer owning review `38e2b64ac5bfece3e4a0da224ed44a9d43579ebe`,
  `docs/delta-sync-codec-review.md`, SHA256
  `69efa803c69c3ed6f9532659d3daae12c2c7dc71826952f7df1dad67da92b8d6`.
- Observer consolidated decision `ffa302fba16f90d00c39229ae810547aeb850908`,
  `docs/delta-sync-normalization-decision.md`, SHA256
  `35b1911388e75f4bc2a87087f23f07f7ca95346719933d7b37a5365d528734d6`.

Mesh accepts that exact Observer decision's proposed signatures, AliasSpec and
HeaderRef completions, streaming phases, before/provisional/final alias split,
mask/token rules and compact single-writer patch rule. This records the
previously requested Mesh response to those bytes; it does not pretend that
Observer has already accepted the additional concrete raw spelling below.
The older review's open changed-group/patch questions are answered here by
those later owning decisions, not reopened as implementation permission.

Frozen G0 SHA256
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`,
agreed input API `7f7751ec...`, old LOCK/schemas and existing numeric gates stay
unchanged. Private storage work is independently authorized by RLCD `0aa5f5b`.
No sibling runtime, service, route, package/version, artifact or rollout changes.

## Exact proposed generic API

```text
OwnedSyncCache(profile, source_binding, budgets=None, *, request_binding=None,
               ledger=None, local_owner=False, native_codec=None)
NativeCodec.spec: CodecSpec
CodecSpec(encoding_id, encoding_schema_digest, native_descriptor_digest,
          fields, alias_spec, required_profile_features)
AliasSpec(index: str, alias_path: tuple[str, ...], birth_path: tuple[str, ...])
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
HeaderRef.materialization_bytes: int
HeaderRef.materialize() -> dict

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

The codec/normalization signatures follow Observer's exact decision. This r2
also pins the public intent representation and raw reference spelling for
counterpart confirmation. The constructor line makes the original proposal's additive injection keyword
explicit. `native_codec=None` selects the strict built-in expanded path, with
no wire sniffing or fallback. A supplied supported codec is trusted local
configuration, captured for that cache lifetime. Compact setup requires its
exact encoding/schema/native descriptor and every declared profile feature.
Existing methods and plain mutable/raw-byte revalidation remain independently
strict. No native source/factory/import can be selected by a payload. Topology
and A1 relay factories retain their separate reviewed contracts.

Agent AliasSpec is `("aliases", ("alias",), ("birth",))`; full identity comes
from the record key. Neither a source alias nor a compact index is identity.
Per-space iteration lets the generic engine control phases independently of
JSON property/array order. Baseline uses entries; transactions use operations.
For a compact material plan, the controlled order is records, receipts, cohorts,
bodies, observations, scopes, metadata, memberships, then semantic admission and
generic completion. There is at most one live space iterator; every required
space is exhausted and validated before a candidate can survive. A malformed
late value rejects the entire stage. A head/control never enters these phases.

`open` scans the complete bounded JSON grammar and closed structural framing,
without restoring a whole native DTO/roster. Each returned wire value passes its
complete structural schema before yield. Domain/join/support and cross-record
checks remain the semantic callback's independent work. The plan may retain
bounded per-space offsets and receipt-key dictionaries, not a decoded body or
observation roster. Iterator scratch is bounded to the current value plus
explicitly charged alias/group/receipt overlays.

`HeaderRef.materialization_bytes` advertises sufficient prepaid heap credit for
an independent bounded structural dictionary. Both it and `materialize()` reject
after ticket/plan retirement. The caller reserves before copying and retains
that independent credit through actual dictionary/child-alias retirement; closing
the original ticket cannot refund a surviving copy. Extra encoded copies need
separate encoded credit. Header access retains no opaque body/observation roster
or authority. The head/control dictionary preserves explicit kind/status.

NormalizedEntry/Operation and MembershipGroup/Change are frozen, exact DTO types.
The codec owns and prepays their plain strict JSON key/cohort/record-ref fields
until synchronous engine adoption/snapshot, then drops its copies before scratch
refund. The value field is the separately minted CanonicalValueRef; ownership
transfers once without a second canonical value copy or validation memo. No
borrowed raw span/private graph is a normalized value. Returning an iterator
without exhausting/closing it never constitutes structural success.

MembershipGroupIntent is an engine-minted immutable, metered, revocable public
handle with exactly `cohort`, `record_ref`, `old_mask`, `new_mask`. Cohort and
record_ref expose the existing readonly public array-reference materialization
pattern, including prepaid materialization bounds; they do not expose private
arrays. Mask properties are exact integers 0..511, with zero meaning no cells.
A fresh property access or iterator next after stage retirement rejects; already
detached scalar values grant no authority. Baseline emits one intent per declared
group with old_mask=0. Delta emits only explicit resolved group assertions,
including equal-mask assertions, once per resolved key; iterator order confers
no semantic precedence. Token-only
implicit cell changes are computed after the callback and do not fabricate
pre-callback group edits. An omitted group inherits its admitted before mask.

AliasView's returned full record ref uses that same public readonly array-ref
pattern. A codec needing a plain JSON ref for its normalized DTO explicitly
prepays materialization and retains its copy credit through engine handoff.
The DTO and callback intent are different lifetime boundaries, with no private
tree or borrowed raw payload exposed at either boundary.

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

In compact mode `DomainIndexPatch.membership_expansion` must be exactly the empty
tuple `()`. A nonempty expansion rejects even if it claims the same cells or
roots. The profile returns its normal independently validated field-token/index
patch; the generic engine is the only cell expander. Expanded mode retains the
existing G0 data-only membership_expansion path. Compact wire cannot also contain
explicit membership-cell edits. There is no second writer before or after the
callback and no N-per-field public Operation roster hidden in patch output.

## Alias sides, definitions and births

RecordRef is exact `[fivePartIdentity,[ownerEpoch,creationGeneration]]`.
Identity order remains hostScope/provider/namespace/nativeIdKind/nativeId.
An integer native alias is 1..2^64-1, never boolean, null or zero. It is scoped
to the complete native binding, including view, owner and original contexts;
it is unrelated to a configured Mesh source alias. Every encoded record reference
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

## Concrete raw reference completion for owning review

This is a candidate reference grammar for Observer's separately owned Agent
compact schema. It allocates no encoding ID/schema digest and is not a complete
native envelope/record schema. Observer must confirm these exact positions or
return a concrete alternative before dependent shared implementation. Fixed
local codec/schema data identifies every reference position; wire data cannot
supply paths, a codec or a side selector. Unlisted opaque/context values retain
their exact existing logical form rather than being guessed into aliases.

```text
RawRecordRef = [alias, birthGeneration]
RawGroupSide = [receiptIndex, alias, birthGeneration]
RawBaselineGroup = [afterSide: RawGroupSide, mask]
RawGroupChange = [beforeSide: RawGroupSide|null, expectedOldMask: int|null,
                  afterSide: RawGroupSide|null, newMask: int]
receiptRefs = {before: [fullReceiptKey, ...], after: [fullReceiptKey, ...]}
fullReceiptKey = [provider, namespace, component]
```

Every tuple and object is closed and has its exact stated length/keys. Record
alias is an integer 1..2^64-1; birthGeneration is an integer 1..proposedGeneration.
Bool is not an integer. Owner epoch is restored only from the exact message's
validated NativeBinding. A transaction cannot change that binding in place.
The full restored birth must match the explicitly chosen before/after alias
view. Baseline uses after only. Native aliases, birth and all full identity
components remain checked independently; no bare alias reference is accepted.
Context/uncertainty identities that do not name a live slot stay full identities.

Each `receiptRefs` array has at most 32 distinct full keys, in its declared
message-local order. Entries are strict native receipt-key tuples and duplicates
reject, even if unused. Baseline before is exactly empty. The arrays are bounded
reference dictionaries, not a completeness/census claim; they may name a subset
of keys and never confer receipt health, reobservation, support or currentness.
Before keys must exist in admitted before receipts. After keys must exist in
the candidate receipt state. The supported codec resolves that bounded state
from the message's receipt edits plus before keyed lookups; it does not scan a
body/alias roster or require a new private query API. Final profile admission
still validates all restored receipt/support/scope relationships independently.

Receipt indices are exact integers 0..len(the selected dictionary)-1. Index
zero is valid; null, bool, negative, missing and out-of-range indices reject.
There is no lookup fallback to the other dictionary. Reordering after keys or
removing an old receipt cannot rebind a before removal or old support reference.
The complete native transaction ID covers these original raw dictionary bytes
under the same canonical transaction-ID formula as other encoded fields.

| Typed position | Record and receipt reference side |
| --- | --- |
| Record/body/observation removal key or expected-old material reference | BEFORE only |
| New record/body/observation/support value | AFTER only |
| RawBaselineGroup.afterSide | AFTER dictionary and alias view |
| RawGroupChange.beforeSide | BEFORE dictionary and alias view |
| RawGroupChange.afterSide | AFTER dictionary and alias view |
| Cohort deletion key | BEFORE receipt dictionary |
| Cohort put key/value or explicit cohort support on a replacement observation | AFTER receipt dictionary |
| Original context/negative/uncertainty values | Exact original expanded values; no invented live alias/index |

A RawRecordRef receives its side from that fixed typed position. An old and new
reference inside one operation are resolved separately before comparison. Record
and receipt references for expected-old values cannot be decoded through a new
candidate catalogue simply because an alias/index number is the same.

For RawGroupChange, beforeSide is null iff expectedOldMask is null; afterSide is
null iff newMask is zero. Null old plus zero new rejects. If both sides exist,
they must resolve to the same full receipt key AND exact full record ref; index
numbers need not match after a dictionary reorder. A cohort or record/birth
change therefore requires separate removal and insertion groups. The normalized
MembershipGroupChange keeps one stable full cohort key and the corresponding
full before/after record refs. Duplicate detection uses that resolved logical
key, never receipt index, alias number or wire order.

A deliberate reorder fixture has before receipt index0=runtime, index1=history;
after index0=history, index1=runtime. Alias7 names A/birth1 before and B/birth2
after. Removing `[[0,7,1],1,null,0]` addresses runtime/A/birth1. Inserting
`[null,null,[1,7,2],1]` addresses runtime/B/birth2. Combining both refs into one
group rejects because their identities/births differ. If runtime is removed from
after receipts, its before removal remains valid; a new after runtime support
cannot silently resolve through the old dictionary. The arithmetic supplement
pins these results and malformed/duplicate/birth cases. Actual joined raw/native
schema and transport execution remain later qualification gates.

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

Head uses NativeCodec.head only and validates a closed <=49,152-byte native head/control.
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

## Exact agreement and remaining qualification

Mesh's original stdlib r1 oracle/fixtures remain byte-for-byte unchanged: eight
positive cases, 37 rejections and four optional field-token inputs. Observer's
committed `ffa302f` independently reproduces positive arithmetic/eight-table
roots/permutations and supplies joined full/active synthetic native fixtures.
The independent arithmetic verifier reports zero independently executed
rejection cases; its replay of all 37 through the upstream oracle is separate
evidence. Do not call that replay independent rejection qualification.

The r2 receipt/reference supplement adds the exact message-local before/after
spelling above without pretending to be the future native schema or cache.
Both sets of arithmetic and joined native split/token fixtures must remain equal
when the actual encoding/schema is chosen. Same logical descriptor/generation
means exact eight-table/cohort/native/source equality. A native descriptor change
requires recomputed body IDs/tokens and ordinary new-binding admission.

Mesh's acceptance of Observer `35b19113...` settles its signature, phase,
AliasSpec/HeaderRef and compact single-writer decisions at the owning-contract
level. Observer must confirm the r2 public handle/raw-reference completion and
coordinator reconciliation before shared dependent edits; a conceptual/no-domain-
conflict review is not an implementation freeze. The complete Agent raw compact
schema and concrete encoding identity remain unallocated and need their own
same-byte owning vectors/strict-schema confirmation. No implementation-first
review or new general execution permission is requested.

Runtime freeze must run these fixtures through complete strict expanded and
compact admission: alias conflicts/reuse/birth/foreign refs; receipt dictionary
reorder/removal, missing/duplicate keys and wrong-side refs; every mask/null/type/
duplicate rule; omitted/equal-mask token expansion; nonempty compact patch rejection;
late malformed value and incomplete iterator; callback/index/table/seal/native/
source-root failure with atomic rollback; context/plan/iterator/header retirement;
no-body head/control; codec/schema/callback replacement; preallocation refusal;
GC-disabled held-error and repeated-cancel cleanup. Actual sparse visits/key counts
and inclusive intake/stage/output/pin peaks remain required. Baseline, cold/all-body/
recovery and whole-pipeline CPU/bytes, RSS/plateau, actual native IPC/fixed SSH and
immutable installed full/active/old-route pairing remain open. Prior private
storage fit and failed dense CPU are separate evidence. No release or rollout.
