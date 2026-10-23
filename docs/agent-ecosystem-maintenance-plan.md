# Agent ecosystem: maintenance and retirement follow-up

Status: full-loop execution authorized 2026-10-23. The
[execution ledger](agent-ecosystem-maintenance-status.md) records checkpoint
acceptance; the original planning review did not itself perform implementation.
This follows the completed [realignment loop](agent-ecosystem-realignment-plan.md)
and its [qualification handoff](evidence/2026-10-22-ecosystem-realignment/README.md).
The earlier retained-path decisions remain accurate for that completed loop;
the user decisions below govern the next one.

## Agreed outcome and execution boundary

| Area | User decision / intended result |
| --- | --- |
| Maintained source | Main follows the maintained release lineage; preserve provenance and explicitly gated experiments |
| Observer reads | Working-set is the ordinary utility path; retain deliberate full-inventory diagnostics |
| Utility work | Improve working-set inspection through the existing Observer CLI before creating another application or general client framework |
| Observer writes | Fully retire the supported New/Resume write path, implementation, package entrypoint and managed command |
| Active-only feed | Retire its standalone producer, native/Mesh interfaces, read facade, advertisement, configuration and hosting; working-set retains its active membership branch |
| Native entry | Agent Plus continues native Codex/Claude entry/focus; native tools own conversation control |
| Tmux / repositories | Maintain generic tmux workflows and the six existing repository boundaries |
| Host topology | Starship -> Snap; Snap -> Starship; Carbon -> Snap and Starship; no automatic reverse edge to Carbon |

The subsequent goal-loop request adopts full-loop execution. Completion
includes local source integration, qualified new artifacts, consumer
compatibility and bounded retirement on Starship, Snap and Carbon. A later
execution request may narrow the endpoint. Once a
checkpoint is authorized, routine preparation, corrections and its reviewed
changes do not need another approval of the same product decision.

Push, public artifact publication, unrelated fleet upgrades, firmware and
installed-prefix purging are not implicit. If a public release is required to
complete an installer/CI path, prepare the exact release candidate and identify
that dependency before publication. Qualified private delivery can complete a
managed change only where the owning deployment policy supports it; do not
silently replace a required public release with a private artifact.

Full retirement means no supported current command, dispatcher, producer or
client API for either retired feature after the fleet checkpoint. Historical
receipts, frozen contract bytes, immutable releases and bounded rollback inputs
remain evidence/recovery material. Their retention does not advertise current
support. Do not modify or purge old wheels to erase their historical entrypoints.

## Planning baseline and independent selections

Use the [integration map](evidence/2026-10-22-ecosystem-realignment/integration-map.json)
and refresh exact heads, ownership and installed selections at M0. Reviewed
local heads are Mesh b0495b8, Observer 488100e, SSH Plus 11d6be1, Agent Plus
3b11f50, Tmux Observer db63675 and Tmux Plus 0bc11ba. RLCD's selected-source
proof tree is 629af372; its current main is a different input and needs its own
review. Those references are planning inputs, not acceptance of new bytes.

Mesh and Observer extend remote main linearly by 107 and 111 commits at this
review. The released a24/a8 lineage already contains retained gated research.
Commit count alone is not a reason to rebuild that lineage. Prefer a reviewed
local promotion candidate, with explicit support/gate review and recovery refs.
Preserve all existing branches/worktrees; do not rewrite history, overwrite
released artifacts or enable delta/view-feed experiments during integration.

Chezmoi main was 7633b195 at review. Four uncommitted files contain the applied
directional-topology fix: AGENTS.md, docs/carbon-fleet-sync.md,
dot_config/rofi-ssh-plus/config.toml.tmpl and scripts/check. Include that delta
in candidate provenance and preserve it on every host. Snap also has concurrent
unrelated work; do not reset, stash, overwrite or commit it as part of this loop.

Keep runtime admission, outbound peer lists, available local sources and each
consumer's host/home selection independent. Adding a runtime host must not add
an outbound edge or dashboard row. Source and controlled route tests must prove
the forbidden Starship/Snap -> Carbon edges are never selected; verify allowed
edges from their owning hosts without constructing a test full mesh. Inspect
Carbon's local/outbound behavior through an explicit operator diagnostic, not
by registering Carbon as an automatic Starship/Snap read target.

## Ordered checkpoints

