# Maintenance and retirement execution status

Execution authorized 2026-10-23 against the
[maintenance plan](agent-ecosystem-maintenance-plan.md), including its bounded
fleet-retirement endpoint. Push, public publication, firmware and prefix purging
remain outside this run.

| Checkpoint | Status | Evidence / next work |
| --- | --- | --- |
| M0 Baseline | Source and two hosts captured; Carbon pending | Directional graph confirmed on Starship/Snap; Carbon operator SSH timed out |
| M1 Maintained lineage | Local candidates established | Isolated worktrees preserve released lineage, prior loop and topology fix; baseline owning gates pass |
| M2 Read usability / common code | In progress | Shared helpers extracted; 17 lifecycle and 4 CLI tests pass; local cached CLI smoke passes; full owning gate running |
| M3 Consumer migration | Pending | Dashboard already selects working-set with an independent SDK tuple; evaluate compatibility without an unnecessary bundle upgrade |
| M4 Source / artifacts | Pending | Withdraw writer and active-only dispatch after shared extraction is accepted |
| M5 Managed retirement | Pending | No live selection or service changes yet; Carbon required for full completion |
| M6 Closeout | Pending | Exact source/artifact/consumer/host acceptance required |

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
SSH failure. No provider query, native action or live mutation was performed.

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
