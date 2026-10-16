# Delta synchronization G0 contract appendix

Proposal, 2026-10-16. This makes the generic choices in
[the Mesh proposal](delta-sync-proposal.md) concrete for Observer/RLCD review.
Names below are proposed field/API names, not allocated wire IDs or an accepted
schema. No runtime capability, lock change or artifact is introduced by this
document. RLCD must record joint G0 closure before implementation.

## Canonical bytes and map commitment

All framing here is exact. `H` is SHA-256 returning 32 raw bytes. `U64(n)` is
eight-byte unsigned big-endian; `U16(n)` is two-byte unsigned big-endian.
`F(b) = U64(len(b)) || b`. A trailing `\0` in a tag is one zero byte, not two
printable characters. Wire digests are 64 lowercase hexadecimal characters;
hash inputs use raw digest bytes unless explicitly placed in canonical JSON.

`C(x)` is UTF-8 JSON with these rules:

- Types are null, boolean, integer, Unicode scalar string, array and string-keyed
  object. No floats, NaN, infinity, bytes or duplicate object keys. Boolean is
  distinct from integer. Integers use minimal base-ten notation; no negative zero.
- Object keys sort by Unicode scalar code point. Arrays preserve order. No
  whitespace occurs between tokens. Strings use literal non-ASCII UTF-8;
  escape quote/backslash and U+0000..U+001F using JSON short escapes where defined
  (`\b`, `\f`, `\n`, `\r`, `\t`), otherwise lowercase `\u00xx`.
  Do not escape slash or other scalars, normalize Unicode, or accept surrogates.
- For this integer-only JSON subset, Python stdlib
  `json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
  allow_nan=False).encode('utf-8')` is the reference after strict type/input
  validation. Optional-key absence and present null remain different values.
- Wire fields have schema-specific bounded lengths/ranges. Generation is
  0..2^64-1; overflow starts a new owner epoch/baseline, never wraps. No new
  restriction is applied retroactively to old schemas.

For space name `S` (UTF-8), canonical key `k` and value `v`:

```text
K(S,k) = H("mesh-sync-key\0" || F(S) || F(C(k)))
V(S,v) = H("mesh-sync-value\0" || F(S) || F(C(v)))
E(S)   = H("mesh-sync-empty\0" || F(S))
L(S,k,v) = H("mesh-sync-leaf\0" || F(S) || K(S,k)
             || F(C(k)) || V(S,v))
```

For one entry the map root is its leaf hash. For more than one, find the
longest common prefix of **all** 256-bit K values at that node. Let its bit
length be `p`, 0..255, counting most-significant bits first. `prefix` is
`ceil(p/8)` bytes, with unused low bits zero. Partition on bit p into nonempty
left (0) and right (1) children and recurse:

```text
B(S,p,prefix,left,right) = H("mesh-sync-branch\0" || F(S) || U16(p)
                           || F(prefix) || left || right)
```

No single-child branches exist. Deletion collapses them; insertion reconstructs
the unique split. At p=0 prefix is empty. Different canonical keys with the same
K are rejected; equal canonical keys are one map key. Duplicate operations or
baseline keys are rejected, not last-write-wins. Shape/root is independent of
insertion order. An update recomputes only its <=256 ancestor path; the first
implementation must not sort/rebuild the entire map on sparse changes.
Cardinality is maintained with each node and checked against the state summary.
Empty map cardinality is zero; nonempty tree has at most 2N-1 nodes.

The native descriptor fixes the exact table registry and value schema. Its
summary `T` is an array of `[spaceName, lowercaseRootHex, cardinality]` sorted
by space name; every declared table occurs, including empty tables. The registry
is bounded, so sorting T is independent of roster N. The root is:

```text
NativeRoot = H("mesh-sync-native\0" || F(C(NativeBinding))
               || U64(generation) || F(C(T)))
SourceRoot = H("mesh-sync-source\0" || F(C(SourceBinding)) || NativeRoot)
```

`NativeBinding` has exact contract/schema digest, native host/UID, view/selector,
owner incarnation, boot/time context and projection continuity. Their concrete
native field names belong to Observer's reviewed new descriptor. No Mesh alias,
Mesh import or Mesh profile is required by the engine/service.
`SourceBinding` has exact configured authenticated host, source alias, sync
profile ID/schema digest and expected native descriptor digest. Mesh independently
checks/recomputes the wrapper. Route/catalog/ordered-host/channel/reader epochs
belong to acquisition/proof binding, not per-alias native rosters.

