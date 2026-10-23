# Maintenance and retirement execution status

Execution authorized 2026-10-23 against the
[maintenance plan](agent-ecosystem-maintenance-plan.md), including its bounded
fleet-retirement endpoint. Push, public publication, firmware and prefix purging
remain outside this run.

| Checkpoint | Status | Evidence / next work |
| --- | --- | --- |
| M0 Baseline | Source and two hosts captured; Carbon pending | Directional graph confirmed on Starship/Snap; Carbon operator SSH timed out |
| M1 Maintained lineage | Local candidates established | Isolated worktrees preserve released lineage, prior loop and topology fix; baseline owning gates pass |
| M2 Read usability / common code | Accepted | Cached working-set list/watch and neutral projection helpers; 1,210-case owning gate and real cached CLI smoke pass |
| M3 Consumer migration | Accepted in source/controlled consumer | Inherited dashboard defaults use working-set; 19 consumer cases and old installed dashboard SDK against new installed producer pass; live acceptance remains M5 |
| M4 Source / artifacts | Accepted | Observer a9/Mesh a25 wheels; 1,138-case Observer gate, Mesh canonical gate, 49 Python 3.11 installed cases, installed-byte and capability checks pass |
| M5 Managed retirement | Starship/Snap accepted; Carbon pending | New pair selected, legacy targets/hosting absent, repeat apply converged; Starship rollback/reselection passed; Carbon offline and unchanged |
| M6 Closeout | Two-host handoff recorded; full completion pending | [Acceptance and resume boundary](evidence/2026-10-23-maintenance-retirement/README.md); Carbon remains required |

## Inputs and ownership

Worktrees are Mesh, Observer, Chezmoi and RLCD under
`/home/bryan/code/<repo>-maintenance-20261023`, on
`maintenance-retirement-20261023`. Mesh starts at local plan commit 92202f0,
Observer 488100e, Chezmoi 7633b195 plus the four-file directional fix, and RLCD
aaeb32b (selected 629af372 plus the documented age-ticker delivery).

Original worktrees and all experimental branches remain intact. Snap's Chezmoi
source advanced independently to 34627be4 and retains an unrelated dirty package
manifest. Future sync must preserve those changes rather than resetting Snap to
the local source parent.

Private metadata receipts, logs and candidate staging are under
`/home/bryan/.cache/agent-ecosystem-maintenance-20261023/`.
The three-host probe saved Starship/Snap baselines and recorded Carbon's bounded
SSH failure. The baseline used no provider query, native action or live mutation. Subsequent
scoped live changes are recorded in the acceptance receipt.

Mesh's baseline canonical gate and Observer's 1,206-case required-working-set
gate pass in a new isolated editable development environment with the correct
a24/a8 metadata. They establish a source baseline, not a new immutable artifact.

The existing dashboard's public a8/a24 lock and selected immutable bundle can
remain independent if exact producer/consumer compatibility passes. An active
definition inside a retained immutable SDK is not an active selected producer.
No current public-release lock will be relabeled as a nonexistent publication.

## Refresh and acceptance

Update this ledger after each accepted bounded change. Capture fresh live
selectors, configuration, process births and provider-independent consumer
results before a scoped apply. Carbon's unavailable state cannot be counted as
retirement acceptance. The user has been asked to bring it online while source
work continues. Preserve the corrected graph throughout.

## Accepted live checkpoint

Observer a9/Mesh a25 now runs the Starship Default and Snap Default/Work
collector/working-set roles. Four legacy targets and the active socket are absent
on both hosts. Full/Tmux/dashboard roles and native sessions are preserved. The
Starship pilot exercised captured rollback and finished reselected/retired.
Canonical source heads remain unchanged with the reviewed owned deployment
delta retained; Snap's unrelated source/package work is preserved.

Carbon remains offline (Tailscale last seen 16:00 UTC; bounded SSH retries timed
out), with no source or live mutation. M5/M6 cannot be marked fully complete.
The [receipt](evidence/2026-10-23-maintenance-retirement/README.md) records exact
artifacts, source candidates, independent role pins, recovery and resume steps.
