# Decisions, integration and rollout boundary

The 2026-10-23 loop implements the source/artifact endpoint of the
[execution plan](../../agent-ecosystem-realignment-plan.md). Final validation
and local commit identities are recorded by the execution status and handoff.
No selected service, native runtime, configuration, firmware or remote ref is
changed by these decisions.

## Accepted architecture

Mesh owns shared host authority and reusable state delivery. SSH Plus owns the
canonical Host Mesh v1 process contract/facade and picker history/connection UX.
Keep existing commands and paths. Independent contract validation and explicit
legacy rollback are required compatibility boundaries.

Agent Observer supplies Codex read-only facts to dashboards, diagnostics and
agent utilities. Pure model/read facades, collection/service and optional
networking retain their own responsibilities. Native provider managers own
conversation control. Agent Plus discovers environments and enters/focuses
owned native manager windows through Host Mesh, with no Observer/Tmux runtime
dependency. Claude native entry is independent of retired Claude observation.

Tmux Observer/Plus continue as supported generic tmux tooling. New work requires
a concrete consumer. Their reduced agent-runtime relevance supplies no evidence
for stopping currently running owner/fleet services or removing action APIs.

## Source simplification decisions

| Area | Decision | Reason and reopen trigger |
| --- | --- | --- |
| Former Agent Plus dependencies | Remove current-facing claims that Observer/Tmux back Agent Plus | Current runtime imports and native-entry path no longer have those dependencies; historical receipts remain dated |
| Observation support | Describe Codex observation and Codex/Claude entry separately | Launch capability does not imply discovery/monitoring support; new observation adapter requires its own native contract proof |
| Full Agent route | Retain | Full read CLI and explicit dashboard full-roster diagnostics remain consumers; replacing a full contract with a projection would change semantics |
| Working-set route | Retain | Existing hardware/dashboard consumer uses it; currentness, uncertainty and membership/scope coverage are useful beyond that display |
| Active-only route | Retain selected hosting; identify retirement candidate | Current in-repository downstream consumer after the dashboard move is unresolved. Reopen after manual/external and rollback use is established |
| Historical writer | Retain source, public command and installed prefix; identify retirement candidate | No current Agent Plus caller, but it remains an independently selected public command and manual/external use is unresolved |
| Tmux owner/fleet/actions | Maintain | All three hosts run them and generic/manual clients remain supported. Reopen with an explicit workflow retirement or measured operational problem |
| New utility helper API | Reuse existing public facades | The new example and existing dashboard can use Service4/SDK1 working-set reads without copying provider logic or creating another daemon |
| Exact package guards and role pins | Preserve | Source, installed selection and consumer acceptance remain independently bound; a version mismatch alone is not a simplification defect |

The source census did not establish a safe deletion of any runtime path. Keeping
an unresolved compatibility surface is an accepted decision for this loop;
retirement remains a separately reviewable change with a specific trigger.

## Live retirement packets for later review

These identify concrete future targets. They do not authorize applying them.

### Active-only hosting

Candidate targets on Starship, Snap and Carbon are
`mesh-plus-agent-active.service`, its default-target link, the fixed
`mesh-plus-active` launcher and the active-source branch of the shared launcher.
The `activeSelection` owner manifest binds Observer a7/Mesh a23 independently.
Before changing hosting, identify manual/external callers, retained rollback
uses, fixed remote-command expectations and the desired on-demand availability.

Capture the current unit, enablement/link, launcher bytes, manifest and source
dispatch. A proposed disablement must preserve typed source-unavailable results
and healthy full/working-set/Tmux siblings, with no implicit fallback. Verify the
same consumer behavior after rollback/reselection. Keep the a7 prefix while any
client or accepted rollback needs it. Public active-profile retirement is a
different change from disabling always-on hosting.

### Historical writer

Candidate targets are `.local/bin/agent-observer-write` and `writerPrefix` in
the Observer deployment selection. The selected 0.4.0a16 prefix is a recovery
input, not an invitation to purge installed bytes. This is a public-command
retirement, so source searches and an instantaneous process count cannot close
the manual/external-consumer question. A native manager entrypoint is not a
drop-in replacement for exact New/Resume write semantics.

Before removal, settle remaining workflows, compatibility messaging and command
absence/error behavior; verify the independent read/collector/publisher roles.
Capture and restore the exact selector and manifest on rollback. Keep ordinary
provider runtimes, histories, settings and active TUI clients untouched.

### Tmux maintenance

No live retirement proposal is accepted. Owner, desktop fleet and action
interfaces remain useful to Tmux Plus and manual clients. If the user later
retires those workflows, inventory owned sessions and caller identities first;
stop/rollback boundaries must preserve native sessions and other domains.

## Source-to-main integration

Each local loop commit is confined to an isolated worktree and preserves its
source parent. The integration map records exact parent/main refs, the loop
commit, and all prerequisite commits outside main. These are review inputs,
not an automatically approved merge set.

| Repository | Parent relative to the inspected origin/main | Integration disposition |
| --- | --- | --- |
| SSH Plus | Same main | Narrow docs plus gate-formatting correction can be reviewed independently |
| Agent Plus | Same main | Narrow documentation commit can be reviewed independently |
| Tmux Observer | Three prerequisite commits | Current selected a9/full-view cohort is on its own lineage; review its recorded source/artifact acceptance before promoting that base |
| Tmux Plus | One prerequisite commit | Exact a9 producer pin is separate from this loop's documentation changes; artifact supply for CI must be resolved before public integration |
| Mesh Plus | 105 prerequisite commits | Preserve experimental/dark lineages; do not merge the entire branch to land this plan or ownership text |
| Agent Observer | 110 prerequisite commits | The utility tests use a8 working-set fixtures/interfaces; preserve that explicit dependency and its separate producer history |

For Mesh/Observer, an owner-reviewed promotion of the selected release lineage
and a targeted port against main are alternative integration tasks. Either must
preserve frozen schemas, retained experiments and exact evidence attribution.
Blind cherry-picks can leave missing guide/fixture targets or misstate available
interfaces. This loop provides local commits against the reviewed cohort and
the exact prerequisite list; it does not choose an unreviewed main promotion.

Tmux Plus currently pins a private a9 wheel. Its public CI recipe expects a
hosted release at that version. The v0.6.0a9 remote tag was absent when inspected;
the exact wheel is staged locally and its digest is verified. The corrected
development guide uses an explicit qualified artifact path. Local source gates
can pass without claiming hosted CI acceptance. Separately authorized artifact
publication or an explicit qualified artifact supply is needed before that CI
recipe is usable. Do not weaken its hash/module guards or substitute a wheel.

## Managed deployment delta for this loop

The accepted changes introduce no new packaged producer/transport behavior or
selected unit. The new example is a source-owned developer recipe consuming
unchanged installed public packages. The SSH check-script correction only
formats a test-interpreter wrapper; it has no product/runtime behavior change.

Consequently, the proposed managed target set is empty. No chezmoi apply, daemon
restart, version convergence, dashboard rebundle or firmware flash is needed to
make these source changes available for review. Publication/integration is
separate from fleet adoption; future runtime changes get fresh package and
consumer gates rather than reusing this documentation/recipe acceptance.

Any later approved retirement or runtime rollout must capture exact preimages,
review scoped status/diff/dry-run with umask 022, apply only its reviewed targets,
verify selected/installed/running and actual consumer behavior, then exercise
the agreed rollback/reselection. Device ACK/panel/input and physical suspend
remain independent evidence. Preserve unrelated drift and prefixes used by live
clients throughout.