NativeTag is `(nativeBindingDigest, generation, NativeRoot)`; SourceTag adds
`sourceBindingDigest, SourceRoot`. Binding digests are
H(`"mesh-sync-native-binding\0" || F(C(NativeBinding))`) and
H(`"mesh-sync-source-binding\0" || F(C(SourceBinding))`), respectively;
roots above still hash the complete binding.
Changing a binding requires a new epoch/baseline. Generations and roots both
must match; equal body bytes or equal roots in another binding cannot be reused
as an authority token. A received expected root is never the computed root.
The native cursor is the deterministic tuple `(ownerEpoch,generation,NativeRoot)`,
not an independent sequence or opaque owner counter. NativeRoot already commits
all its components, so SourceRoot above binds the cursor without a per-alias
roster hash. Subscription/channel sequence remains separate proof/delivery data.

## Typed state and compact membership encoding

Adopt this eight-table registry for the first Agent sync descriptors; fixed
full/active descriptors define different scope schemas, not different root math.
Keys below are logical keys, independently reconstructed at each boundary.
Tuple notation means a JSON array. Identity order is exactly
`[host,provider,namespace,nativeKind,nativeId]`. Birth is
`[ownerEpoch,creationGeneration]`, referring to accepted sampled-state removal
and reinsertion, not an unobserved provider lifecycle between samples.

| Space | Logical key and value |
| --- | --- |
| `records` | Full five-part identity -> birth `(owner epoch, creation generation)`, body ID, order key, scope ref |
| `bodies` | Body ID -> exact stable content; only bodies referenced by current slots are logical state |
| `observations` | `(identity,birth)` -> typed moved observation paths with exact optional/null preservation and support refs |
| `memberships` | `(cohort ID,identity,birth,field name)` -> locally derived validated field-content token |
| `receipts` | Original bounded receipt key -> exact original FactSupport tuple/context |
| `cohorts` | Stable logical cohort ID -> producing receipt ref, immutable seal version/root/count and original support head |
| `scopes` | Typed scope/fact key -> one coverage/continuity/member/uncertain/nonmember authority fact; roster-sized lists are flattened into per-identity entries |
| `metadata` | Bounded native metadata key -> exact committed collection/publication anchors, counters, diagnostics and ordered arrays |

Bodies use `H("mesh-sync-body\0" || F(nativeDescriptorDigestBytes) || F(C(content)))`.
Field tokens use `H("mesh-sync-field\0" || F(nativeDescriptorDigestBytes)
|| F(C(identity)) || F(C(birth)) || F(UTF8(fieldName)) || F(C(fieldValue)))`.
Observer's exact nine field-value extractions and lossless observation-path
table are accepted as proposed. A title change cannot renew or invalidate an
unrelated runtime token. Birth is cache instance identity, not a new assertion
about native session lifecycle.

Each cohort's seal is a second Patricia map using space name `cohort-members`:
key `(identity,birth,field name)` -> token. Its count and root are in `cohorts`.
Generic code maintains this grouped membership index incrementally alongside
the global membership table. It does not enumerate members to renew a head.
Logical cohort ID is stable within its native receipt-key/context/owner scope.
It is the namespace used in membership keys, not a content-addressed set ID.
Changing one binding updates only that binding's map paths and the cohort head.
It creates a new immutable seal version `(generation,memberRoot,count)` under
the same logical ID; it does not rekey unchanged members. Earlier seals remain
immutable under current/predecessor root retention. A support renewal names the
exact committed seal version; an old version cannot inherit a newer head.
G1 must demonstrate sparse changed-key/visit counts for one-member changes,
not merely equal roots. Current cohort heads remain bounded by the receipt map.
Context-only former bindings live with bounded original observation context,
not a growing bank of current cohorts or historical receipts.
Body reference counts, identity uniqueness, order and reverse dependencies are
maintained indexes. Last-reference removal deterministically removes the body
from logical state; physically retained deduplicated bytes remain budgeted and
grant no authority. Extra unreferenced baseline bodies are rejected.

