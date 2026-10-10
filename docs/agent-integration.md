# Agent Observer SDK integration checkpoint

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

Immutable wheels, ordinary native session comparison and operational selection
require the following integration gates. This source checkpoint alone changes
no installed bridge, shared authority, Observer service or downstream client.
