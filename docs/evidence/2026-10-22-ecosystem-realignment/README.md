# Native-runtime ecosystem loop: qualification and handoff

Completed 2026-10-23 at the agreed source/artifact endpoint. The ecosystem now
has a consistent current role description and a qualified read-only utility
recipe. Existing runtime and deployment boundaries remain independently owned.

## Result

- Mesh/SSH remain the multi-host backbone, with Mesh authority implementation
  and the supported SSH Plus Host Mesh facade/contract clearly distinguished.
- Agent Observer is Codex read-only observation for dashboards and utilities.
  Agent Plus independently opens native Codex/Claude managers. Claude entry
  does not imply Claude monitoring. Tmux remains supported generic tooling.
- Six repositories' landing/current architecture/support instructions were
  reconciled. Historical producer and consumer acceptance keeps its original
  source, artifact, date and endpoint scope.
- Observer has a developer-owned bounded summary example and public-read guide.
  It uses existing Service4 and optional SDK1 working-set reads, with explicit
  expiry, coverage, failures and terminal revocation. It starts no collector or
  provider and provides no action or event-replay API.
- Source/config consumer tracing supports retaining full, working-set, active,
  writer and Tmux paths. Unknown manual/external use is recorded instead of
  being treated as permission to delete code or stop services.

The [role guide](../../ecosystem-role.md), [source census](source-census.md),
[host census](host-census.md) and [decisions/rollout packet](decisions-and-rollout.md)
provide the architecture, active dependencies and reopen triggers.

## Qualification

| Owning source gate | Cases | Result |
| --- | --- | --- |
| Mesh canonical gate | 483 | Pass; zero skips |
| Agent Observer, working-set SDK required | 1,206 | Pass; zero skips |
| Tmux Observer | 405 | Pass; zero skips |
| Agent Plus | 153 | Pass; zero skips |
| Tmux Plus | 293 | Pass; zero skips |
| SSH Plus | 82 | Pass; zero skips |

Observer's 17 focused utility tests pass on Python 3.11 and 3.14 with the exact
released a8/a24 wheels. The final required gate uses the matched installed
interpreter. Tmux gates use declared Ruff 0.16.6 and the exact staged a9 producer
wheel where needed. Mesh uses a complete isolated a24 editable dev environment.
One pre-existing SSH check-script formatting defect was corrected, with no
product behavior change. Documentation-only closeout edits receive focused
link/whitespace checks rather than another unchanged runtime-suite run.

Earlier failed environment attempts remain recorded: a private package index
returned 401; bare test environments lacked the accepted Tmux package; a
borrowed Mesh source env retained a23 distribution metadata; the installed a24
runtime had no Ruff. None was bypassed by weakening a guard or changing a live
prefix. Complete test environments ran the owning gates successfully.

Six outside-checkout smoke cases pass for the copied example using isolated
imports from the installed Observer a8/Mesh a24 pair: Starship local service,
local Mesh, Snap Default, Snap Work, Carbon, and an expected missing-socket
failure. Snap Default/Work namespace digests differ. Every final view has zero
current identities. The exact script hash, artifact path and final results are
in [qualification.json](qualification.json); the earlier failed local timeout
smoke is retained separately from this final qualified artifact.

The existing dashboard bundle 164b7f99c40e7676 passes its manifest verification.
Nineteen existing prepared/working-set/public-two-home consumer tests pass with
zero skips, using its exact selected source 629af372 and unchanged a8/a24 SDKs.
The Observer-owned utility receipt records its detailed example and consumer
acceptance; no RLCD source or selected bundle was modified.

## Preservation and evidence limits

[Runtime/contract parity](runtime-contract-parity.json) compares 703 tracked
existing files across all six protected originals and execution worktrees, with
zero differences. New example/tests, documentation and the SSH check-script
formatting are separate. No frozen schema, lock, profile identifier, provider
runtime or SDK/package implementation was changed.

The [three-host before/after audit](preservation.json) reports no selector or
configuration changes, no service PID/state changes, and all 37 baseline native
process birth identities still observed. Native workflows and selected collector,
publisher, read CLI, writer, Tmux and dashboard roles remain intact. Source
worktrees, installed prefixes, rollback inputs and remote main refs are retained.

The smoke preserves real unavailable source/scope states. A successful read
lifecycle does not certify continuously current native evidence. This loop adds
no independent native classification, GUI/focus/input, device ACK/panel,
suspend, long-run capacity or performance acceptance. Earlier acceptance is not
expanded to a new source or role by this report.

## Local integration and next boundary

All changes are local commits on isolated branches. The
[integration map](integration-map.json) records exact source parents, remote
main snapshots, loop commits and prerequisite exclusions. Mesh's coordination
closeout is the commit containing this final handoff. A generated private
handoff manifest records the final exact heads without a self-referential
tracked commit hash.

Agent/SSH Plus are based on the inspected main heads. Tmux Observer/Plus retain
three/one prerequisite commits; Mesh/Observer retain 105/110 prerequisites.
Review those lineages or port the narrow change deliberately. Do not merge
experimental histories merely to land the documentation/example.

Tmux's private a9 wheel has no hosted v0.6.0a9 tag at inspection, while its
current public CI recipe expects that release. The development guide now uses
an explicit qualified artifact. Artifact publication or another explicit,
qualified CI supply remains a separate integration prerequisite; hash/module
guards stay enabled. No hosted CI success is claimed.

The managed deployment target set for this source loop is empty. Publication,
main promotion, service retirement and firmware remain separately scoped.
Concrete later active-feed/writer retirement targets and rollback conditions
are in the decisions packet. Current unknown consumers are retained decisions,
with no required source-loop work left open.

Luna Max supplied the source census, utility/guide/tests and a final read-only
documentation review. Primary resolved scope and ownership, corrected and
reviewed the work, ran final owning/installed/consumer/preservation checks,
updated all six projects' current-facing documents and accepted the endpoint.
