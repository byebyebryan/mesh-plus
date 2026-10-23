# Agent ecosystem execution status

Execution authorized 2026-10-23 through the source/artifact endpoint in
[the plan](agent-ecosystem-realignment-plan.md). Push, publication, fleet changes,
live retirement and firmware changes remain separately scoped.

## Current checkpoint

Checkpoint 2 in progress. Luna Max owns the bounded utility example, its guide
and focused tests in the isolated Observer worktree. Primary owns six-repository
current-state documentation, host/consumer acceptance, dashboard compatibility,
integration, final gates and this ledger. No deployed/runtime selection changes.

| Checkpoint | Status | Evidence / next acceptance |
| --- | --- | --- |
| 0 Current state / consumers | Accepted | Source census reviewed/corrected; read-only snapshots on all three hosts |
| 1 Ownership / capabilities | Accepted | Existing authority split preserved; user direction reflected in owner docs |
| 2 Utility read path | In progress | Luna example/guide/tests; primary existing-dashboard compatibility |
| 3 Justified simplification | Decisions accepted; packet pending | Retain full, active, writer and Tmux roles; unknown manual uses prevent retirement |
| 4 Documentation / integration | Drafted; gates pending | Six current landing pages and existing AGENTS aligned; exact integration packet follows commits |
| 5 Qualification / handoff | In progress | Selected dashboard immutable verification passes; owning gates follow |

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
  source 629af3721b9ffc6218060c839d22472cf1b808e0. No RLCD source edits planned.

## Current review and verification

- Luna's initial utility passed seven focused tests; primary found and returned
  an outer-timeout/quiet-tick race. The corrected thirteen-test slice passes on
  Python 3.11/3.14, including a real configured-reader quiet-expiry regression.
  The first full Observer gate passes with the required working-set SDK.
  Outside-checkout smoke then exposed a local timeout boundary using the real
  public ContractError type; Luna is correcting that last edge case before
  another focused/owning gate and actual local smoke. Keep checkpoint 2 open.
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
- Four accepted local commits are complete (not pushed): Agent Plus `3b11f50`,
  SSH Plus `11d6be1`, Tmux Observer `db63675`, Tmux Plus `e7c0e80`. A final
  focused doc review corrected Tmux's current SDK paragraph and aligned
  Observer roadmap wording; links and whitespace pass. Original source trees
  and remote main refs remain untouched.

## Restart procedure

Read this ledger and the plan, inspect outstanding Luna messages, refresh goal
status and repository heads/dirty state, then resume the current checkpoint.
Inspect actual partial diffs before editing a worker-owned file. Keep raw
provider payloads, prompts, conversation content and credentials out of evidence.
