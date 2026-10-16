# G1 compact native codec seam for review

This is a proposal, not a frozen ABI or an enabled route. The G0 appendix
`a376bc84…` remains unchanged. Current expanded full bytes are 3.11 times legacy
at 500 rows, so masks and compact references must be settled before G1 freeze.

Keep the four accepted semantic `SyncProfile` callbacks unchanged. Add a
separately injected, immutable pure native codec for structural wire expansion;
Observer owns its concrete Agent implementation/schema. It has no collector,
transport, currentness, filtering or action capability. Mesh owns lifetime,
budgets, generic normalized maps/indexes, mask expansion and independent roots.
Wire metadata never chooses an import or executable.

```text
OwnedSyncCache(..., native_codec=PlainNativeCodec())

NativeCodec.descriptor                      # exact native/schema/encoding data
NativeCodec.open(raw: bytes, budget: BudgetRef) -> NativeInputPlan
NativeCodec.entries(plan, space, ctx: NormalizationContext)
    -> owned lazy iterator[NormalizedEntry | MembershipGroup]
NativeCodec.operations(plan, ctx: NormalizationContext)
    -> owned lazy iterator[NormalizedOperation | MembershipGroupChange]
NativeCodec.head(raw: bytes, budget: BudgetRef) -> immutable bounded NativeHead
NativeInputPlan.header                      # kind/binding/tags/cursors/ID
NativeInputPlan.close() -> None

NormalizationContext.before: PublicStateRef
NormalizationContext.records: PublicStateRef
NormalizationContext.aliases.get(alias) -> [fivePartIdentity,birth] | ABSENT
NormalizationContext.binding, descriptor, budget, visits

NormalizedEntry(space, key, canonical_value_bytes)
NormalizedOperation(space, op, key, expected_old_v, canonical_value_bytes?)
MembershipGroup(cohort, record_ref, mask)
MembershipGroupChange(cohort, record_ref, expected_old_mask|null, new_mask)
```

All signatures/types are open for joint refinement. Codec/schema/encoding and
callback identities become part of cache/input-ref binding. The codec compares
the exact configured descriptor and strictly validates its raw schema, aliases,
group forms and resource limits before yielding owned values. Generic code
still independently checks duplicates, old values, birth/foreign keys, body
digests, seals, all roots and the source wrapper. The semantic profile admits
the normalized logical values and produces the existing data-only patch.

The plain codec preserves current expanded input. A compact codec is selected
explicitly during construction and protocol negotiation; unsupported encoding
fails. There is no automatic alternate profile or full-feed fallback.

Baseline staging parses record definitions first. Structural native row aliases
are binding/epoch/birth scoped; they are unrelated to configured Mesh source
aliases. A validated native alias definition updates a declared alias index
before decoding dependent bodies/observations/scopes. The semantic callback
still verifies that the normalized record slot and body have the exact native
identity, order and scope. The codec may restore declared identity/reference
positions; it cannot infer runtime, membership or expiry. A sparse transaction
uses only existing indexed aliases plus explicit changed definitions.

Membership masks can avoid transmitting per-field hash strings. Generic code
applies a group only after the semantic patch has supplied validated field
tokens. It independently verifies every old mask against the admitted cells,
checks exact birth and descriptor bit positions, obtains tokens from the staged
field index, then computes the global/grouped roots. A changed field token with
an unchanged mask updates only its incident cells under the bounded cohort
registry; it does not need a redundant wire cell update. Group insertion/removal
edits only changed cells. Logical cohort IDs remain stable; immutable seal
versions/root/count remain the accepted G0 data.

The profile needs a bounded public view of new group masks while validating
new observation supports, before derived cells exist. Proposed addition:
`ctx.membership_mask(cohort,record_ref) -> int`, plus a metered lazy iterator of
changed groups. These are provisional assertions, not current authority.
The profile can use its locally computed new field tokens; after callback return
the generic engine applies and independently checks all derived cells and roots.
Baseline mask expansion bulk-builds trees once rather than doing N successive
Patricia inserts. Sparse changes retain the existing path-update behavior.

Every plan/iterator is owned and closed in the same synchronous admission scope.
Its refs retire on success, rejection, cancellation or descriptor replacement.
The codec does not receive private graph pointers or retain a full normalized
roster DTO. Before-allocation charging and caller-visible materialization costs
remain mandatory; wire packing cannot conceal decoded allocation or CPU work.
Head decoding is separate and O(P), with no plan/body catch-up in the two-second
nonce operation.

Joint decisions needed: exact injected codec surface; declared alias-index
binding; exact raw compact schemas/group shapes; and the public provisional
mask query. Implementation of these shared additions waits for owning agreement.
