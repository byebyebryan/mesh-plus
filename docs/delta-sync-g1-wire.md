# G1 wire allocation and cache integration checkpoint

Proposed concrete encoding, pending counterpart agreement. This supplements the
accepted G0 appendix without editing its pinned bytes. Changes of accepted
meaning return to joint review. Native tables/adapters remain Observer-owned;
generic framing, cache, proofs and transport remain Mesh-owned.

## Identifiers

- Generic opt-in delivery: `mesh.state-sync/1`; sync interface 1, separately
  negotiated from SDK 1 / Delivery 1.
- Commitment algorithm: `mesh.patricia-sha256/1`, exact G0 framing.
- Observer local requests already declare `agent-observer.sync` and
  `agent-observer.active-sync`, each `version: 1`; accept those identifiers.
- Proposed pure Mesh profiles: `agent-observer.mesh-sync.v1` and
  `agent-observer.mesh-active-sync.v1`. Old full/active profiles stay explicit.
- Native descriptor digest is lowercase SHA-256 of C(native descriptor), matching
  Observer's independent `descriptor_digest`. Native/body/schema bytes are
  distinct from a configured Mesh profile/source binding.

No candidate package version is allocated by this checkpoint. Preserve a23 and
all existing private artifacts; reconcile an unused version before building.

## Native messages

Observer's current response descriptor carries native protocol/version; do not
repeat those properties at top level. Use `kind` in responses. A native
descriptor is Mesh-free immutable JSON with the native contract/schema digest,
view/selector, commitment revision, eight spaces and encoding/field registry.
Its exact schema/digest is supplied by Observer and pinned in the new Mesh profile.

```text
baseline {
  kind:"baseline", descriptor,
  nativeBinding, tag:[bindingDigest,generation,nativeRoot],
  cursor:[ownerEpoch,generation,nativeRoot], tables
}

transaction {
  kind:"transaction", descriptor,
  nativeBindingDigest, transactionId,
  baseTag, resultTag, baseCursor, resultCursor, operations
}

head {
  kind:"head", descriptor,
  nativeBindingDigest, tag, challenge,
  ownerClock:{bootId,clockDomain,boottimeMs,ownerEpoch,uid,hostScope},
  originalReceipts, cohortHeads, attenuation
}

control {kind:"control",descriptor,status,reason,tag?,cursor?,ownerClock}
```

The native cursor is deterministic as accepted at G0. Every descriptor must
equal the configured expected descriptor. All objects are closed;
response-kind-specific fields are required. Native `clockDomain` preserves its
original `time:[id]` representation; the profile's bounded head projection maps
it to Mesh's reader clock domain without changing rooted original bytes.
One encoded native message fits the existing 8,404,992-byte bound, except the
native head has the tighter accepted 49,152-byte ceiling. Head clocks are real
BOOTTIME/context; committed publication/observation anchors stay in rooted state.

For ordinary spaces, a baseline table is an array of `[key,value]` entries.
Array position carries no record order; the accepted order key/index does.
Logical state is exactly the accepted eight-table registry. The normalizer
strictly checks native schemas and per-host identity before generating typed
operations. A record slot supplies the immutable epoch/birth-bound wire alias
used by compact memberships. The precise slot/observation/scope native schemas
remain an Observer input to this joint checkpoint.

For ordinary spaces, operations are per-space arrays:

```text
["put", key, <old V hex or null>, value]
["remove", key, <old V hex>]
```

Null expected means absence, never a wildcard; duplicate table keys/operations
fail. Expected tokens use G0 V(space,value), not a body digest or leaf hash.
The transaction ID is the G0 domain-separated hash of the canonical native
transaction with only its transactionId property omitted.

Compact membership wire remains unresolved against Observer's current expanded
per-cell envelope implementation; settle before final G1 schema freeze. Proposed
baseline groups use a stable logical cohort ID, record ref
and nine-bit mask, with field bit order from G0. Changes use old/new masks or
equivalent typed group replacements; explicit changed-body tokens may change
one field with the same mask. Their exact native schema remains pending joint
agreement. A full `[identity,birth]` ref works without adding a separate slot
alias: group once per record/cohort, rather than repeat it for all nine cells.
Each receiver derives the exact changed logical cell tokens after
validating new content, compares against the admitted old tokens, and edits only
different cells. Global and grouped member trees share the same owned token atom.
It must not rebuild a group to produce a new seal or rewrite N observation refs.

