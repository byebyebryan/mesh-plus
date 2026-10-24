# G1 native completion transfer, candidate r1

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **Mesh proposal for one bounded owning review**, not agreed API or
implemented source behavior. This completes the concrete implementation seam
reported in Mesh `m118` and received by RLCD `m119`. It does not reopen the
closed R4 role contract, alter native JSON, allocate an encoding/schema ID or
authorize rollout. Exact Observer and coordinator review precedes dependent
implementation.

The current supported `SourceSession.changes()` returns transaction refs after
checking native completion and closing its control ticket. R4 requires verbatim
native control forwarding. Returning only the tuple cannot transfer the exact
completion bytes or its independently retained metadata. Generic code must not
fabricate them or inspect source-private state.

## Proposed additive public surface

Keep the existing `changes()` signature, tuple/control result and behavior.
Add a method used explicitly by the transport relay:

```text
SourceSession.changes_with_completion(
    base, *, target, max_transactions=4, max_bytes=8388608
) -> awaitable[CompletedChanges[RefT] | SyncControl[RefT]]

CompletedChanges.transactions: tuple[RefT, ...]
CompletedChanges.completion: SyncControl[RefT]
CompletedChanges.close() -> None
```

Constructors remain source-private. The source opens no additional session,
collects no state and owns all construction under the existing public input
owner. It returns a complete batch only after the existing native completion
checks. A failed chain/recovery result returns its exact existing control ticket;
it is never represented as a completed empty tuple.

The completed batch has at most four transaction refs and their exact sum is
at most `max_bytes <= 8 MiB`. Its separate native completion control is at most
65,536 bytes, with `status == complete`, exact target tag and last result cursor.
Its complete nested Mesh control, including envelope and LF, must also fit the
existing 65,536-byte bound; a native maximum cannot override that outer limit.
This separates the already bounded control from the existing transaction sum;
all control, container, header, request, raw/copy/pin and parser storage still
counts in the unchanged shared 64/32 MiB ledgers and total wire/CPU evidence.
There is no new allowance. A zero-transaction batch is allowed only when base
equals target, with completion naming that same tag/cursor.

The batch has its own prepaid bounded metadata/container lease. Its completion
is a normal independently leased `SyncControl` with opaque `.data`, `.status`,
`.reason`, `.tag`, `.cursor`, and idempotent `.close()`. Consuming a transaction
or completion ref cannot refund any still-live batch/control/header metadata.
Batch close first drops its metadata aliases, closes every still-owned data ref
and the completion ticket, then retires its own container lease. It never closes
the input owner, source session, source, ledger or siblings. Repeated close is
safe; source/session retirement revokes this scope before awaiting cleanup.
After retirement, both public batch properties reject; retained storage/leases
remain charged through any active cleanup pins and never authorize late output.

## Generic ownership and output

The selected relay route requires this method explicitly; missing support fails
setup. There is no fallback to `changes()` with inferred completion. Existing
material-cache acquisition using `changes()` remains unchanged.

Before content checking, generic code verifies the bounded public batch shape
and transfers all supplied transaction and completion refs. Malformed/oversized
DTOs do not transfer and require session cleanup. Foreign handles never refund
other sibling storage. A transferred batch owns all refs even when the first
one fails scanning; error/cancel closes every transferred ref and DTO lease.

Pin and structurally scan the entire chain and completion before emitting a
prefix. Check base/result adjacency, native binding and cursor owner/generation,
the exact requested target, and the completion ticket's metadata against its
scanned native bytes. The completion must name the same final tag/cursor and
`complete` status. A wrong, missing, duplicate, foreign or malformed completion
fails the whole preflight. This is structural verification, with all ordinary
Reader semantic/schema/token/root checks still independent.

After successful preflight, send each native transaction verbatim and drain it,
then send the original completion control verbatim with the next ordinary
delivery sequence. Keep all physical pins/copies and separately owned metadata
charged until their actual retirement. Completion cannot precede a material
drain or survive scope retirement. Acquisition/proof deadlines, head-only
behavior and the one moved-head retry remain unchanged.

Source implementation may share its private acquisition code with ordinary
`changes()` while preserving that method's public behavior. It must retain the
exact completed-result/cancellation cleanup guarantees from `f14fb67` and later
watch/session fixes. No Mesh imports, private generic helpers, authority memo or
callback admission capability is introduced in the source.

## Required joined cases before implementation acceptance

Qualify unchanged/zero, one and four transaction completion; early recovery
control; wrong final tag/cursor/status; missing/duplicate/foreign completion;
truncated/duplicate header; exceeded transaction and separate control bounds;
at-limit reservation before container/copy allocation; close/cancellation during
source completion, preflight, material drain and completion drain; late result
after close and repeated cancellation with GC disabled/saved errors; sibling
isolation and no changes to ordinary `changes()`. Include all intake/control
storage in peaks and every transaction/control/fallback byte in matched totals.

This proposal does not define the generic hello/setup/operation-request
dispatcher. That separate controller grammar still needs exact negotiated
identifiers/vectors and cannot be inferred from local Python method names.
