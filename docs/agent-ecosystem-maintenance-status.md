# Maintenance and retirement execution status

Execution authorized 2026-10-23 against the
[maintenance plan](agent-ecosystem-maintenance-plan.md), including its bounded
fleet-retirement endpoint. Push, public publication, firmware and prefix purging
remain outside this run.

| Checkpoint | Status | Evidence / next work |
| --- | --- | --- |
| M0 Baseline | Accepted | All three host/home and ownership baselines captured; Carbon completed after becoming reachable |
| M1 Maintained lineage | Accepted: local candidates established | Isolated worktrees preserve released lineage, prior loop and topology fix; baseline owning gates pass |
| M2 Read usability / common code | Accepted | Cached working-set list/watch and neutral projection helpers; 1,210-case owning gate and real cached CLI smoke pass |
| M3 Consumer migration | Accepted | Inherited defaults use working-set; 19 consumer cases and old installed dashboard SDK against new producer pass; live acceptance is recorded at M5 |
| M4 Source / artifacts | Accepted | Observer a9/Mesh a25 wheels; 1,138-case Observer gate, Mesh canonical gate, 49 Python 3.11 installed cases, installed-byte and capability checks pass |
| M5 Managed retirement | Accepted on all three hosts | New pair selected, legacy targets/hosting absent, repeat apply converged; Starship rollback/reselection passed; directional routes verified |
| M6 Closeout | Accepted | [Final acceptance](evidence/2026-10-23-maintenance-retirement/README.md) and requirement audit record exact provenance and the publication boundary |

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
The initial probe saved Starship/Snap baselines and Carbon's bounded SSH
failure; Carbon's fresh baseline followed when reachable. Baselines used no
provider query, native action or live mutation. Subsequent scoped live changes
are recorded in the acceptance receipt.

Mesh's baseline canonical gate and Observer's 1,206-case required-working-set
gate pass in a new isolated editable development environment with the correct
a24/a8 metadata. They establish a source baseline, not a new immutable artifact.

The existing dashboard's public a8/a24 lock and selected immutable bundle remain
independent after exact producer/consumer compatibility passed. An active
definition inside a retained immutable SDK is not an active selected producer.
No current public-release lock will be relabeled as a nonexistent publication.

## Final acceptance

Observer a9/Mesh a25 runs Starship Default, Snap Default/Work and Carbon
Default collector/working-set roles. All twelve managed legacy targets and the
three active sockets are absent. Repeat scoped apply/cleanup converges. The
Starship pilot exercised captured rollback and finished reselected/retired.
Full/Tmux/dashboard role selections and native identities at each apply were
preserved. Canonical source heads remain unchanged with reviewed owned deltas;
Snap's unrelated source/package work remains intact.

Carbon became reachable and completed its fresh baseline, exact staged pair,
scoped source/application and guarded retirement. Its local Codex feed was
unavailable with zero members before and after selection; this is preserved
negative evidence, not a claimed live native-session pass. Its outbound reads
of Starship, Snap Default and Snap Work pass with complete coverage. Starship
and Snap reject Carbon before any endpoint connection.

The [final receipt](evidence/2026-10-23-maintenance-retirement/README.md) and
[requirement audit](evidence/2026-10-23-maintenance-retirement/audit-coverage.json)
close M0-M6 within the adopted local-source/private-fleet endpoint. No push,
public publication, firmware/GUI acceptance or prefix purging was performed.