## Cache callback and proof seam

The generic cache admits encoded immutable native bytes. It stages ordinary
operations, then calls `admit_baseline` / `stage_delta` with PublicStageContext.
`ctx.after` is provisional. DomainIndexPatch supplies validated field tokens,
compact membership expansion, declared index/rule writes/removals, affected
scopes and invalidations. Generic code checks/freezes/budget-charges those data,
applies derived logical member updates, computes table/cohort/native/source
roots locally and compares exact expected tags. No callbacks can commit early.

Public lookup returns revocable read-only refs, not pointers into a retained
root graph; explicit changed-value materialization/export is detached and charged.
Profile index schemas and original-receipt lease projections must be declared
before the dependent cache/profile adapter is implemented. Head rules restrict
already admitted original evidence; they cannot invent or extend its support.

Mesh proof is a separate closed source/request-bound envelope around the compact
native head. It commits exact host/source/profile, request/channel/reader epoch,
nonce, publisher/clock, source/native tag and original remaining receipt leases.
No body or transaction chain occurs inside its two-second operation. An owner
tag mismatch returns moved/revokes, followed by separate bounded catch-up and a
new nonce within the absolute acquisition deadline. No old-route fallback.

Before dependent integration: Observer confirms native descriptor/table/
membership/head shapes; Mesh confirms public index/patch and original-lease
projection types; both produce exact native/schema/transaction/head vectors.
No accepted runtime or installed artifact is implied by this planning checkpoint.

## Source implementation checkpoint

The additive `mesh_plus.sync` package now has the material and confirmation
engine. No old profile, schema, command or deployed selection dispatches to it.
The canonical source gate includes reconstruction, ordered-index and cache
tests. This is an implementation checkpoint, not G1/G2 qualification.

`IndexSpec(..., ordered=True)` declares an ordered profile index. Keys follow
the total JSON order null, boolean, integer, string, array, object; arrays and
object pairs compare lexicographically. The persistent AVL index changes only
O(log N) paths. `iter_keys(prefix)` seeks the first prefix and visits matching
keys without a full sort. A profile encodes its reviewed native sort in keys;
the generic cache does not choose record display order. This extension awaits
Observer's ordering review before the final descriptor is frozen.

The public patch data are exported from `mesh_plus.sync`. A field-token or
rule key is `[fivePartIdentity,birth]`. `RuleWrite(key,value)` stores bounded
immutable JSON; the generic engine independently checks its record birth.
Field token removal also accepts the exact record birth automatically retired
by that transaction. Derived membership puts pass the same birth, field-token,
old-value and seal/root checks as ordinary logical membership operations.

`check_head(ctx, head)` receives revocable immutable refs. `ctx.view` supplies
table/index queries into the exact candidate, with no currentness;
`ctx.binding` is NativeBinding; `ctx.tag` is SourceTag;
`ctx.original_receipts` is the bounded raw `[key,value]` list. The callback
returns `HeadRules(original_receipts=(OriginalReceipt(...),...),
allowed_receipts=None|tuple[plain receipt key,...])`. Each projection declares
an owned `Atom` key, exact raw receipt value hash, accepted count, health and
original absolute owner expiry. Generic code reowns the projection, checks all
receipt keys/value hashes, bounds both native and bridge attenuation by the
original expiry, and applies measured whole-proof RTT plus the existing remote
margin. Restrictions can only remove support. Native/domain receipt semantics
remain independently validated by the profile.

The owned Reader will mint the nonce and capture send time immediately before
its compact operation. A supplied proof cannot choose its own send time.
Confirmation consumes that nonce on success or failure. Its closed envelope
binds the complete descriptor, SourceBinding, computed SourceTag, request,
challenge, bridge incarnation and owner/bridge clocks. A fresh different tag
revokes all old view refs before returning the target for separate catch-up.
Staging never publishes a ViewRef. Confirmed query refs and iterators retire
on replacement, revoke or disconnect and do not retain an old root graph.

Pending work includes compact native packing, before-allocation accounting of
all staged graph objects, exact private validator accounting, public owned
publisher/Reader IPC and fixed-SSH transport, deadline/cancellation integration,
new schema/lock review, resource/performance gates and installed qualification.
The current lexical input reservation is deliberately conservative and is not
evidence that the 2000-row dense fixture fits the accepted aggregate cap.
