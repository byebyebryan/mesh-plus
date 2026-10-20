# View change feed: conservative Mesh-owned design

Status: design draft R1, 2026-10-19. This captures Bryan's requested design
review before implementation. The decisions below are proposed behavior, not
an accepted wire, SDK extension or implementation release. Names in examples
are illustrative; no protocol/profile IDs or schema/encoding versions are
allocated.

The retained [delta-sync implementation remains dark](delta-sync-dark-status.md).
This is a separate design for complete published views, whole-record changes
and ordinary reconstruction. It does not resume that implementation, change
the [state freeze](contract-freeze.md) or modify `contracts/LOCK.json`. Existing
routes, proofs, packaged schemas and installed selections stay independent.

## Purpose and decision

A publisher continues supplying a complete view. Mesh can deliver that view
as a complete replacement or as changes relative to an exact previous view.
Applications may process change batches, read a reconstructed view through the
Mesh SDK, or do both. In the first version, both APIs use the SDK's internally
retained, independently validated baseline.

Mesh owns identity matching, default comparison, change calculation, batch
validation, ordering, reconstruction and recovery. The publisher owns record
meaning, selection, identity semantics, coverage and original evidence.

Start with whole-record replacement and removal. Do not introduce field-level
patches, observation factoring, per-field tokens, incremental semantic indexes,
Merkle trees or an occurrence journal. Full native/domain validation remains.
The initial objective is useful state-change delivery and lower transport bytes;
sublinear admission or reconstruction CPU is not promised.

## Inputs and relationship to existing work

The design review inspected these source revisions; they are context, not a
new qualified artifact tuple:

| Input | Revision | Relevant boundary |
| --- | --- | --- |
| Retained Mesh checkout | `bea028964f5c1f89c6527fcd9f04e4d634c00d7b` | Dark delta status and frozen state-only routes |
| Mesh working-set source | `2fb502da35c0ef9865762c4dc4b486dd30b7e316` | SDK 1 profile identity, lossless decomposition and current publisher/proof behavior |
| Observer working-set source | `58b90e1a4a6b57e2c07d10856206908d2619af5b` | Complete active-plus-recent view and frame-local support metadata |

The existing [SDK 1](sdk-api.md) exposes `record_identity(record)` and
`NativeState(owner, records, clock, publisher, emitted_ms, receipts)`, plus
`restore_native(owner, records)`. Reuse those supported concepts. A separate
explicit capability and reviewed interface/wire addition would be needed for
this feed; extra fields must not silently activate it. The
[cached publisher interface](publisher-api.md) remains supported unchanged.

The prior proposal aimed to make source storage, admission, roots and repeated
reads incremental. Its CPU/capacity failures are retained in the dark-status
record. This proposal deliberately accepts full-view scans and full validation.
It must earn its value against today's smaller complete replacements rather
than inherit performance claims from that earlier effort.

## What a change means

The feed reports differences between accepted published states. It does not
observe every native transition or establish native causality. Several Codex
changes between observations may appear as one resulting record replacement.
It is distinct from the deferred [native event product](event-delivery.md).

An upsert contains the complete new published record. A removal means only
that its key is absent from this target view. A session leaving a time window
is not necessarily deleted or stopped. Omitted records under partial or failed
evidence do not acquire negative domain meaning.

Representation and evidence completeness are separate. If the publisher emits
a whole replacement whose coverage is partial, reconstruct that exact partial
view. Do not merge old positive rows into it. Uncertainty, nonmembers and
coverage remain in the publisher's current metadata. A malformed or incomplete
transport message is rejected rather than treated as a partial publication.

Local expiry does not manufacture a source revision. A direct subscriber must
respect original evidence deadlines even if no new batch arrives. A prepared
domain facade may reevaluate currentness using its existing rules; the raw feed
does not promise a timer event for every expired field or every consumer filter.

## Ownership