| Checkpoint | Work | Exit evidence |
| --- | --- | --- |
| M0 Baseline | Refresh source/artifact/consumer selections, topology, concurrent ownership and recovery inputs | Exact per-host/per-home role map, scoped changes and preservation baseline |
| M1 Maintained lineage | Prepare local main-promotion candidates from the released lineages and prior loop commits | Reviewed commit sets, dark gates intact, owning baseline gates pass; no remote ref update |
| M2 Read usability and shared code | Add bounded working-set CLI inspection; extract the common validation/receipt helpers needed by surviving paths | Public-read-only CLI; unchanged full/working-set semantics and schema bytes |
| M3 Consumer migration | Remove active-only dependencies from current consumers, defaults, manifests, tooling and current docs | Effective configurations and consumer tests use working-set/full as intended |
| M4 Source retirement and artifacts | Remove writer and standalone active-only runtime surfaces; qualify fresh immutable package/consumer tuples | Owning source, contract, wheel and consumer gates; explicit unsupported old routes |
| M5 Managed retirement | Stage reviewed artifacts, remove selected legacy commands/hosting and adopt replacement collector/client selections | Scoped convergence on all three hosts; working-set/full/Tmux/native entry preserved; recovery tested |
| M6 Closeout | Record maintained-source candidates, retired surfaces, artifact/host results and publication dependencies | Requirement audit, exact commits/digests, complete or explicitly unaccepted checkpoint status |

No required checkpoint is complete merely because its source is committed.
M1 prepares local integration candidates; actual protected-main ref changes
follow the authorized integration scope. A public-main/hosted-CI success is not
claimed from a local gate. Tmux a9 currently has no hosted v0.6.0a9 tag while
its CI recipe expects one; resolve its qualified supply before claiming public
Tmux promotion, or record that promotion as outside the adopted endpoint.

### M0-M1: refresh once and establish the maintained base

Record selected collector, full reader/publisher, working-set publisher per home,
active publisher, writer, Tmux, authority and dashboard tuples independently.
Identify the exact consumers and processes that will change; native sessions,
TUI/window ownership, SSH history and unrelated services are protected.

The user has resolved the retirement policy; do not repeat an open-ended search
for hypothetical manual callers. Trace concrete current callers/defaults and
catch discrepancies. An identified required consumer absent from this plan
needs a migration or a bounded scope decision before its affected removal.

Keep source/module evidence, selected immutable artifacts, running processes
and physical device behavior separate. Refresh live state before any actual
apply; earlier source-loop and directional-fix receipts are dated baselines.

### M2: working-set CLI and common-helper extraction

Use existing public Service/Observer/Mesh interfaces. Scope a cached working-set
list and bounded watch, with explicit host/home/source selection and useful human
output for current members, active/recent membership, coverage, uncertainty and
delivery failure. Reuse the accepted example's lifecycle cases. Do not duplicate
the existing full diagnostics or add a daemon, provider query, action or event
replay promise. Keep any machine output tied to an existing contract; a new
stable output schema requires its own reviewed contract.

If an active-only presentation filter is useful, derive it from current
working-set active-membership evidence. Do not recreate the retired active profile or
request a different window from the fixed 72-hour publisher. Loaded idle/waiting
sessions are active; generation phase and recent activity are separate facts.

Working-set currently imports active_contract helpers through its contract,
support table, ledger, read facade and profile. Retained dark sync code also
imports that module. Produce a dependency inventory, then extract necessary pure
identity/receipt/validation definitions into a neutral common module before
deleting the active-only implementation. Preserve resulting schema bytes,
receipt identity, error meanings, bounds and clocks. Audit active_feed helpers
for the same issue. Do not leave the old feature operational just to keep shared
imports working, and do not delete shared definitions by filename or grep count.

### M3-M4: migrate consumers, then withdraw capabilities

The dashboard's base manifest still names the active profile, while both selected
host overrides name working-set. Resolve the base default, effective per-host
profiles, current tools/tests and rollback selections before withdrawal. Keep
the dashboard's loaded-user display policy and full-roster diagnostic behavior.
Historical active fixtures/receipts may remain explicitly historical; they are
not current supported consumers. Existing immutable bundles cannot be edited
in place to claim compatibility with changed SDKs. Where dependencies change,
qualify a new bundle from reviewed source and exact new artifacts.

| Owner | Retirement surface / preserved boundary |
| --- | --- |
| Observer writer | Remove write_client/write_contract implementation and the agent-observer-write package entrypoint, current helpers/support claims and all managed selectors including legacy fallback branches; native Codex/Claude commands, histories and Agent Plus entry remain |
| Observer active-only | Remove projector generation/cache, Service active request dispatch/API commands, Mesh active source/profile/read facade and publisher branch; retain the working-set active branch and shared pure semantics |
| Mesh | Withdraw active-profile advertisement and current runtime admission in the new package; old IDs fail explicitly before connection/dispatch, with no full/working-set alias |
| Chezmoi | Remove writerPrefix/current command selection, activeSelection/activeFeed hosting metadata, agent_active source, mesh-plus-active launcher, active shared-launcher dispatch, active unit and enablement link; update ignore/install/retirement hooks and checkers |
| Consumers | Migrate effective and inherited active-only defaults, scripts and current documentation; preserve independent host/home/view selections |