Wire record references are epoch/birth-bound aliases declared by admitted slots;
they expand losslessly to identity/birth. Membership changes group one record
ref plus a nine-bit mask, using this fixed bit order:
`runtime, phase, kind, savedIdentity, activity, outcome, workspace, lastUpdated,
latestTurn`. Tokens need not be sent for each cell. The strict profile normalizer
derives them from validated content and expands only changed cells before the
generic locally computed commitment. Neither a peer-supplied token nor mask
alone establishes support. The membership expansion contract is part of the
native descriptor and must have independent join/token vectors at G1 freeze.

Subset reobservation removes/reattributes missing cells before renewing its new
sealed set in the same transaction. Retained old cells keep their original
refs/context and cannot inherit the new receipt. Renewing an existing seal is
allowed only by the explicit actual-reobservation predicate in the owning
proposal, not by receipt-key equality. True N distinct moved timestamps remain
N facet updates; no common batch clock is inferred.

## Messages, barriers and transport binding

JSON messages have a closed category plus exact negotiated descriptor and
request binding. Unknown fields/categories, conflicting duplicate operations,
unknown refs and out-of-range values fail admission. Concrete wire IDs remain
unallocated; these are structural names for review.

`SyncDescriptor` is immutable data: sync-interface revision, sync protocol/contract
digest, commitment algorithm revision, profile ID/schema digest, native contract/
schema digest, exact table registry, declared index schemas and full/active
view/selector. Both endpoints compare the complete expected descriptor/digest
and required baseline/transaction/head feature set during explicit sync setup.
Request setup fixes configured source and request/channel epochs plus limits
no larger than either endpoint's hard caps. A mismatch returns unsupported;
there is no retry as old Delivery 1 or a legacy full profile. Wire descriptors
cannot choose modules, factory imports, executable paths or SSH commands.
Factory injection is trusted local configuration, as with the old SDK, but the
new factory must explicitly return a sync publisher/reader, not an SDK 1 adapter.

```text
Baseline {descriptor, nativeBinding, tag, cursor, tables}
Transaction {descriptor, nativeBindingDigest, transactionId,
             baseTag, resultTag, baseCursor, resultCursor, operations}
Head {descriptor, nativeBindingDigest, tag, challenge, ownerClock,
      originalReceipts, cohortHeads, attenuation}
SourceEnvelope {sourceBinding, nativeMessage, sourceTag, requestBinding}
Control {requestBinding, status, reason, currentTag?}
```

`tables` contains every declared table; baseline O(N) normalization is explicit.
`operations` contains typed put/remove groups per space and compact memberships.
A put is `(key, expectedOldValueHash|null, newValue)`; remove is
`(key, expectedOldValueHash)`. Null means exact absence. Value hashes are V above;
wrong expected value fails. Each key has at most one operation. Bodies are sent
once on insertion; unchanged admitted bytes are referred to, not resent.
`transactionId` commits exact canonical transaction bytes excluding that field:
H(`"mesh-sync-transaction\0" || F(C(transaction_without_id))`). Recognition of
an exact duplicate is bounded to retained transaction tokens and never renews
authority. Composed transactions must account for the entire contiguous base
to result chain; no omitted delta is relabeled as baseline/resync.

The local source's `baseline()` atomically captures the committed tag and watch
cursor under its existing publication barrier. `watch(cursor)` starts strictly
after that cursor or returns explicit baseline-required if the bounded journal
cannot bridge it. `changes(base,target)` returns the exact bounded contiguous
chain, never a later mutable head. Cursor and generation are distinct: the
cursor is owner-incarnation plus generation/root, subscription sequence is a
separate transport field. No durable history or cross-connection resume is
promised. An owner generation is encoded/diffed once and shared.

`head_after_nonce` is a fresh live service operation after challenge admission;
it captures the then-current head without frame()/active_frame(), full export,
expire/publish or native collection. It may attenuate original leases using the
actual clock; material failures/context/health changes require a new commit.
Reserve at most 49,152 bytes for the native head and 16,384 for its Mesh
source/proof/delivery envelope; their complete encoded sum is <=65,536 bytes.
The 8 KiB fixed native budget plus 32*768 receipt bytes plus 32*384 cohort-head
bytes is 45,056, leaving 4 KiB native slack before the envelope reserve.
Entry/fixed caps include their JSON punctuation, not just leaf string values.
Entry/fixed caps are
enforced, not truncated; a 32-receipt/cohort encoded boundary vector is a G1
freeze gate. The <=8 KiB measured target is the <=4-receipt case.