| Responsibility | Owner |
| --- | --- |
| Collection, selection, scope, record meaning and evidence | Publisher and its supported pure domain profile |
| Stable record identity | Existing profile `record_identity`; Mesh checks exact keys and uniqueness |
| Optional cached change indicator | Trusted installed publisher/profile code under an explicit opt-in contract |
| Default fingerprint, diff and independently checked target | Mesh |
| Feed binding, material revisions, ordered delivery and reset | Mesh |
| Applying a batch and reconstructing native state | One Mesh SDK implementation, usable on server or client |
| Domain presentation, actions and retained notification history | Consumer/domain facade |

Mesh owning reconstruction does not require a server-side broker. An application
using only the change API need not maintain its own full map, but the first
version's receiving SDK does retain a baseline and independently admit each
target before invoking the application. Its memory/CPU belongs in the budget.
The producer-side engine also owns enough state to verify each transition.
Do not build separate server and client merge algorithms.

A genuinely stateless wire consumer cannot perform the existing complete native
admission or independently verify a whole-target digest. Authentication alone
does not fill that gap. A separate notification-only/trust contract would be
needed for that mode; it is deferred rather than silently advertised as having
the same guarantees. The phrase event-only below means the application's API,
not absence of an SDK baseline.

Publisher-supplied deltas are a possible later optimization of upstream delivery,
not required publisher work in this version. They would need a reviewed input
contract with the same transition, target-verification and recovery semantics;
they must not become a second merge implementation or bypass full admission.

## Identity, binding and revisions

Use the full typed profile identity, not a display name, list position, object
identity or a string made by joining key components. Reject duplicate keys and
invalid key components, including booleans where integer components are allowed.
Use the existing profile's identity/birth rules; no generic birth inference is
added. If a profile needs two incarnations distinguished, its identity must do so.

A base is usable only under the exact feed binding: configured host and source,
profile/contract identity, native selector including window, publisher/native
incarnation and owning clock context. Transport stream incarnation and material
revision are separate from native observation counters and source chronology.
No cross-host, cross-home, cross-selector or cross-profile base reuse is allowed.

Mesh material revisions advance for committed publication changes, including
metadata-only changes. They do not substitute for native `viewRevision`, proof
nonces or Delivery sequences. A transport reconnect starts a new stream and
baseline. It must not erase native continuity or clock-regression watermarks
that remain applicable within the same native incarnation.

Source loss, a native continuity barrier, changed binding or a lost stream base
requires a reset. Equal record bytes do not waive that requirement.

## Record comparison

The safe default is a Mesh-owned fingerprint over the complete canonical JSON
record. Use the defined Mesh canonical JSON/digest behavior, preserving array
order, optional-key presence and JSON scalar types. Do not normalize strings,
discard timestamps or exclude changing fields as a generic optimization.
Comparison sees privately owned or pinned immutable data, not mutable caller
objects that can change after hashing.

An optional publisher change token may be a cached content fingerprint or a
scoped revision. Its exact callback, token type/size and token-scheme binding
need a later supported API proposal. It must satisfy this promise within its
scope: equal tokens imply equal complete published record content. Different
tokens may cause a redundant upsert; equal tokens hiding a change are a defect.
Do not add an arbitrary old/new comparator callback in the initial interface.

Tokens are local optimization inputs, not wire authority. A token may avoid an
individual comparison, but cannot bypass complete target verification. Mesh
must establish the expected target from the admitted incoming view independently
of token-directed reuse. A lying/stale token must fail before any batch is
published, including to an application using only the change API. Receiver
verification is an additional boundary, not a substitute for a correct
publisher-side transition.

On a local optimization mismatch, discard the proposed batch, retire its
scratch and disable that optimization for the feed incarnation. An independently
admitted complete replacement may be published if it fits existing budgets.
Never retry indefinitely or commit a target digest computed only from the
incorrectly reused baseline. Callback errors cannot mutate the accepted base.

This is a correctness-first design. The independent check still costs a full
walk/hash/comparison. Replacing it with a trusted incremental commitment would
be a different design requiring evidence, not an implementation shortcut.

