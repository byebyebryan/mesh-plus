# Agent ecosystem realignment: execution plan

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: source/artifact endpoint completed under the user's explicit
luna-goal-loop request, 2026-10-23. See the
[qualification and handoff](../../evidence/2026-10-22-ecosystem-realignment/README.md).
The subsequent user review settled main-line maintenance, working-set CLI work
and full retirement of Observer writes and the standalone active-only feed.
The [maintenance and retirement follow-up](agent-ecosystem-maintenance-plan.md)
is the current next-loop plan. The completed checkpoints and retained-path
decisions below keep their original execution scope.
This document coordinates work across the six repositories. Each
repository continues to own its contracts, code, checks and acceptance evidence.
Managed host selection belongs to chezmoi. This plan does not supersede frozen
contracts or reassign historical acceptance to new bytes.

## Objective and completion boundary

Align the ecosystem with native shared agent runtimes: Mesh/SSH provide the
multi-host backbone, Agent Observer provides reusable read-only agent facts,
Agent Plus opens native managers, and the Tmux pair serves its remaining users.
Make the active dependencies understandable, simplify supported paths where
evidence justifies it, and prove that an additional read-only utility can use the
existing public boundaries without copying provider internals.

First-loop endpoint: reviewed source/documentation changes, focused
compatibility evidence, qualified local artifacts where runtime bytes change,
and a concrete rollout/retirement proposal. Push, publication, fleet selection,
live service retirement and firmware changes have separate authorization.
The execution request adopts this endpoint; no publication or deployment
extension was requested.

Completion requires the checkpoint outcomes below, including explicit retained
decisions where removing a path is unjustified. It does not require reducing
every version to one value, removing every legacy path, creating a new product,
or completing deferred performance/physical-device research.

## Direction established by the user

| Area | Direction |
| --- | --- |
| Native provider managers and daemons | Own conversation/session control, work, authentication and provider settings |
| Mesh Plus / SSH Plus | Remain the multi-host backbone |
| Agent Observer | Read-only observation is useful independently, including for hardware dashboards and future agent utilities |
| Agent Plus | Convenience entry/focus for native multi-session TUIs; external conversation control is no longer its central job |
| Tmux Observer / Tmux Plus | Lower strategic relevance following the runtime change; continued purpose follows real tmux usage |
| Claude | Retired from Observer native discovery/monitoring; lightweight native TUI entry remains valid in Agent Plus |
| Codex | Primary observation target for work and personal use |

The company licensing context explains product priority. Record the resulting
support policy in product docs without duplicating personal employment details.

## Working decisions for this plan

The execution request adopts these working defaults. Material changes follow
the decision and compatibility gates below.

- Keep the six repository boundaries. Evaluate simplification within them.
- Preserve the current Host Mesh v1 commands and configuration/state paths.
  Existing Mesh ownership documentation already settles the authority split;
  reconcile implementation and descriptions before proposing another migration.
- Keep the Tmux pair in maintenance with a stated purpose and reopen triggers.
  Reduced strategic importance does not establish that its services are unused.
- Start utility work from existing public cached-read and Mesh interfaces. Use
  the working-set route when its semantics fit; preserve deliberate full reads
  for diagnostics and other documented consumers.
- Use the existing hardware dashboard as one compatibility consumer and a tiny
  read-only example as a second consumer. The example is a developer recipe,
  with no persistent service or new application release.
- Preserve exact artifact guards, independent role pins and existing rollback
  points until a separately qualified replacement earns adoption.
- Keep execution primary-led, with Luna Max handling bounded investigation and
  implementation under the explicitly invoked luna-goal-loop skill. Primary
  retains product decisions, integration and acceptance.

Reopen these defaults only for a demonstrated requirement. Record the evidence,
alternatives, compatibility impact and chosen boundary before changing code.

## Baseline and ownership

These are starting references, not permission to edit existing worktrees or
promote a branch. Refresh the exact heads, dirty state and owners at execution.

