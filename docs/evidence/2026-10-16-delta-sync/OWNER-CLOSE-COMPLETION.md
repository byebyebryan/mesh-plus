# Focused owner-close request completion

This reconciles delayed RLCD request `e-0f11c018` with the already implemented
common input contract. The publication fix is runtime
`e9f07c36b89787994448769d158960cf8856ec14`; callback material-credit protection
is runtime `66b9c1e9c170dbfab847c1c691a6b7b11c9eff13`. RLCD's later
`157a888d25076e0c30d8d4eac4038545d51a506d` records independent bounded source
verification of both. The unchanged common API is SHA256 `7f7751ec...`.

The [publication evidence](INPUT-OWNER-RETIREMENT.md) and
[confirmation-lifetime evidence](HEAD-RETIREMENT.md) remain their original dated
records. This completion adds explicit regression assertions without changing
runtime code, signatures, budgets, roles or those historical artifacts.

The strengthened GC-disabled shared-ledger case now directly establishes:

- Confirmed `ViewRef.context()` and `cache.acquire().context()` report current
  before standalone owner close. Afterwards the old context rejects with
  `sync_view_retired`, acquire rejects with `sync_unconfirmed`, and old refs,
  reserve/resize/seal reject. A previously captured bare proof rejects on the
  retired candidate; its owned-input equivalent rejects on the retired input.
- A still-live receive lease retains its exact 8,192 heap/1,024 encoded credit
  through owner close, replacement intake, repeated stale close, disconnect,
  and a further intake epoch. The sibling remains current throughout.
- Replacement intake still needs ordinary baseline admission and fresh proof.
  Closing the old owner cannot revoke that replacement or a shared-ledger sibling.
  Disconnect remains reusable, without close/disconnect recursion.
- The existing head-callback matrix covers bare/owned proof with owner close/
  disconnect. New assertions directly show that a consuming owned proof keeps
  its full encoded credit while public `nbytes` rejects. No material root is
  released in callback, confirmation or input-pin unwind. The existing stage
  slot holds its charge until subsequent material work or owning cleanup;
  no additional root/retirement queue or quota is introduced.

The targeted publication regression fails on an immutable `32090d69` source
export on both Python versions: acquire incorrectly succeeds after close.
Both Python 3.14.8 and 3.11.17 pass all **59** focused input/cache/acquisition/
private-page tests against the fixed runtime and strengthened tests. Before runs
use the new tests/fixture overlay, not tests attributed to `32090d69`.
Input hashes are stable across the four runs. Ruff and the unchanged 33-input/
25-schema lock pass. The earlier 290-test canonical gate remains bound to its
original test bytes; it was not rerun or relabeled for this test-only completion.

[`owner-close-completion.json`](owner-close-completion.json) binds test/runtime
inputs, before/after source, commands/PYTHONPATH, logs and earlier evidence.
The original Observer probe SHA256
`14357ed33e1036edc9b9c8db40d9a3e2c00c79b1c44edcaa7d3a56cbb3c6d550`
is preserved as the finding's provenance. It intentionally asserts the old
incorrect behavior, so it is not relabeled a passing fixed-source test.

The standalone owner is an owning cache/Reader lifecycle control. Source sessions
continue closing only their own refs/leases and do not close a shared owner.
The separate Observer watch-close defect was fixed in `4254a97`; it is not
claimed as coverage from these Mesh-only tests. A1 and compact interface
agreements remain closed on their exact previously recorded bytes. Actual
compact/relay execution, aggregate resources/RSS, dense/cold/recovery performance,
native/installed pair and G1/G2 acceptance remain open. No sibling, package,
install, provider/service, consumer, device or rollout action occurs.