This is an intentional withdrawal of public prerelease capabilities, not a
wire-compatible rename. Record it in owner release/support notes. Review the
profile/capability withdrawal against the frozen lock before changing normative
inputs. Preserve accepted full/working-set/Tmux/Host Mesh identifiers and bytes;
never regenerate a lock to hide a mismatch. Retired historical definitions can
remain archival metadata, with no operational registration or advertised API.

Build fresh versions and digests; do not reuse released version/artifact names.
Test new wheels outside checkouts and preserve independent role pins unless
that role must change. In particular, do not upgrade Tmux or the full reader
merely to remove an old definition from an unrelated immutable environment.
Replace obsolete positive feature tests with explicit withdrawal/rejection
checks, retaining shared validation and surviving-product coverage. Archived
schemas and surviving active-membership reason names are not operational legacy
features; establish retirement from capability and dispatch inventories.

### M5: bounded managed retirement

On each host, capture exact selectors, owned files/units, enablement, relevant
PIDs/incarnations and consumer bundle manifests. Stage and verify packages before
selection. Review only the intended chezmoi status/diff/dry-run with umask 022.
Choose a pilot from fresh host evidence, then roll out the same qualified delta
to the other hosts. Preserve Snap Default/Work separation and Carbon's routes.

Migrate and verify consumers before stopping mesh-plus-agent-active.service.
Remove its default-target link, launcher/dispatch and obsolete runtime socket;
verify stopped/unenabled hosting and no automatic reactivation. Remove the
managed agent-observer-write command with explicit absence, rather than a
success-returning shim. Stop only exact owned retired processes; a collector
upgrade must preserve native provider sessions and account for read-service
incarnation changes. No native session control action is a retirement test.
Deleting a source template or adding an ignore entry is not installed cleanup.
Use explicit, idempotent removal of captured owned targets and enablement links;
stop for an unexpected replacement or a custom target instead of deleting it.
Render known and unknown-host cases to prove the old writer fallback cannot
reappear, without adding any cleanup effects on unowned/unknown hosts.

Prove ordinary services remain healthy and existing watches revoke/reacquire
after a changed collector. Verify effective installed/running bytes and consumer
behavior, not just a service's active state. Exercise captured rollback and
reselection on the pilot before broad rollout; keep rollback resurrection
temporary and explicit. Close with the retired state selected. Retain immutable
prefixes while another role or the recorded recovery set references them.

## Required acceptance and quick review

| Requirement | Proof / review result |
| --- | --- |
| Working-set covers the old active membership | Compare exact identities from the same accepted canonical input: every eligible current active member remains a working-set member even when activity is old/unknown or the recent clock is warming |
| Broader membership remains intentional | Recent unloaded rows remain eligible; old unloaded rows do not; expiry of the active branch can leave a row recent-only without retaining a current runtime claim |
| Source truth survives | Cover complete-empty, partial/unavailable scopes, quiet expiry, loaded idle/waiting, two homes, clock/incarnation changes and cancellation/sibling cleanup |
| Shared code survives removal | Working-set imports/schema digests/receipt rules and retained default-off experiments remain valid after neutral extraction |
| Retirement is complete | New installed package has no writer entrypoint or standalone active implementation/API; old active requests fail explicitly with no provider work or route fallback; managed hosting/commands stay absent after repeat apply and startup checks |
| Existing products survive | Full diagnostics, working-set/dashboard presentation, Tmux and native entry pass their affected source/artifact/consumer gates; no implicit version convergence |
| Topology survives | Render/check the directional graph including unknown hosts; verify each live reader's allowed scope and controlled rejection of forbidden routes without contacting them |
| Rollout is attributable | Separate source, wheel, consumer bundle, selected/running and GUI/device receipts; native actions, firmware and visual acceptance are not inferred from software fixtures |

Owning gates are Mesh scripts/check.py, Observer scripts/check with required
working-set support, affected SSH/Agent Plus/Tmux checks, RLCD SDK/bundle and
consumer tests, and chezmoi selection/retirement checks. New package bytes need
installed import/entrypoint checks; source fixture passes alone are insufficient.
Run focused documentation checks for this planning edit, not unchanged runtimes.

The quick review identified and addressed the sequencing risks: shared active
contract imports; different active/working-set wire formats despite membership
coverage; inherited dashboard defaults; legacy selector fallbacks and installed
cleanup; previously uncommitted directional policy; and private artifact supply
versus public-main/CI claims. No product decision
remains open for the two retirements. Exact new versions, deletion manifests,
pilot host and live targets are execution preflight outputs.

Stop the affected checkpoint for an unexplained semantic/schema change, a real
unmigrated consumer, owner conflict, failed source/artifact/consumer gate or
unexpected live delta. Preserve evidence and recovery inputs, fix the owning
bounded issue and rerun its affected checks. Continue independent authorized
work; do not declare retirement complete while a required host or consumer gate
is still unaccepted. Do not expand into failed capacity research or unrelated
cleanup to resolve a retirement checkpoint.