## Logical material and batch shape

The material being reconstructed is the exact native JSON value obtained by
`restore_native(owner, ordered_records)`. JSON whitespace and object-member
serialization order are not native facts; array order, scalar types, nulls and
optional-key presence are preserved. This proposal does not promise preservation
of the original raw text or reuse the old byte-splicing relay contract.

For every target, retain these logical parts:

- The complete `owner`, including service, coverage, sources, receipts and
  frame-local metadata.
- Full records keyed by their exact identities, and their original order.
- A digest of the complete restored target, computed independently from the
  admitted incoming publication using the defined canonical encoding.

Do not split or incrementally merge the owner in the first version. In the
working-set profile it includes membership/uncertainty metadata and support
tables whose integer references are local to that frame. Replace the table
and all its references together. Its complete cost counts even when no row
body changes.

Conceptual message contents, not Python signatures or a frozen wire schema:

| Material message | Contents |
| --- | --- |
| Complete replacement | Feed/stream binding, target revision/digest, complete owner, ordered complete records and bounded reason |
| Change batch | Same binding, exact base revision/digest, target revision/digest, complete owner, full-record upserts, removed keys and optional complete target key order |

If the key order differs, the batch must carry the complete target order. If it
is omitted, the previous order must be exactly correct, which excludes additions,
removals and reorder-only updates. At application, the order must contain every
target key exactly once and no other key. Its bytes, decoded keys and scratch
count toward the same limits; it is not a free side channel.

Upsert keys and removed keys must be unique, disjoint and in the bound scope.
A removed key must exist in the base. No implicit deletion, per-field merge or
order-dependent remove/reinsert interpretation is allowed. A change to a
record's identity is an old-key removal plus a new-key upsert.

Every batch is atomic. Receipt/coverage-only and reorder-only changes are valid
batches with no record upserts. Tokens are not part of the restored native view;
a token-only change need not publish a new view when all native material is equal.

For example, between `[A@1, B@1]` and `[B@2, C@1]`, send an upsert of the
complete B and C records, removal of A, order `[B, C]`, and the complete target
owner. If the next publication only changes receipts, send its owner with empty
upserts/removals and unchanged order. The record bodies do not gain new
observation times merely because they were reused.

## Generation and reconstruction sequence

Publisher-side Mesh processing:

1. Acquire and own one complete incoming publication; run existing source,
   native/profile, scope, chronology and resource admission.
2. Establish the authoritative complete target and its digest independently of
   change tokens. Extract exact identities and order; reject duplicates.
3. Compare with the current committed base and build a bounded provisional batch.
4. Use the common reconstruction logic and verify that applying the batch
   reproduces the independently admitted target exactly, including owner/order.
   Keep existing native round-trip and digest checks; scalar coercion is forbidden.
5. Select a checked batch or complete replacement. Commit publication state and
   revision only after all callbacks/checks succeed. Expose no partial result.
6. Deliver immutable checked material subject to each subscriber's queue bounds.

Receiver-side processing:

1. Validate framing, sizes, binding, stream order and base revision/digest before
   applying a delta. A replacement must be valid for this stream/binding.
2. Build a provisional target without changing the committed baseline. Resolve
   records and exact order; replace the whole owner.
3. Restore native state, verify the independent target digest and run existing
   native/profile, chronology, proof/receipt and currentness gates as applicable.
4. Commit atomically and expose one complete batch/view. Failure rolls back all
   provisional ownership and invalidates the affected stream's authority.

A whole-view digest proves content equality under the authenticated binding,
not source freshness, admission reuse or current authority. The existing
nonce-bound proof must still obtain a new checked cached source reply. No
digest-only proof or new compact head shortcut is introduced here.

An event subscriber receives only committed, checked publication transitions
after its SDK has admitted the target, but must still obey binding, availability
and expiry semantics. It gains no currentness merely from receiving an upsert.
Both application APIs use the same checked reconstruction path before exporting
change batches or current state.

