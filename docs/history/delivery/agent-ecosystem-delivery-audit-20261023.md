# Ecosystem source, publication and managed-delivery audit

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Audited 2026-10-23 against current remote refs, GitHub release metadata and live
Starship/Snap/Carbon selectors and unit process paths. This is an audit and local
preparation pass; no push, release/tag, canonical-main ref or live selection was
changed. [Structured summary](../../evidence/2026-10-23-delivery-audit/summary.json).

## What is already delivered

The new runtime work is deployed through scoped chezmoi applications on all
three hosts. Observer 0.7.0a9 / Mesh 0.1.0a25 supplies Default collector and
working-set roles, plus Snap Work. Agent Plus 0.15.0a15 is selected on all three.
The directional peer policy and installed write/active retirement are applied.
Artifacts were staged privately before managed targets were applied.

The separately pinned full bridge remains a5/a20. Tmux's Mesh SDK and both
existing dashboard bundles remain a24 and a8/a24 respectively. Their independent
pins are intentional; public housekeeping does not require advancing them or
reflashing/rebuilding displays. [Live receipt](../../evidence/2026-10-23-delivery-audit/live-summary.json).

## Source and public supply

| Owner | Current relevant delivery | Remaining upstream work |
| --- | --- | --- |
| Mesh Plus | a25 in Observer collector/working-set prefixes on all hosts | Review candidate 06a305a is ahead of GitHub main; public release remains a24; publish exact qualified a25 assets |
| Agent Observer | a9 Default on all hosts and Snap Work | Review candidate 8f5af7f plus this audit's CI fix 158a952; public release remains a8; publish exact a9 assets and qualify current pair in hosted CI |
| Agent Plus | a15 selected on all three; cached removed-peer rows fixed | Four commits beyond GitHub main at 35eeada; no GitHub Releases; a15 is privately supplied |
| SSH Plus | Existing public archive plus directional policy in dotfiles | One source role/check-format commit at 11d6be1; this source delta needs no new runtime artifact |
| Tmux Observer | Privately supplied a9, exact wheel b117cc5d... | Four commits beyond main at db63675; public release remains a7; provide qualified a9 release supply |
| Tmux Plus | Privately supplied a8, qualified against Observer a9 | Three commits beyond main at 0bc11ba; public release remains a7; candidate CI requires the missing public Observer a9 wheel |
| Dotfiles | All live targets applied from reviewed source deltas | Three local commits at b3bcafc remain outside upstream main; integrate with upstream 34627be and reconcile canonical checkouts |
| RLCD | Existing bundle 164b7f99c40e7676 and wire 6 retained | One source cleanup/docs commit at 768b50d; no new device/runtime release is needed for that cleanup |

[Remote refs](../../evidence/2026-10-23-delivery-audit/remote-ref-audit.json),
[release assets](../../evidence/2026-10-23-delivery-audit/github-release-audit.json) and
[source deltas](../../evidence/2026-10-23-delivery-audit/source-delta-summary.json)
separate those states. The recorded candidate tips are not advertised by any
remote ref. The selected new version tags are absent.

Mesh and Observer are 112 and 115 commits ahead of GitHub main at the pre-audit
snapshot (Observer's CI fix adds one). This is not a count of wholly unpublished
work: the already published Mesh a24 and Observer a8 release commits are
ancestors of those candidates. The candidates are only 8 and 6 commits beyond
those published releases respectively. Main is behind the maintained release
lineage; promote that reviewed lineage rather than dropping it and replaying
only the latest patch. [Reachability proof](../../evidence/2026-10-23-delivery-audit/remote-reachability.json).

GitHub release metadata is the checked publication channel; these findings do
not assert an audit of unrelated package registries or forks. SSH Plus and Agent
Plus currently have no GitHub Releases, which is consistent with their existing
archive/private-wheel delivery rather than evidence that their source is absent.

## Canonical chezmoi gap

Starship/Carbon canonical main remains 7633b195; Snap main and upstream main are
34627be. All carry the applied, uncommitted ecosystem delta. Snap also retains
an unrelated package-manifest change. The reviewed local source commits exist
on isolated branches; they have not been integrated into those canonical heads.

A clean checkout of current GitHub dotfiles main still selects Observer a8 and
Agent Plus a14, includes writer/active hosting and derives full-mesh peers from
the runtime cohort. It does not reproduce the current fleet. Private artifact
staging and live managed application succeeded; durable upstream/canonical
source convergence is still unfinished.

The prepared integration candidate is **8c630a8**, on
`delivery/canonical-source-20261023`, in
/home/bryan/code/chezmoi-delivery-audit-20261023. It preserves upstream's shared-
daemon subscription-fallback commit and our three reviewed commits. The merge
is conflict-free and the complete dotfiles gate passes. It includes no unrelated
uncommitted Snap package changes. Canonical heads/worktrees remain untouched.

## Delivery blockers checked and prepared

Observer's working-set CI job invokes scripts/check-mesh-release. That script
still imported the retired mesh_active_profile and attempted an active factory.
The exact installed a9 owner plus published a24 wheel reproduced the import
failure. Candidate **158a952**, on `delivery/ci-preparation-20261023`, removes
that stale consumer and checks full/working-set factories plus explicit retired
profile rejection. The real installed gate now passes, with no native/socket
I/O; the 1,138-case required-working-set gate, docs and lint pass. This changes
release tooling/CI naming, not qualified runtime wheel bytes.

Observer's hosted working-set job still targets the published a24 SDK. Preserve
that useful compatibility proof, and add/qualify the selected a25 path when its
public assets are available. Local a9/a25 source, installed-wheel and live
qualification already exists; it is not a hosted-CI result.

Tmux Plus's candidate workflow constructs a v0.6.0a9 Observer release URL and
checks the exact pinned wheel digest. No such tag/release exists, so that
candidate cannot acquire its dependency on a clean hosted runner. Publish the
already qualified exact Tmux Observer wheel before claiming Tmux Plus hosted
adoption. Do not replace its checksum or relax that gate merely to pass CI.

## Recommended closure order

1. Promote reviewed source lineages using fresh remote-head checks. Preserve
   research gates, historical refs and separately owned worktrees. Use the
   prepared Observer CI and merged dotfiles candidates.
2. Publish the qualified immutable Mesh a25, Observer a9 and Agent Plus a15
   payloads with their actual runtime-source and qualification provenance.
   Mesh supply precedes the Observer pair's hosted qualification. Do not
   regenerate or overwrite an installed artifact to make it match a tag tip.
3. Supply the exact private Tmux Observer a9 wheel, then qualify/publish the
   pinned Tmux Plus a8 payload. Preserve the installed full-view/a24 route;
   this does not enable delta/view-feed research.
4. Push the integrated dotfiles selection and reconcile each canonical checkout
   against exact owned preimages. Preserve Snap's unrelated dirty package and
   upstream Codex work. Document/test acquisition of the published artifacts
   through the owners' staging/install paths; existing offline hooks remain
   checksum guarded.
5. Use scoped chezmoi status/diff/dry-run/apply for this work's targets and prove
   convergence. The live fleet already has the qualified behavior, so this is
   source/supply convergence, not a reason to restart native clients, advance
   unrelated roles or flash devices. Record unrelated upstream/live drift
   separately rather than bulk-applying it.

The earlier maintenance endpoint explicitly excluded public push/publication
and protected-main promotion. This pass makes the remaining closure concrete;
those external actions have not been performed. Exact private logs, installed
CI before/after receipts and merged-source checks are retained under
/home/bryan/.cache/agent-ecosystem-delivery-audit-20261023.