| Repository | Inspected worktree | Starting head | Responsibility in this loop |
| --- | --- | --- | --- |
| mesh-plus | mesh-plus-view-feed | a32019b | Host authority, public SDK/delivery boundaries, shared coordination plan |
| rofi-ssh-plus | rofi-ssh-plus | 470dd89 | SSH picker and Host Mesh CLI/contract compatibility |
| agent-observer | agent-observer-working-set | a4a122a | Observation semantics, read interfaces, utility guide/example, retained read/write paths |
| rofi-agent-plus | rofi-agent-plus | 62d9bc5 | Native environment/window entry, Host Mesh consumption, capability-specific support |
| tmux-observer | tmux-observer-view-feed-20261020 | a71a4d5 | Remaining owner/fleet/action consumers and maintenance boundary |
| rofi-tmux-plus | rofi-tmux-plus-mesh-a24-20261020 | 3839c2a | Tmux user workflows, public CLI consumers and maintenance documentation |
| chezmoi | ~/.local/share/chezmoi | b5357c2 | Host/role selection, launchers, units and deployment preparation only |
| esp32-rlcd | selected immutable dashboard bundle plus owning source worktree | discover exact selected source | Existing downstream consumer; compatibility observation by default |

Create isolated execution worktrees from reviewed relevant lineage. Keep
concurrent work and experimental branches intact. Source-to-main reconciliation
is an explicit integration item, not an instruction to merge every feature branch.
Record excluded branches and why they are excluded.

Current observations that need fresh confirmation in checkpoint 0:

- Starship selects Observer a8 collectors and a8/Mesh a24 working-set publication,
  while its read CLI and full-feed publication retain a5/a20. Active publication
  retains a7/a23. The historical writer has another independent prefix.
- The Tmux selected cohort is Observer 0.6.0a9 / Plus 0.12.0a8 / Mesh a24 with
  ordinary full views; view-feed and semantic delta remain unselected.
- Both picker consumers contain the 38 Host Mesh producer files byte-for-byte.
- Current-facing documentation and AGENTS.md contain earlier Agent Plus/Tmux
  dependency assumptions and older current-version statements.
- The dashboard's effective host overrides and Starship entrypoint now reference
  an a8/a24 immutable bundle. Earlier a7/a23 handoff notes are historical.
  Separate candidate manifests name other bundles; their existence alone does
  not establish selection, running bytes or device acceptance.
- Multiple source branches contain selected work beyond remote main. Their
  preserved experiments must not be promoted as part of documentation cleanup.

## Checkpoint 0: reproducible current-state and consumer census

Produce one compact census with supporting receipts, without changing native
runtime or service selection. Cover Starship, Snap and Carbon where accessible;
mark unreachable or uninspected hosts explicitly. Read-only source inventory
can proceed while host access is unavailable. Host-specific conclusions remain
pending until inspected.

For each meaningful role, record repository/source, artifact digest, host/home,
unit/command/socket, public interface/profile, selection source, confirmed
consumers, compatibility purpose, rollback dependency and operational owner.
Distinguish declared, selected, installed, running and physically observed state.

Trace at least: host authority, generic/shared Mesh launcher, Tmux owner/fleet/
desktop/actions, Observer collector per home, full/active/working-set publishers,
read CLI, historical writer, Agent Plus helper/desktop, and dashboard bundles.
Search source, managed config, scripts, external entrypoints and declared manual
workflows. A grep miss or one moment with zero socket clients is insufficient
evidence for removal.

Classify each path as required, manual/on-demand, compatibility/rollback,
retirement candidate, or unresolved. Record evidence and unknowns. For retirement
candidates, inspect a bounded representative observation window and clarify
undiscoverable manual/external consumers before making a removal decision.

Acceptance: each enabled role has a known consumer/purpose or an explicit
unresolved item; effective dashboard and shared-launcher dispatch are traced;
no historical handoff is treated as current status. Save enough identities and
artifact receipts to detect concurrent changes before later mutations.

## Checkpoint 1: settle ownership and capability contracts