## Subscription, replacement and recovery

Subscription setup captures a committed baseline and installs observation of
later revisions at one synchronization boundary. A concurrent publication must
appear either in the baseline or after it; it must never be missed between
snapshot and subscription. If startup cannot retain that boundary within the
limit, reject/reset rather than silently begin after the gap.

Each stream begins with a complete replacement. Later messages may be deltas
or complete replacements. A complete replacement is a normal encoding choice
when changes/order/metadata make a delta larger or more expensive. It is also
the recovery representation after a new baseline is established.

Both event and view subscribers must handle complete replacement/reset messages.
The change API does not promise exclusively per-row events. Its SDK retains the
baseline for validation, but does not silently diff across a gap and invent the
missed intermediate changes. Applications must rebuild or otherwise handle reset
explicitly. Exactly-once external side effects are not promised by sequencing.

The first version has no durable replay journal or cross-connection resume
cursor. Bounded transport queues and in-process bases are not retained native
history. On EOF, mismatch or gap, revoke current claims and acquire a new
baseline/proof before positives resume. Do not infer that missing transitions
never occurred or silently repair an occurrence log with a snapshot.

Do not coalesce dependent queued deltas silently. A full queue/slow consumer
gets a bounded gap/reset or terminal outcome and recovery, preserving healthy
siblings. Base/digest or malformed-peer failures reject the affected stream;
they cannot be repaired by accepting an unsolicited arbitrary replacement.
Local optimization failures can use the checked replacement path described
above without treating the publisher's valid target as a source failure.

Binding and catalog/route checks, separate control capacity, original absolute
acquisition/proof deadlines and per-stream cancellation remain compulsory.
No new deadline is minted when bytes leave a queue, and a reset cannot erase
still-applicable native scope/clock history.

## Cost and resource ownership

Complete-list input requires O(N) identity/token inspection. Without cached
publisher fingerprints it also requires hashing the record bytes. Reconstruction,
complete target verification and existing full admission remain O(N) work in the
first design. K upserts do not imply O(K) total CPU. Publisher optimization is
possible, but this does not move all performance pressure out of Mesh.

Measure the independent sender verification, receiver verification, full proofs
and all fallback work. Complete proof replies may remain a significant byte
floor even when watch batches shrink. Count native input, Mesh output and
consumer work separately and together; report actual bytes and cadences.

Reuse an immutable checked publication and its diff among subscribers when
that exact input is already shared. Do not create another full baseline per
subscriber unnecessarily. A global broker, cross-process cache or unbounded
publisher history is not a prerequisite; exact sharing topology is an
implementation proposal and must be measured with real subscription paths.

Resource peaks include the old base, incoming target, owner/support metadata,
identity/fingerprint maps, key-order arrays, provisional reconstruction,
serialization, queued outputs, active I/O/copy pins and caller-held failures.
Shared physical allocations are charged once with explicit owners; actual
copies and container capacity are charged separately. Release credit only when
the last physical owner retires. Revocation must precede awaited cleanup, and
held copies/I/O must retain credit until unwind.

Reserve before allocation/copy and fail before mutation at limits. A complete
replacement fallback must fit the same shared resources; no second emergency
allowance or hidden unbounded diff scratch is available. Preserve the original
head/acquisition deadlines and each applicable native, Delivery and negotiated
feature limit. Do not conflate Runtime's encoded budget, process RSS and the
old delta engine's encoded/heap caps. A new path needs an explicit resource
table before implementation; there is no implicit cap increase or waiver of
the prior 32 MiB encoded / 64 MiB heap qualification boundary.

Repeated cancel/close, callback failure, constructor refusal, reentrant close,
concurrent copy/close and late result delivery must retire only owned work.
Snapshots retained by callers, healthy siblings and unrelated publishers must
not be shut down. Cleanup must not rely on cyclic GC or discard held errors
merely to make counters appear zero.

