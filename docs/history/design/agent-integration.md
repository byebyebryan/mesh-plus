# Agent Observer SDK integration checkpoint

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Date: 2026-10-09. Source starts at `dc79623` (unreleased a3); the compatible
integration candidate is a4. The Agent wire remains
`agent-observer.mesh-candidate.v1`. Authority, frozen lock and packaged schemas
are unchanged. The a3 diagnostics and pool design remain independently scoped.

`configured_read.configured_reader` resolves local or catalog endpoints without
opening them. It returns the existing Reader. `report_routes=False` is the
default; Observer explicitly uses it to remain a read-only client. Mesh's CLI
retains its existing opt-in route reporting. Remote catalog revision monitoring,
ordered scope, codec binding and owned connection cleanup stay in Mesh.

The Agent adapter now gets frame limits from the public service descriptor.
The effective selector requires current runtime evidence/receipt for unsaved
rows. Independently fresh history cannot renew stale runtime-only rows. Saved
metadata and unrelated providers remain usable; original native frames/rows
remain lossless. This conservative selection grants no negative lifecycle fact.

Source gate: lock checks pass (18 inputs, 20 identical packaged schemas), design
116 checks, Delivery 169 checks, runtime/owned native SSH 84 tests and lint pass.
Configured binding tests cover no early connection, ordered remote scope,
revision checks and route-report opt-in. The stale-unsaved regression covers
healthy initial state, independent fresh history, raw retention and unaffected
Claude rows. Observer's own optional client checks are separate.

The exact-checkout `--check-sources` command rejects newer Tmux Observer HEAD
`b9c6836` against its historical `128f7f8` baseline. An independent file-digest
comparison matches every recorded input in all five sibling repositories.
The lock/reference evidence is preserved. Current repository HEAD equivalence
is not claimed; no sibling source is rewritten to satisfy a historical gate.

The following Agent Observer integration gate is now accepted. Its local evidence
is `agent-observer/docs/evidence/2026-10-09-mesh-integration/REPORT.md`.
Observer source `e55825e` and Mesh source `2cc12ac` bind a12/a4 wheels. Mesh wheel
SHA-256 is `55a8ef018e0bab994ce3dd2106552a69fdcb5a397ed607cd9cab92afb51659dd`.
Isolated core packaging passes 56 tests with neither Observer installed;
the two-domain immutable-wheel environment passes all 84 owned native/SSH tests.
An initial Agent-only full-suite attempt lacked the required optional Tmux
package; its rejected evidence is retained before the corrected fixture gate.

Ordinary native comparisons verify 3 running Codex/8 Claude contexts on Snap,
and 6 Codex contexts on Starship, within existing provider/cache limitations.
Fleet cached snapshot and replacement-watch proofs work in both directions.
Bridge loss revokes authority and restart produces ready resync; serialized
rollback restores a11 read targets/cache and reselects the reviewed a12/a4 tuple.
Provider settings, collection-service PIDs, shared SSH authority a1 and unrelated
source drift are preserved. Only the separate Agent bridge/client selection
changes; no provider policy, Tmux/Plus, alert, action or device migration occurs.
Exact wheels are archived on both hosts; no public a4 release is claimed.
