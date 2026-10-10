# Hardening adoption on Snap and Starship

Checkpoint: 2026-10-10. Paired selection, live recovery, rollback and reselection
pass. Final ten-minute cached resources and installed SSH/Tmux closure pass;
Agent cached local/fleet delivery passes separately. Agent Plus migration is excluded.
The [artifact checkpoint](../2026-10-10-hardening-artifacts/README.md) binds
publication, isolated package gates and accepted production-budget lifetimes.
The [completion audit](../2026-10-10-hardening-artifacts/completion-audit.md)
retains all required gates and exclusions.

## Exact selection

Managed source is committed revision `5ff8b412a45b69cac64b8eb356444e6cf0705012`.
Starship uses its separate clean export; its foreign chezmoi checkout retains
its captured HEAD, status and private source hashes. Nine intended targets are
applied on each endpoint. Baseline payload/control archives remain private.

| Role | Selected artifact | SHA-256 |
| --- | --- | --- |
| Public Mesh CLI / transport | 0.1.0a10, source `3684fe083c0ab5af3c74aa27dff169e5764489f5` | `c9fecd77e3ea181d43447784824616232874cfc9ead12a30460d0682bdc3684d` |
| Tmux Observer | 0.6.0a5, source `5d8b7234ba10920beb59bde35c2f79c73d382b25` | `958d2f5381d57f172294e35654e19c96770ccd38e7ef8421a23f3dcf00abe536` |
| Tmux Plus managed bundle | 0.12.0a5, source `8d5242ac3b5252028803a982e70d8215613d5010` | `07df66c71e0684987dcd10ca524a5ecf72d583b3802be024ab3e64acf73947b6` |
| Separate Agent reader and bridge environments | 0.5.0a16, source `301b57a6eb12bacde220603d47c21995548bb7b6`, each with Mesh a10 | `94705baebfa51a9664e9dbfa7603dcb932d6301146cf9a59017017c5285b3b17` |

Agent's ordinary 0.5.0a15 collector and 0.4.0a16 writer remain independently
selected, with unchanged protected processes/configuration and package bytes.
SSH Plus remains at `e01f89cfdb7b068f6b2150b33a96dbce1b5c328f` with its separate
unversioned shared authority SDK a6 root. Its reviewed authority bytes and
history/config ownership are unchanged. Actual Agent Plus remains the independently
selected versioned 0.14.0a1 pilot (`8ba19a0eba87944aec2848542fb3ddcb91f3ccc33790ba42565928e18daa497b`
wheel SHA-256), outside the legacy extension directory. Its source and package
selection are untouched. The held `6d30f8c71a9e44ba1da19f4102292f6811df50d8`
source clone is only a historical/synthetic compatibility input; it does not
represent the installed consumer or establish its newer Observer compatibility.

## Live phases

Initial selection verifies exact installed payloads, Agent role archives and
rendered controls, kernel IPC peer/unit identity, entry/interpreter identity,
fresh cached Tmux local/fleet delivery and Agent local/fleet delivery.
Snap retains no managed desktop/Fleet context. Starship retains its captured
desktop context. Prepared reader reports compare against its original context.

Live recovery replaces both owned owner/bridge incarnations. Starship also
changes its prepared reader ID and restores fresh cached delivery. The paired
rollback restores the exact old a9 / Tmux a4 / Plus a4 / Agent a13-reader and
a12-bridge selection and passes fresh reads on both endpoints. Reselection
restores the new cohort and repeats all these artifact, cache and preservation
checks. The original selected receipts are copied before fixed output names
are reused; `initial-selection-*` distinguishes them from final selection.

Every phase preserves baseline native server generation, session creation
references and global/preexisting session hooks. New native sessions would be
allowed, but lost/replaced references fail. Ordinary collector/writer controls,
incarnations and package bytes, and foreign managed source, remain protected.
Raw native frames, control definitions and hook contents remain private;
published receipts contain hashes/counts and process/reader identities only.

The first Snap attempt is retained as a checker-readiness rejection in the
artifact checkpoint. The refined helper waits for the existing bounded native
ready gate before its kernel peer assertion. Original helper bytes and prior
offline receipts are preserved. This refinement does not change runtime wire,
schemas, source receipts or normative lock inputs.

## Final gates and limits

The public source/contract and synthetic PATH gate passes against the selected
Observer a5 root. SSH passes 82 tests, Tmux Plus 293, held Agent Plus 320 with
four explicit skips. This does not certify installed live lifecycle or Agent
Plus migration. The legacy all-picker live gate rejects the versioned Agent
Plus package before lifecycle. Its old Tmux Tab callback check also rejects the
new native picker presentation. Both are retained in
[the negative receipt](legacy-picker-live-negative.json); neither gate was
forced to accept a different contract or package.

The scoped [installed checker](check-installed-ssh-tmux.py) reuses canonical
Host Mesh, Tmux inventory, SSH callback/history and exact-reference lifecycle
checks. It passes from [Snap](snap/picker-live-scoped.json) and
[Starship](starship/picker-live-scoped.json). Disposable create/duplicate/rename/
stale-kill/kill passes across both advertised hosts, with SSH history unchanged.
The supported installed native/headless Plus candidate checks remain separately
recorded in the artifact checkpoint. Agent Plus still requires its independent
reader/cache/transport migration; its existing pilot is not certified here.

[Final cached resources](resources-selected-headless.json) pass a full 600-second
owned headless delivery profile after selection: Snap 4.31% CPU / 82.37 MiB
combined fleet-and-bridge / 24.69 MiB owner; Starship 2.50% / 82.45 MiB /
23.43 MiB. Original limits remain 5% / 96 MiB / 64 MiB. This is an installed
artifact profile with private fixture units, not managed desktop CPU acceptance;
sampled memory can miss peaks. Raw frames and process samples remain private,
with input hashes/counts retained and gate aggregates unchanged. Final passive
checks after lifecycle preserve the original seven Snap and six Starship
sessions, server generations and hooks, with no added references.

Physical suspend/wake, graphical input/focus, positive viewer matching and
provider-resume acceptance are excluded. This record does not upgrade passive
desktop service/context checks into physical desktop acceptance. Pooling,
digest-proof, WSS, ordered replay and further consumers remain separate work.