## Validation before adoption

The following are required design/implementation evidence, not results claimed
by this draft:

| Area | Required cases |
| --- | --- |
| Exact state | Empty/nonempty, insert/update/remove, identity rebirth, reorder-only, null versus absent, exact bool/int/float types, Unicode, duplicate keys and duplicate operations |
| Metadata | Zero-upsert receipt/coverage changes, frame-local support-table remap, projection unavailable versus complete empty, partial target removing old positives, quiet cutoff and local expiry |
| Tokens | Default hash path, valid cached tokens, redundant changed token, false unchanged token rejected before any subscriber output, token-scheme/scope change and callback errors |
| Binding/order | Wrong host/home/source/profile/selector, stale incarnation, regressive revision/clock/continuity, wrong base/digest and exact array order |
| Race/recovery | Publish during baseline capture, reconnect, lost batch, dependent-delta coalescing attempt, slow subscriber, bounded full-replacement fallback and fresh proof after recovery |
| Physical lifetime | At-limit preallocation refusal, held baseline/target/output, blocked copy/drain, reentrant/concurrent close, repeated cancellation, retained errors and sibling isolation with GC disabled |
| Cost | Real complete-replacement baseline, compressed replacements as a separate control, hash versus cached-token path, mostly unchanged/all-changed/metadata-heavy input and proof/fallback bytes/CPU |
| Integration | Supported publisher/profile, ordinary Reader and change-only application using the validating SDK, local IPC/fixed SSH, isolated installed package tuple and independent native comparison |

Before product implementation, freeze an independent small reference model and
positive/rejection vectors for the chosen messages and transition rules. The
earlier discussion's in-memory JSON exploration was diagnostic only; it was
not a published protocol oracle or runtime acceptance and is not relabeled here.

Run an early bounded feasibility slice on the current working-set feed before
building general replay or broader native adapters. Compare matched useful
outputs and fresh proofs with today's complete replacements, not the failed
old delta candidate. Include cold start, recovery, shared subscriber pressure,
both supported Python versions and inclusive ownership/physical memory evidence.
Source correctness, installed package, native parity, ordinary authenticated
route selection and consumer/device adoption remain separate gates.

If deltas do not provide worthwhile measured benefit within applicable CPU and
resource ceilings, retain complete replacements. No percentage saving or
2,000-row capacity pass is inferred from this design or from a small model.

## Remaining specification work

The architectural decisions above are the proposed review baseline. Before
implementation, make these items concrete in one additive interface packet:

1. Exact capability negotiation, SDK entry points, message/schema encoding,
   canonical digest/key framing, revision ranges and error/control outcomes.
2. Captured feed binding and selector representation, including how existing
   source/profile chronology survives transport reset.
3. Whether cached publisher tokens are included in the first implementation;
   if included, their public signature, bounded representation, scheme binding,
   failure behavior and ownership. The hash-only path remains sufficient.
4. Numeric input/map/staging/output limits, sharing topology and shutdown bounds
   reconciled with the unchanged applicable resource/deadline contracts.
5. Exact placement of sender verification, receiver admission and fresh full
   proofs in the supported Reader/change APIs, with independently tested
   subscription startup and fallback behavior. Both APIs retain the validating
   SDK baseline; a stateless notification mode is not part of this packet.

These are requests for a precise implementation specification, not another
general permission loop. This draft authorizes no production edits, sibling
changes, ID/schema freeze, artifact release, service selection or rollout.

## Documentation validation

On this retained checkout, `rtk proxy .venv/bin/python scripts/check.py` passed
using Python 3.14.8: 33 locked inputs, 25 identical packaged schemas, 116 design
checks, 169 Delivery checks, 411 core runtime tests with zero skips, and Ruff.
That gate checks the existing implementation and documentation consistency;
it does not implement or qualify this proposed feed. Native/source-parity,
performance, physical resources, wheels, installed pairs and deployment were
not exercised by this documentation task.