Proof carries no body/transaction chain. If its fresh tag differs from the
requested admitted tag, return `moved`, revoke that host's authority, catch up
separately (<=4 transactions/8 MiB), then obtain a fresh nonce proof. At most one
such retry fits the original 15-second acquisition budget. The two-second proof
budget includes queue/transport/native head/check/RTT work and old margin rules.
Further movement, eviction or exhaustion gets explicit sync baseline recovery
or failure within the original budget. No old-tag proof or legacy fallback.

Use a distinct negotiated sync delivery contract/profile with explicit trusted
full-sync/active-sync factories. Reuse existing authenticated IPC/SSH framing,
connection lifetime and credit primitives. Do not broaden Delivery 1 capability
enums or promote its reserved digest-proof/replay/events syntax. Old Client,
Bridge and publisher replacement behavior remains on its old routes. New
SyncBridge preserves a complete chain or signals gap/baseline. An unsupported
new route fails explicitly. WSS is independently qualified if exposed.

## Public immutable staging and query API

These signatures are the proposed sync interface, separate from SDK 1. Inputs
cross an ownership boundary as immutable bytes or cache-minted capability refs.
No mutable caller dict is retained. `FrozenValue` below is immutable JSON data;
refs are revocable cache lookups, not owning graph pointers.

```text
CachedSyncSource.baseline() -> BaselineTicket[bytes, NativeTag, Cursor]
CachedSyncSource.changes(base: NativeTag, *, target: NativeTag,
                         limits: CatchupLimits) -> tuple[bytes, ...] | ResyncRequired
CachedSyncSource.watch(cursor: Cursor) -> AsyncIterator[bytes | SyncControl]
CachedSyncSource.head_after_nonce(challenge: HeadChallenge) -> bytes

create_sync_publisher(source: CachedSyncSource, profile: SyncProfile,
                      source_binding: SourceBinding, budgets: SyncBudgets) -> SyncPublisher
create_sync_reader(config: SyncConfig, profile: SyncProfile) -> SyncReader

SyncProfile.descriptor: SyncDescriptor
SyncProfile.admit_baseline(ctx: PublicStageContext) -> DomainIndexPatch
SyncProfile.stage_delta(ctx: PublicStageContext) -> DomainIndexPatch
SyncProfile.check_head(ctx: PublicCommitContext, head: FrozenValue) -> HeadRules
SyncProfile.export_committed(view: ViewRef) -> detached domain DTO

OwnedSyncCache(profile, source_binding, budgets)
OwnedSyncCache.admit_baseline(raw: bytes | OwnedInputRef) -> CandidateRef
OwnedSyncCache.stage(raw: bytes | OwnedInputRef) -> CandidateRef
OwnedSyncCache.stage_batch(base: SourceTag, frames: tuple[bytes, ...]) -> CandidateRef
OwnedSyncCache.confirm(candidate: CandidateRef, proof: bytes,
                       clock: ReaderClock) -> AdmittedCommit
OwnedSyncCache.acquire() -> ViewRef
OwnedSyncCache.revoke(reason: SyncReason) -> None
OwnedSyncCache.disconnect() -> None

SyncReader.updates(request: SyncRequest) -> AsyncIterator[AggregateCommit | SyncControl]
AggregateCommit.hosts() -> ordered bounded host statuses/tags
AggregateCommit.host(host: str) -> ViewRef | UnavailableHost

ViewRef.tag: SourceTag
ViewRef.changes(since: SourceTag) -> ChangeSet | ResyncRequired
ViewRef.lookup(space: str, key: FrozenValue) -> FrozenValue | ABSENT
ViewRef.index(name: str) -> PublicIndexRef
ViewRef.context(now_ms: int, clock: ReaderClock) -> bounded detached header
ViewRef.export_committed() -> explicit O(N) detached domain DTO
```

CandidateRef is minted by one cache and tied to profile/callback identities,
source/owner/request epochs and staged root. It cannot be used in another cache,
after disconnect, or after eviction. `confirm` independently verifies roots,
request, nonce, source/native binding, live-owner proof, original receipts and
RTT, calls bounded `check_head`, then atomically publishes. HeadRules can only
restrict generic authority; it cannot relax a failed root/proof/clock check.
There is no public `mark_admitted(dict)` or public callback commit operation.
OwnedInputRef reuse is local, exact profile/callback/epoch-bound and revocable;
transmission always requires independent receiving-process admission.