Write a compact current architecture/ownership record and per-repository changes.
Use current implementation and user direction to resolve these boundaries:

| Boundary | Required result |
| --- | --- |
| Host authority | Mesh owns host IDs, aliases, route policy/revisions and health; SSH owns picker history/explicit connection UX; one selected authority writer |
| Public Host Mesh interface | Existing CLI remains supported; identify canonical contract owner and provenance without moving schema files or changing bytes implicitly |
| Observation | Observer owns native identity, runtime/phase/activity/coverage; core/local service remain Mesh-free |
| Network delivery | Mesh preserves native meaning, origin, uncertainty and original receipts; no provider classifier or UI policy |
| TUI entry | Agent Plus owns declared environments, owned windows and fresh entry/focus validation; native tools own conversations |
| Utilities | Consume public read interfaces; own selection, presentation and any separately designed action/alert policy |
| Tmux | State the supported generic tmux use cases and public APIs independently of retired agent-runtime assumptions |
| Provider support | Codex observation; Codex/Claude native entry as separate capabilities; no implied Claude monitoring commitment |

Acceptance: each responsibility has an owner; retained compatibility is explicit;
remaining product decisions are visible. Any public behavior change has its own
reviewed change packet before implementation. The ownership docs do not invent
a new normative protocol or waive frozen contract rules.

## Checkpoint 2: establish a usable Observer utility path

Document the shortest supported path for a new read-only utility: compatible
artifact selection, host/home identity, cached local read, explicit Mesh read,
snapshot/watch, currentness/expiry, selection, disconnect/recovery and shutdown.
Link dated evidence separately from the current interface guide.

Build one small source-owned example, preferably under Agent Observer's existing
examples structure: a terminal current-state summary with explicit identity,
health and coverage. Reuse public read helpers and existing fixtures. It must
contain no provider queries, private imports, conversation-content persistence,
new daemon, native actions or device transport.

Use both that example and the existing dashboard adapter to assess the public
boundary. Record duplicated client policy separately from missing producer
capability. Implement a shared helper only for demonstrated reusable semantics.
If current APIs suffice, preserve them and deliver the recipe/example evidence.

Acceptance cases, primarily reusing existing tests and controlled fixtures:

- Cached local consumption starts no collector, provider daemon or native TUI.
- Exact host/account/home/namespace/session identities remain distinct, including
  two Codex homes. Titles, cwd, PIDs and window presence grant no runtime truth.
- Complete-empty, partial, warming, stale-source and failed-delivery cases remain
  distinguishable. One host failure preserves independently valid siblings.
- Quiet expiry removes authority without waiting for another data event.
  Heartbeats, copying and display refresh do not renew native facts.
- Restart/reconnect/incarnation change revokes old claims and recovers from a
  valid replacement baseline. Source and receiving clock domains stay separate.
- Cancelling/closing a utility retires its owned reads/streams and preserves
  sibling consumers. A retained label or identity is not a current-state claim.
- Installed execution outside sibling checkouts uses only declared packages and
  public interfaces. No silent fallback to a different profile/read path.

Keep sampled-state and occurrence-event guarantees explicit. Durable completion
alerts, notification replay and action APIs remain separate future requirements.

## Checkpoint 3: simplify only justified source paths

Create a per-change packet: problem, known consumers, smallest viable change,
preserved public behavior, rollback, checks, deployment delta and acceptance.
Handle producer changes before consumer adoption; a consumer-discovered producer
defect reopens its owning checkpoint.

Candidate areas to decide from the census:

- Retained Observer writer/launch helpers tied to the former external controller.
- Full, active-only and working-set publication overlap. Preserve distinct
  semantics and explicit diagnostic uses; API availability and always-on hosting
  are separate decisions.
- Repeated host-authority adapters or contradictory ownership descriptions.
  Independent consumer validation and frozen contract copies are not redundant
  merely because they are similar.
- Tmux components whose only documented consumer was the former Agent Plus.
  Preserve current generic tmux and manual consumers where they remain useful.
