# Agent ecosystem execution status

Execution authorized 2026-10-23 through the source/artifact endpoint in
[the plan](agent-ecosystem-realignment-plan.md). Push, publication, fleet changes,
live retirement and firmware changes remain separately scoped.

## Follow-up planning, 2026-10-23

The user has agreed to main following the maintained release lineage, a useful
working-set CLI, full Observer write-path retirement, and retirement of the
standalone active-only feed. The [follow-up plan](agent-ecosystem-maintenance-plan.md)
records sequencing, exact retirement surfaces, compatibility, topology and
acceptance. It supersedes the earlier unresolved/retain decisions for those
two features in future work; it does not change the first loop's receipts.

This turn updates and reviews the plan only. Follow-up implementation, builds,
main promotion and managed retirement have not started. The proposed full-loop
endpoint includes bounded fleet retirement after source/artifact/consumer gates;
the later execution request determines which checkpoints are authorized.

The intervening Host Mesh correction is an already completed, separate fix:
Starship lists Snap, Snap lists Starship, and Carbon lists both. Preserve its
four uncommitted chezmoi source changes and its applied topology. Future host
refreshes must distinguish this correction from the earlier full-mesh census.

## Current checkpoint

The agreed source/artifact endpoint is complete. Luna Max supplied the bounded
census and utility implementation/tests. Primary owned decisions, six-repository
documentation, review corrections, installed/host compatibility, integration and
acceptance. The [final handoff](evidence/2026-10-22-ecosystem-realignment/README.md)
records results and remaining publication/retirement boundaries.

| Checkpoint | Status | Evidence / next acceptance |
| --- | --- | --- |
| 0 Current state / consumers | Accepted | Source census reviewed/corrected; read-only snapshots on all three hosts |
| 1 Ownership / capabilities | Accepted | Existing authority split preserved; user direction reflected in owner docs |
| 2 Utility read path | Accepted | 17 focused tests per interpreter; final owning gate; six outside-checkout cases; dashboard consumer compatibility |
| 3 Justified simplification | Accepted | Retained-path decisions and concrete later retirement packets; no unsupported runtime deletion |
| 4 Documentation / integration | Accepted | Six current landing pages and existing AGENTS aligned; exact local commits/prerequisites recorded |
| 5 Qualification / handoff | Accepted | All six source gates; qualified example; 19 dashboard cases; three-host preservation audit |

## Baseline and decisions

- Mesh coordination worktree: ecosystem-plan-20261022, based on a32019b.
- Six inspected product source worktrees retain the plan's recorded heads and
  clean status at execution start. Existing branches will not be checked out or
  reset; code/documentation execution uses isolated worktrees.
- Goal created without an invented token budget. Luna Max completed the
  investigation-only census, then implemented the separately scoped utility.
- Preserve Host Mesh commands/config paths and frozen schemas. Full/active/
  working-set services and historical writer remain selected during this loop.
- User direction: native provider tools own session control; Agent Plus is entry
  and focus; Observer is Codex observation; Claude TUI entry remains independent;
  Tmux is maintained secondary tooling.
- Source-census review corrected the Tmux distinction: generic shared CLI a15;
  Tmux Reader SDK and dedicated bridge a24. SSH DESIGN's legacy-default claim
  is stale; current code defaults to Mesh. Both report corrections accepted.
- All three hosts run the retained publication and Tmux roles. Dashboard
  164b7f99c40e7676 is selected/running on Starship/Snap, using a8/a24. Its local
  immutable manifest verification passed; another candidate manifest is not
  treated as installed selection or physical evidence.
- Execution worktrees are `/home/bryan/code/<repo>-ecosystem-20261023` for the
  five non-Mesh projects, each on `ecosystem-realignment-20261023`. Mesh uses
  this coordination tree. Original source worktrees remain protected.
- RLCD compatibility-only detached tree:
  `/home/bryan/code/esp32-rlcd-ecosystem-proof-20261023`, at the exact selected
  source 629af3721b9ffc6218060c839d22472cf1b808e0. No RLCD source was edited.

## Current review and verification

- Primary review exposed a Mesh quiet-tick race; the first installed smoke then
  exposed a real public ContractError/local deadline boundary. Luna corrected
  both. The final 17-case focused suite passes on Python 3.11 and 3.14 with exact
  a8/a24 wheels. The final owning gate passes 1,206 tests with zero skips.
  Failed initial evidence remains separate; it is not reassigned to the fix.
- Six final outside-checkout cases pass against unchanged installed a8/a24
  packages. Snap Default/Work namespaces stay distinct, all final views revoke,
  and output excludes conversation content. Source unavailable states remain
  visible; success is not a claim of continuously healthy native sources.
- Agent Plus source gate passed. SSH source gate passed after a narrow,
  pre-existing formatting defect in `scripts/check-public-contract` was fixed.
  The defect also reproduces on the untouched original source.
- Tmux Plus source gate passed with the exact staged a9 wheel (digest verified)
  and declared Ruff 0.16.6. Tmux Observer source gate passed in an isolated
  editable source environment with its declared dev dependencies. The ordinary
  uv index returned 401; the explicit public-index environment avoids credential
  changes and leaves uv.lock untouched. Earlier missing-package setup failures
  are retained separately.
- Mesh's borrowed environment had a23 distribution metadata. In the matched
  installed a24 interpreter all 483 tests passed, then lint could not run because
  that runtime prefix has no Ruff. The complete isolated a24 editable dev
  environment now passes the canonical gate; no installed prefix is modified.
- Selected dashboard immutable verification passed. Nineteen existing
  working-set/prepared/two-home public consumer tests passed with zero skips,
  using the selected a8/a24 interpreter and selected source commit. These are
  controlled consumer fixtures, not native/provider or physical display proof.
- Runtime/contract parity compares 703 tracked files across the six protected
  originals and execution worktrees, with zero differences. Developer example,
  tests, docs and the SSH check-script formatting are separate changes.
- `decisions-and-rollout.md` records retained paths, concrete later retirement
  packets and an empty managed deployment delta. Main prerequisites: Mesh 105,
  Observer 110, Tmux Observer 3, Tmux Plus 1 commits; do not merge them implicitly.
  Tmux a9 is private; its missing hosted tag blocks the current public CI recipe,
  not this loop's local source/artifact endpoint.
- Detailed private logs and machine-readable gate receipts are under
  `/home/bryan/.cache/agent-ecosystem-realignment-20261023/validation/`.
- Accepted local commits are complete (not pushed): Agent Plus `3b11f50`,
  SSH Plus `11d6be1`, Tmux Observer `db63675`, Tmux Plus `e7c0e80` / `0bc11ba`, Observer
  `488100e`, and Mesh census/ownership `6a1daff` plus this closeout commit. A final
  focused doc review corrected Tmux's current SDK paragraph and aligned
  Observer roadmap wording; links and whitespace pass. Original source trees
  and remote main refs remain untouched.
- The final whole-documentation link audit found a retired Agent Plus navigation
  link in Tmux's historical plan. It now points to the verified pre-cleanup Git
  checkpoint; the historical design itself is unchanged.
- The final before/after audit reports zero selected-link/configuration changes
  and zero service PID/state changes across all three hosts. All 37 baseline
  native process birth identities were still observed. No apply, native action,
  provider query, firmware or installed-prefix change was performed.

## Restart procedure

For later work, read the final handoff and decisions/rollout packet, refresh the
relevant heads and effective host selections, then scope the next integration,
publication, runtime or retirement checkpoint. This source loop schedules no
automatic rollout. Preserve concurrent work and keep provider payloads,
conversation content and credentials out of evidence.
