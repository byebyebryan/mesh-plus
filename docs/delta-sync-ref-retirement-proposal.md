# Input retirement query proposal

Status: **docs-only proposal for the existing G1 consuming-ref tracking gap**.
This is not implemented or advertised as a current runtime capability. Exact
Mesh/Observer agreement precedes dependent edits; no general user permission,
A1/R4 reopening, cap change, schema/encoding allocation or rollout is requested.

The [actual completion review](evidence/2026-10-16-delta-sync/completed-relay-review.json)
reproduces the detached-head gap on Observer `2f697d4` and Mesh `f32218b`.
`nbytes` correctly rejects both a retired ref and a ref currently being consumed.
Consequently it cannot tell the source whether dropping its revocation alias is
safe. Inspection prunes a still-consuming head ref; later source close cannot
revoke it. The batch's own child tracking protects new completed batches, but
does not fix detached head refs or the general source registry.

## Exact proposed addition

```text
InputOwner.ref_is_retired(ref: OwnedInputRef) -> bool
RelayInputOwner.ref_is_retired(ref: RelayInputRef) -> bool
```

The owner is the exact minting input owner, including its cache-intake epoch or
relay channel. This synchronous query returns an exact `bool` using only bounded
storage-lifetime metadata. It performs O(1) work without parsing bytes, copying
DTOs, scanning material/rosters, calling profile/codec/domain callbacks, allocating
a new reservation/history entry or reclaiming a graph. It never admits material,
confirms a proof, renews a receipt or changes publication. All existing `nbytes`,
reserve/resize/seal/consume/close checks and errors stay strict and unchanged.

The query remains callable on a closed owner for refs minted by that same owner.
It does not call semantic cache checks or require the owner still to accept new
work. Exact ref type and minting-owner identity protect the query. Role crossing,
foreign-owner refs, raw bytes, DTOs and malformed/uninitialized objects reject
`ProtocolError("sync_input_owner")` without closing anything. For a well-formed
own handle, an extant buffer record must match that handle's identity; absence
of its storage record means retired, without adding historical tracking. This
does not authenticate private-field tampering or attest prior admission; public
mint guards and all actual consumption checks remain unchanged. A valid old
owner's retired ref is still foreign to its replacement or a sibling owner.

| Exact own-ref state | Query | Existing `nbytes` | Credit/authority effect of query |
| --- | --- | --- | --- |
| Available, live scope | `False` | Original length | None |
| Being consumed, not revoked | `False` | Rejects `sync_input_retired` | None; source keeps revocation alias |
| Explicitly closed/revoked during a pin | `True` | Rejects | None; physical pin remains fully charged |
| Consumption finished and buffer retired | `True` | Rejects | None; no retained consumed history |
| Minting owner closed/disconnected/replaced | `True` | Rejects | None; live I/O/pins keep their credit |
| Wrong type, role or minting owner | Error | Unchanged | No close, refund or sibling action |

Unavailable physical storage and semantic authority are separate. `False` is
only a reason to retain the source's revocation alias; it is not permission to
consume, an assertion of material validity/currentness or proof of free capacity.
`True` permits removing that source registry alias, never refunding another
owner's storage, closing a ticket's separate metadata lease or treating data as
admitted. The physical buffer owner and consumer pin keep their existing duties.

## Proposed owning-source adoption

The updated opt-in owned source requires callable `inputs.ref_is_retired` during
`open_session(inputs)`, before reserving source state or beginning I/O. Absence
rejects existing `ContractError("sync_source_input_owner")`; it cannot fall back
to the ambiguous `nbytes` check. The ordinary byte source and legacy APIs are
unchanged. Older source/owner pair evidence retains its original provenance;
this proposal does not claim older owners implement the capability.

The source captures the supported query for that session, checks exact bool
results and prunes only `True`. Non-bool or foreign-ref errors fail the affected
source intake without closing a shared owner or sibling. Available and consuming
refs remain in the existing bounded registry; no new history, cap or allowance is
added. Terminal cleanup drops the captured callback after its own children and
I/O unwind. Batch/control/header metadata still retires only through its own
explicit lifetime. None of these operations closes the shared input owner.

## Required qualification after exact agreement

- Cache and relay owners: available/consuming/revoked/consumed/closed states,
  wrong type/role/owner, replacement epoch, independent aliases/shared ledger,
  repeated close and exact bool/error outcomes. Query leaves all counters and
  publication/material/proof state unchanged and runs no configured callback.
- GC disabled and errors/handles held: explicit revocation retains physical
  raw/receive/output credit until unwind, with immediate weak retirement after
  final owning drops and no consumed-ref registry growth.
- Actual source detached head: inspection during an unrevoked pin retains its
  revocation entry; source close makes pin exit reject, retaining the original
  1,753-byte charge until actual cleanup, with siblings unchanged and final zero.
- Actual source batches/watch/paused delivery, failed writes and repeated
  cancellation: no forgotten live refs, no late success, no cross-scope close or
  double credit. Unsupported owner rejects before allocation/recv/copy/parse.
- Re-run the bounded actual-source relay/Reader and codec integration gates
  against exact committed paired sources. Preserve all original 32/64-MiB,
  two-/15-second, dense/cold/recovery, RSS/native/installed-pair requirements.

The current confirmed defect and this proposed remedy remain distinct. No
implementation, public API freeze or source/route acceptance is asserted here.