- Copied deployment selections and drift-prone version summaries. Derive small
  summaries/checks from owner manifests where practical; avoid a second
  authoritative deployment registry.

An unsupported removal remains a retained decision with a reopen trigger.
Classify source deletion, public API retirement, disabling an enabled service and
deleting installed prefixes as different changes. The first loop prepares live
retirement packets; it does not perform live retirement by implication.

Acceptance: every runtime change has a demonstrated purpose and focused proof;
every proposed removal identifies its consumers/compatibility impact; no path is
removed solely because its name, version or architecture is old. Preserved
public contracts and artifact guards remain enforced.

## Checkpoint 4: documentation and integration closeout

Update README current-state sections, architecture/suite integration, roadmap,
support tables and AGENTS.md in each owning repository. Repair claims that
Agent Plus consumes Observer/Tmux, is globally deferred, or owns conversation
control. State current Claude support by capability. Preserve dated evidence;
label superseded records instead of rewriting their acceptance.

Document how source, public main, releases, candidate artifacts and deployment
roles relate. Propose the exact accepted commits for later integration, with
experimental exclusions and provenance. Do not cherry-pick or merge unrelated
feature lineages to make all branches appear current.

Produce an operations map from existing owner manifests: host/home and role,
artifact tuple, selected launcher/unit, consumers, acceptance and rollback.
Keep semantic contracts in producer repositories and host selection in chezmoi.

Acceptance: all six landing pages and agent instructions tell the same current
story; Host Mesh contract bundles remain synchronized; a fresh contributor can
locate current interface documentation and the selected role map without
reconstructing a long historical ledger. Cross-repository links resolve.

## Checkpoint 5: qualification and rollout-ready handoff

Run the owning source/contract gates for changed runtime code. Use focused
checks for documentation-only edits; run any additional checks required by the
owning repository before committing or publishing. Avoid requalifying unchanged
artifacts as if their historical scope had expanded.

| Owner | Validation anchor |
| --- | --- |
| Mesh | Selected environment running scripts/check.py; authority compatibility, SDK/conformance and isolated-wheel checks as affected |
| SSH Plus | scripts/check; public Host Mesh and selected-authority/explicit-legacy compatibility as affected |
| Agent Observer | scripts/check; pure-import/read/working-set checks and installed native comparison as affected |
| Agent Plus | scripts/check; check-contract-sync; installed-artifact and existing direct native proof drivers as affected |
| Tmux Observer | uv run --extra dev ./scripts/check; scripts/check-mesh and owned native/action fixtures as affected |
| Tmux Plus | scripts/check; public contract, Observer artifact guard and installed/headless proof as affected |
| RLCD | Existing SDK/bundle and consumer checks against exact artifacts; device work separately scoped |
| Chezmoi | Scoped status/diff/dry-run and existing selection checks for the proposed target set |

Artifact changes require fresh immutable builds, digests, installed-byte checks
and outside-checkout execution. Shared launcher/authority changes require both
domain routes, identity/route binding, cached/proof/watch behavior and relevant
rollback compatibility. Native claims require independent native evidence;
source fixtures cannot establish physical GUI/device behavior.

Measure performance only for a concrete change that can affect repeated work.
Use bounded before/after workloads with equivalent semantics and report native,
producer, transport and consumer costs according to the changed boundary.
Respect existing resource limits. Do not revive failed dense-capacity/delta
research or invent a whole-fleet saving from one consumer process.

Final handoff contains:

1. Findings and decisions, with unresolved items and reopen triggers.
2. Current ownership, capability support and role/consumer map.
3. Changed repositories/files, exact heads and artifact receipts.
4. Utility recipe/example and existing-dashboard compatibility evidence.
5. Retained/retired-source inventory and live-retirement proposals.
6. Exact integration, publication and managed target deltas, with recovery inputs.
7. Checks passed/failed/skipped and explicit uninspected host/GUI/device limits.