PublicStageContext has the following supported immutable interface:

```text
ctx.descriptor, ctx.binding, ctx.base_tag, ctx.proposed_tag
ctx.before: PublicStateRef                 # empty on baseline
ctx.after: PublicStateRef                  # provisional state; no authority
ctx.operations: tuple[TypedOperation, ...]
ctx.changed(space) -> bounded iterator[TypedOperation]
ctx.index(name) -> immutable base PublicIndexRef
ctx.field_token(record_ref, field) -> admitted token | ABSENT
ctx.cohort_members(cohort) -> metered lazy iterator[BindingCell]
ctx.dependents(dependency) -> metered lazy iterator[DependencyEdge]
ctx.scope(scope_key) -> immutable typed scope | ABSENT
ctx.budget: BudgetRef                      # reserve/charge, no limit override
ctx.visits: VisitMeter                     # lookups/iterations/derived updates

DomainIndexPatch(
    writes: tuple[IndexWrite, ...], removes: tuple[IndexRemove, ...],
    field_tokens: tuple[FieldTokenWrite, ...],
    membership_expansion: tuple[DerivedMembershipOperation, ...],
    changed_rules: tuple[RuleWrite, ...], removed_rules: tuple[RuleKey, ...],
    affected_scopes: tuple[ScopeKey, ...], invalidations: tuple[Invalidation, ...])

PublicIndexRef.get(key) -> FrozenValue | ABSENT
PublicIndexRef.iter_keys(prefix=None) -> metered lazy iterator[FrozenValue]
PublicCommitContext.view, descriptor, binding, tag, original_receipts, budget
```

Index names/key/value shapes are declared in the exact profile descriptor;
duplicate writes/removes or undeclared indexes fail. Index patches are data,
not closures, Python objects holding arbitrary graphs or direct pointers into
profile-owned mutable dictionaries. Generic code freezes, checks and charges
them before committing. Domain-derived membership operations must correspond
exactly to the changed wire masks/refs; newly computed field tokens use the
descriptor's reviewed extraction. Final native map/cohort roots are then
computed locally. A callback cannot supply an unchecked root or commit early.
Validation failure/cancellation discards all provisional state and index writes.

The before/after/index refs look through revocable capabilities. Keeping one
outside a callback does not pin its graph; access after retirement fails.
Current/predecessor roots plus one staged candidate are the only decoded
generations. Descriptor/callback replacement revokes the instance. Iterators
check retirement and charge each visit; no implicit list of N members in a
header. Baseline builds all indexes once. A sparse change updates only affected
identity/body/token/scope/dependency paths; a cohort head-only update does not
reclassify every member. Profiles must name and count any unavoidable O(N)
invariant before acceptance, not hide full restore/validation in this interface.

The pure Observer facade uses these public indexes for exact clock/current-field,
membership/uncertainty and changed-output queries. It may return detached R rows
at O(R). Explicit full exports are O(N), preserve exact committed API 4/native
values and order, and grant no query-time currentness. `context` is O(P+selected
hosts) and contains bounded status/roots, with no nested roster or N-scope list.
Scope enumeration is an explicit metered query. A body lookup alone never says current.
Expired D outputs cost O(D) when those output changes are requested and counted.

Each baseline/delta/confirmation is atomic **per host/native source view**.
There is no cross-host or full+active pair transaction. AggregateCommit fixes
catalog revision, ordered host selection, routes and channel/reader epoch, and
exposes exact per-host confirmed tags/status. Moved/failed host authority is
revoked immediately; other hosts retain only their own checked original leases.
A candidate host never appears as confirmed. No per-read aggregate roster copy
or full aggregate hash is part of this handle.

## Initial arithmetic vectors

These were calculated with stdlib SHA-256 for documentation only. Independent
Observer reproduction is still required; they are not an implementation test or
runtime acceptance. The primitive fixture has S=`records`, k=`"a"`, v=`{"body":"A"}`
and k=`"b"`, v=`{"body":"B"}`. Primitive keys need not be valid Agent identities.

