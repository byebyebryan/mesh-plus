# Cache input-owner publication retirement

Runtime `e9f07c36b89787994448769d158960cf8856ec14` fixes the independent
cache-backed `InputOwner.close()` publication gap identified by Observer's
exact r2+r3 review. This implements the already agreed common input contract
SHA256 `7f7751ec...`; it changes no public signature, schema, package version,
relay contract or role. It is separate from pending A1 exact relay agreement.

Before the fix, closing the current input owner revoked sealed data refs and
prevented future reserve/seal, but left an already confirmed cache view usable.
The new shared-ledger regression fails at `cache.acquire()` against an immutable
export of parent `7d7b09c`: the expected unconfirmed error is not raised. The
same test passes against the changed source.

Owner close now runs under the cache lock, retires that input epoch and applies
the cache's existing publication/candidate revocation barrier when the owner is
still the cache's current owner. It does not terminally close the cache. The
identity check prevents a stale owner's repeated close from revoking its
replacement. It cannot revoke a sibling cache sharing the allocation ledger.
Unsealed receive reservations and consuming raw/I/O pins keep their credit
until their actual cleanup, as before. Sources still close only their own refs
and leases; they must not close a shared InputOwner to retire a source session.

The first regression disables cyclic GC and confirms both aliases on a shared
ledger. After owner close, acquire, retained view/value and candidate accesses
reject; a sealed ref rejects; receive resize/seal reject while its 1,024 encoded
bytes remain charged. The sibling stays confirmed. A replacement owner can
perform ordinary material admission and a fresh proof; repeated old-owner close
leaves both replacement and sibling views usable. Receive cleanup then refunds
its own credit. The second regression closes the owner reentrantly inside the
head callback: no confirmation survives and the owned input/error frames retire.
Neither test grants admission reuse or changes original lease rules.

Validation on the changed source:

- Python 3.14.8 canonical gate: 288 tests, no skips, 116 design and 169 delivery
  checks, Ruff, unchanged 33-input/25-schema lock.
- Python 3.11.17: 57 focused Mesh input/cache/acquisition/private-page checks.
- Both 3.14.8 and 3.11.17: 100 Observer source/intake/acquisition/profile/read
  checks against an immutable export of
  `f14fb675d4b4cc6010a9225084fba0c94ece507d`.
- Each version also passes 101 checks against the stable working-tree overlay
  present during the initial compatibility run. The report lists the three
  uncommitted paths and their exact tested/base hashes. Those results are not
  attributed to f14 alone or accepted as a committed counterpart checkpoint.
  No sibling source/test is edited by Mesh.

[`input-owner-retirement.json`](input-owner-retirement.json) binds the exact
70 Mesh and 91 immutable Observer source/test/schema inputs to their commits,
plus the separately identified working overlay, commands, PYTHONPATH,
before/after results and eight logs. The canonical command is
`rtk proxy .venv/bin/python scripts/check.py`. The before failure is retained in
[`input-owner-before.log`](input-owner-before.log), the focused after result in
[`input-owner-after.log`](input-owner-after.log), and the complete canonical gate
in [`input-owner-canonical.log`](input-owner-canonical.log).

The source-only checks use disposable fixtures; they do not establish populated
installed IPC/fixed SSH, aggregate intake/output/pin peaks, RSS/plateau, dense or
packed recovery CPU, or end-to-end acceptance. Earlier packed-node diagnostics
remain bound to runtime `18e95c1`; they are not reattributed to this changed
runtime. Relay r4 remains exactly SHA256 `5377d3a5...`, candidate commit
`7d7b09c`, with joint signoff and the coordinator's A1 record still required
before dependent relay implementation. No artifact, service/provider, normal
route, sibling runtime or rollout action occurs.