Acceptance: the agreed source/artifact endpoint is reviewable and reproducible.
If a required gate fails, fix its owning bounded change and rerun the affected
checks. Preserve failed evidence; do not weaken validation or change the endpoint
to manufacture completion.

## Execution cadence and stop boundaries

Maintain a small status ledger beside this plan during execution: checkpoint,
current task, exact inputs, changes, next check, blockers and decisions. Refresh
the baseline after compaction/resume and before touching a different repository
or live target. Accept checkpoints against outcomes, not elapsed effort.

Continue autonomously through authorized source changes and routine fixes.
Once execution is authorized, make narrow local commits at accepted checkpoints
after the owning required checks; keep publication and deployment separate.
An investigation should end in a bounded change, a retained decision, or a
specific unresolved requirement. Do not repeatedly widen the census or rerun
large benchmarks after the decision is already supported.

Hold dependent changes for a material new product decision, public-contract break,
unresolved external/manual consumer removal, or conflict with concurrent owner
work. Continue independent planning/checks while resolving it. Existing native
sessions, provider daemons/settings and unrelated services are protected.

Fleet rollout, if later authorized, is a distinct checkpoint: capture exact
preimages; review scoped chezmoi status/diff/dry-run with umask 022; apply only
reviewed targets; verify installed/running bytes and consumer behavior; exercise
the agreed rollback/reselection; retain prefixes still used by live clients.
Choose the least disruptive eligible host from checkpoint 0 rather than
assuming one host's desktop state. Physical panels, ACKs, input and suspend
remain their own evidence. Recheck host-specific ownership before every apply.

No global runtime-model rewrite, repo merger, config-directory rename, new
provider observation, notification/event platform, transport switch, delta/feed
enablement, native runtime shutdown, firmware flash or installed-prefix purge is
part of the proposed first-loop default. A demonstrated need can create a
separately scoped follow-up with its own acceptance criteria.

## Initial decision queue

| Decision | Proposed disposition | Evidence needed before a different choice |
| --- | --- | --- |
| First loop endpoint | Source cleanup, qualified local artifacts, rollout-ready proposal | Explicitly agreed extension to publication/deployment |
| Tmux maintenance purpose | Preserve useful generic tmux workflows | User workflow census and actual consumers before retirement |
| Observer full/active/working-set hosting | Retain until each role is traced | Consumer and compatibility census, bounded usage evidence and rollback impact |
| Historical writer | Treat as a retirement candidate | Manual/external use and native-action compatibility evidence |
| Host Mesh naming/paths | Explain existing ownership and preserve interfaces | A concrete usability/operational defect that justifies migration cost |
| Shared utility helper | Reuse existing facades; add only demonstrated missing semantics | Two-consumer proof of repeated correctness logic |
| Source/main reconciliation | Prepare exact integration proposal | Complete lineage/owner review and explicit integration scope |
| Dashboard adoption | Inspect effective selected bundle and running process afresh | Candidate-manifest existence is insufficient |

## Owning references

- [Mesh/SSH ownership and compatibility](../../ssh-plus-integration.md)
- [Mesh SDK interface](../../sdk-api.md)
- [Mesh frozen contract boundary](../../contract-freeze.md)
- [Mesh handoff and dated checkpoints](../../handoff.md)
- Agent Observer: docs/observation-boundaries.md, docs/api-v4.md,
  docs/prepared-agent-read-interface.md, current working-set/home-profile docs
  and exact-source acceptance receipts.
- Agent Plus: docs/architecture.md, docs/SUITE_INTEGRATION.md,
  docs/managed-operations.md and artifacts/managed-direct-selection.json.
- Tmux Observer: docs/runtime-architecture.md, docs/managed-operations.md and
  the selected full-view cohort receipt. Tmux Plus: docs/observer-boundaries.md
  and its selected observer-artifact.json.
- SSH Plus: contracts/host-mesh-v1 and current authority backend implementation.
- Chezmoi: effective deployment manifests, per-host overrides and rendered
  launchers/units. RLCD: the selected immutable bundle plus owning source.