```text
empty        eeb50b54d1d8075c3a13e3c3d8fbe7c51995bad9129f80e4de7e1b6ce3d6c587
K(a)         ce82c5b724b7c17d4d8ceb7c1b6e5c50115c60572ae3a6863eb2466a3a2e0c9c
K(b)         13d1c83070beb5be53fc138e46af5044b5968fcd458a302c42aaf6eeeeab31cd
L(a,A)       e6656cee7d68057ea405fe79d91dfca8d73242361a402ce86c7ec8df3fb895ac
L(b,B)       ba716d28870d9878937cb24f5b2f1bf6a946c1f01018b87eb7fcfad4b70588b3
root(a,b)    d9d6043d34003e0962032d529fd5ee197a02fe7818b7e91f01563826c914034f
root(b,a)    d9d6043d34003e0962032d529fd5ee197a02fe7818b7e91f01563826c914034f
replace a:A2 60c4c18888def3635a595751bf82e9160a019f4a7ce19a620a5c2b5f60f40419
delete b     e6656cee7d68057ea405fe79d91dfca8d73242361a402ce86c7ec8df3fb895ac
```

The two-key split is p=0, empty prefix, left=b, right=a. Native fixture binding
is `{"contract":"fixture","host":"h","owner":"o","view":"full"}`,
generation=2, T=`[["records",root(a,b),2]]` (root represented as its hex string).
Source binding is `{"host":"h","profile":"proposal","source":"s"}`.
These reduced bindings are arithmetic fixtures, not valid production descriptors.

```text
NativeRoot   5b7ca726bb1e93e425752f9d2c742c80131b1fab11fb57f8940c815b84f3eb0f
owner=o2     e3f480295ecf19e68520ffbdd1e3f937c6cac9c0d0eeb88f9df26f164f81954d
SourceRoot   8ad9669a41a79d9df2d397a1233418ac739bd5d8d8a3b83ae1393e68b863882a
source=s2    71dfd4b47c9316613ab4f5d5fda282fb939bfdd96a85bf3de3f238b368d80d77
```

Non-byte-aligned branch fixture: keep a/A, replace b/B with c/C. The split is
p=2, prefix byte `c0`; all six unused low bits must be zero. Root is
`28143b1ae65c68223f645cb7d988eb6b1e79fba5d9e9705055a3908e190ff560`.
For canonical JSON, `{"z":null,"é":"é\n","a":true}` has C bytes
`7b2261223a747275652c227a223a6e756c6c2c22c3a9223a22c3a95c6e227d`.

Add table `receipts` with key `"r"` and value `{"accepted":1}` or
`{"accepted":2}` to the same T, sorted, keeping the records root/generation
unchanged. It must change the native root without touching record leaves:

```text
receipt1 map 3ef6dffb3d5d4fa791ad6e1c04553d1e9d0233e155d3a41aae2f6ebbcd0d1aee
receipt2 map bd2704bfd2239abdb8903145e17879db02e29e4fc00131b45123b422795a4235
receipt1 all 2485b2dceba1daadcc49da715c99346ebd6466083dbe0603dde3e2b7edc6f43a
receipt2 all 2e3531e0db82dc02bb9ef0e34d020c8b91b0a7f07c4df6f387686efb6b8d0642
```

Cohort primitive fixture: S=`cohort-members`, identity=
`["h","codex","ns","thread","id"]`, birth=`["o",1]`, field=`"runtime"`,
value=the string `11` repeated 32 times. Key is `[identity,birth,"runtime"]`.
Its singleton root is
`f7e17cab2df897006e1a7d89363c6b433c29f81273619eb0e8b729440df2e814`.
Changing only birth to `["o",2]` gives
`e11a69eecb1dbba9d8bec87ff55c5562a0cb579c3259ab306fd03e9c8ab95941`.
A receipt-only renewal keeps this member root; it changes receipt/cohort-head
and native roots. This synthetic token is a commitment arithmetic fixture;
it does not assert a valid Agent field observation.

Wrong expected root, wrong count/table registry, changed owner/source binding,
ambiguous/duplicate JSON keys, wrong prefix padding, duplicate operations and
reusing an old birth-bound cohort after remove/reinsert are rejection vectors.
At G1 freeze, promote agreed vectors as new reviewed immutable contract inputs,
add exact field join/token/cohort renewal, changed
generation, head maximum and transaction examples, and independently execute
them in both owners. Do not edit an old accepted schema or regenerate old lock
digests. Joint review of this appendix remains required before runtime edits.
