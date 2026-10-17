# Native completion transfer: owning reconciliation r2

Mesh accepts Observer's exact method/result/lifetime review at
`132c0f109784ac849fa1d03d254118669224485a`,
`docs/delta-sync-completion-transfer-r1-review.md`, SHA256
`bdd6e13402c44a6c5c58051ecf12a92658230138adec40a25f317f6166733d93`.
Its sole requested bound clarification is adopted below. This records Mesh's
owning agreement for the additive source seam inside the authorized G1 work;
it creates no general permission wait and reopens neither A1/R4 nor compact R2.
Implementation and qualification remain separate from this agreement.

The [original Mesh packet](delta-sync-completion-transfer-r1.md) stays immutable
at `0b942c25fd3c74e16f11398170f28efac2f13138`, SHA256
`740dd8bc5b3c435612194c6451b5fb545d54bd0e3b8115f6934ff29a5686eff0`.
Observer's original proposal is `8f54fd0c3d743ac410776a70c6b01ef2f9620a90`,
SHA256 `32ff86a3a1e4f65d3b070dc57206da6b8bdc2c79c4ca5b40f8cdc38a471f93f1`.
Together with the specific replacement below, the original Mesh packet fixes
the supported return surface, ownership, preflight, failure and cleanup rules.
No other r1 behavior changes.

```text
SourceSession.changes_with_completion(
    base, *, target, max_transactions=4, max_bytes=8388608
) -> awaitable[CompletedChanges[RefT] | SyncControl[RefT]]

CompletedChanges.transactions: tuple[RefT, ...]
CompletedChanges.completion: SyncControl[RefT]
CompletedChanges.close() -> None
```

`CompletedChanges` is the single source-owned result name; no second alias is
needed. Its public properties reject after scoped retirement. Transactions,
completion data, control/header metadata and batch/container metadata have their
respective prepaid lifetimes. Consumption of a ref does not refund independent
metadata. Closing the batch closes only its own still-owned refs, completion and
lease; it never closes a shared input owner, ledger, sibling or native provider.
The completed-result/cancel-before-delivery and revoke-before-await rules remain
mandatory. Legacy `changes()` retains its transaction-only tuple/control shape.

## Exact replacement for the native-control bound

The r1 sentence stating a separate native completion limit of 65,536 bytes is
replaced by:

> Native completion remains within its codec's existing native control cap
> (Agent: 16,384 bytes). The complete nested Mesh control, including envelope and
> LF, also remains at most 65,536 bytes. Both limits and all shared charges apply.

The outer bound cannot replace a stricter native family bound. Generic code
continues to use the configured supported structural codec; no Agent import or
native schema is embedded in Mesh. Material remains at most four transaction
refs and eight MiB. All completion/control, batch, input/copy/parser/pin and
output storage remains inside the same aggregate 64/32 MiB budgets, and counts
in total wire/CPU evidence and the original acquisition deadline. There is no
quota exemption, extra journal or lease renewal.

The terminal control must correlate complete status, request base/target, its
own target tag, final cursor and every nonempty transaction cursor epoch. Zero
transactions are valid only for equal base/target and a self-consistent original
native control. Generic relay preflight independently checks the entire chain
and terminal metadata before output; it drains material before the exact original
completion bytes. It cannot fabricate completion, infer it from EOF/watch, or
fall back to legacy `changes()` when the new method is absent. Reader material,
proof, nonce, root, incarnation and deadline checks remain independent.

## Evidence boundary

The unchanged owning probe at Observer `132c0f1`, SHA256
`c34a325c310e3663aa5348664800578da3bdca9b3e0e29d88fa94c47b12af9c2`,
was replayed from an immutable private export on Python 3.14.8 and 3.11.17.
Its twelve full/active header/head cases accept a 16,384-byte padded native
control and reject 16,385 and 65,536 bytes, with zero final fixture credit.
This proves the synthetic lexical bound only. Test raw input lies outside the
fixture credit; it is no aggregate resource, real relay or native-authority proof.

The [reconciliation evidence](evidence/2026-10-16-delta-sync/completion-transfer-review-r2.json)
pins those bytes and outputs. This document implements no new source method,
relay consumption or controller grammar. The Mesh-owned network operation
grammar, actual source/relay ownership execution, GC-disabled late cancellation,
populated transport, dense/cold/recovery resources and immutable installed pair
remain implementation/qualification work under the existing authorization.
No schema/encoding ID, package/version, artifact, route or rollout changes.
