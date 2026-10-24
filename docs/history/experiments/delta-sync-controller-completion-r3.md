# Relay controller completion bounds, revision 3

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **narrow contract clarification pending exact owning agreement**. This
supplement replaces only the `changes` row in the closed-command table of
[controller R2](delta-sync-controller-proposal-r2.md), immutable commit
`33cb57c98ca3062f139ea1fd0c68b15bd5abd8d6`, SHA256
`89b24a9f3191bcded303d33c8b2ed973335b703811185abf1186848fbd562f48`.
The intended exact controller contract is R2 plus this supplement. All other R2
carrier, first-byte provenance, command/result, terminal-receipt, deadline,
watch, source/head/context and lifecycle provisions remain unchanged. R2's
original bytes and independently reviewed arithmetic stay preserved.

The R2 phrase "1..4 transactions ... no extra terminal-control allowance" was
ambiguous about capacity versus result count and transaction versus terminal
bytes. This replacement states the already accepted
[completion transfer R2](delta-sync-completion-transfer-r2.md) bounds explicitly;
it changes no existing source method, native request, result, cap or allowance.

## Replacement command row

| operation | Additional fields | Dispatch and constraints |
| --- | --- | --- |
| `changes` | `acquisition,base,target,maxTransactions,maxBytes` | Exact live capsule; existing completed-changes path, no watch; exact tags. `maxTransactions` is an exact integer capacity in 1..4. A completed result contains 0..`maxTransactions` transactions; zero is valid only when `base == target`. `maxBytes` is an exact integer in 1..8,388,608 and bounds the sum of original transaction-frame bytes only. The separate original terminal control must independently satisfy its existing native-codec bound (Agent <=16,384 bytes) and the whole nested Mesh control <=65,536 bytes including envelope/LF. All transaction/control and ancillary storage/traffic remain charged under the unchanged shared 32 MiB encoded / 64 MiB heap and CPU/wire gates. |

Both capacities are request limits, not promises of a full result. A zero result
does not require or permit `maxTransactions=0` or `maxBytes=0`. Empty success
requires the original self-consistent `complete` control naming the exact same
base/target/tag and valid cursor/epoch/descriptor; missing, partial, mismatched
or recovery evidence cannot become an empty success. The source/relay still
validate the whole transaction chain and exact original completion. Independent
Reader admission and fresh nonce proof remain mandatory for current authority.

The transaction sum counts each original native transaction frame including its
LF. The original native completion frame, including its LF, is separately bounded
by the configured codec. The nested Mesh control's envelope and final transport
LF must independently fit the existing outer limit. Neither representation can
borrow unused bytes from the other bound. The terminal control is not subtracted
from the transaction byte limit and grants no new aggregate storage, traffic,
deadline or CPU allowance. Existing per-frame limits also remain unchanged.

For example, `maxTransactions=4,maxBytes=8388608` can carry four original
transactions whose sum is exactly 8,388,608 bytes plus the separately bounded
original completion, provided every existing chain, frame, resource and deadline
check passes. A transaction sum of 8,388,609 bytes rejects. An Agent native control
of 16,385 bytes rejects even if the outer Mesh control would fit; an outer control
of 65,537 bytes rejects even if its native fragment fits. These examples restate
independent limits and are not capacity or delivery qualification.

A controller `changes` result is `ok` only after every original transaction and
the exact native terminal control drain. A controller result cannot replace that
terminal control. Source recovery retains its existing exact control and
`failed/source` handling. All bytes, containers, headers, raw/DTO/parser/copy/pin
and output work count in the same existing ledgers and complete CPU/wire totals.
The 2-second head-only proof and absolute 15-second acquisition remain unchanged.

## Evidence and review boundary

The [clarification receipt](../../evidence/2026-10-16-delta-sync/controller-r3-review.json)
pins R2, its unchanged R1/R2 oracle/vector tuple, accepted completion transfer,
Observer's owning completion/source documents and the current Mesh inputs. The
existing source's exact 8 MiB transaction-plus-control, zero/one/four, native
16 KiB and outer 64 KiB cases retain their independently reviewed evidence. This
documentation-only correction does not rerun or reattribute those tests or the
unchanged 8,484-byte R2 arithmetic output.

Observer requested this single clarification after finding no other R2
source/head/context/clock/lifetime incompatibility. Exact owning confirmation of
R2 plus this supplement precedes controller/carrier runtime implementation under
the existing G1 authorization; no new general approval or A1/retirement-query
gate is introduced. No runtime, schema/encoding ID, lock, artifact, route,
provider/service, sibling or rollout change belongs to this revision. Original
aggregate resource, dense CPU, deliverable 2,000-row recovery, RSS, populated
native/fixed-SSH and immutable installed-pair gates remain open.
