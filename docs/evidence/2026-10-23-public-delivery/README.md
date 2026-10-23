# Ecosystem public delivery closeout

Accepted 2026-10-23. This closes the source/publication/canonical gap identified
by the [pre-publication audit](../../agent-ecosystem-delivery-audit-20261023.md).
The [execution plan](../../agent-ecosystem-public-delivery-plan.md) and
[structured receipt](summary.json) separate source, artifact, canonical and
current-consumer evidence. Earlier dated private rollouts retain their original
scope; this record establishes the later public delivery.

## Public supply and source

| Product | Exact qualified public supply | Qualification source |
| --- | --- | --- |
| Mesh Plus | [0.1.0a25](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a25) wheel, manifest, provenance and checksums | `6b0fe54` |
| Agent Observer | [0.7.0a9](https://github.com/byebyebryan/agent-observer/releases/tag/v0.7.0a9) wheel, v6 manifest, owner verifier, producer lock and paired Mesh wheel | `6564d41` |
| Agent Plus | [0.15.0a15](https://github.com/byebyebryan/rofi-agent-plus/releases/tag/v0.15.0a15) wheel and candidate metadata | `35eeada` |
| Tmux Observer | [0.6.0a9](https://github.com/byebyebryan/tmux-observer/releases/tag/v0.6.0a9) wheel and candidate metadata | `13f6c9d` |
| Tmux Plus | [0.12.0a8](https://github.com/byebyebryan/rofi-tmux-plus/releases/tag/v0.12.0a8) exact Linux x86_64 bundle and candidate metadata | `c75cc92` |

All five releases are immutable prereleases. GitHub-signed release subjects,
uploaded inventory/digests/sizes and fresh downloads were verified against the
qualified bytes. No selected wheel or ZIP was rebuilt or replaced. Runtime
build revisions remain separate from later qualification/tag revisions.
Tmux Plus a8 is bundle-only; its historical inner-wheel digest is provenance,
with no standalone wheel download claim. Eighteen older releases and their 48
asset inventories/digests were preserved.

Reviewed source lineages were fast-forwarded to GitHub main in all eight owners:
the six ecosystem products, RLCD source cleanup and dotfiles. SSH Plus is
`05235fc`, RLCD is `768b50d`, and dotfiles is `22aaee1`; the five package owners
use the qualification revisions above. Mesh main additionally carries this
closeout documentation after its release qualification. Source roots and local
main refs were reconciled while retaining the Mesh/Observer research checkouts,
recovery refs, other worktrees and unselected research.

The hosted source and tag gates passed. Observer tests both Mesh a24 and a25 on
Python 3.11/3.14 and retains the a23 full-read compatibility gate. Tmux Plus's
hosted gate downloaded its exact newly published Observer a9 prerequisite.
Dotfiles has no hosted workflow; its full owning source gate passed locally.
Owning source coverage includes Mesh 480, Observer 1,138 plus 265 documentation
checks, Agent Plus 155, SSH Plus 82, Tmux Observer 405 and Tmux Plus 293 tests.

## Reproducible staging and canonical convergence

Dotfiles adds the known-host before-17 public artifact stage, before the existing
offline Agent Plus installer. It checks bounded HTTPS acquisition, exact sizes
and hashes, atomic no-replace cache writes, package inventory/bytes and the
read-only v6 Observer/Mesh owner verifier. Unknown hosts have no new staging
effects. Existing prefixes are verified in place. The known private/public
manifest-note difference is accepted semantically without changing installed
manifest bytes.

Real public downloads were used in an isolated home. Observer/Mesh cold install,
the owner pair verifier and the offline Agent Plus install passed. A repeat
bootstrap performed no network/install work; repeat installation preserved
bytes and modes. The test used the existing system Python and an available
Python 3.11 interpreter. A too-long initial fixture path was rejected because
uv produced a shell entrypoint shim; the accepted fixture used direct Python
entrypoints matching the managed home/prefix contract. The failed fixture was
retained privately.

Snap exposed legitimate uv hardlinked installed files. The final source allows
those only during read-only comparison with exact wheel bytes. Cache/artifact
reads retain the single-link guard. Positive installed-hardlink and negative
cache-hardlink tests passed, followed by the full source gate, repeated real
cold installation and actual Snap verification. No prefix was recreated.

| Host | Canonical chezmoi source | Scoped convergence | Retained unrelated work |
| --- | --- | --- | --- |
| Starship | `22aaee1`, clean | 16 targets; status/diff/dry-run empty, repeat apply converged | Research checkouts and one additional native client left untouched |
| Snap | `22aaee1` | 18 targets, including Work units; repeat apply converged | Only `.chezmoidata/packages.yaml` remains dirty, exact bytes preserved |
| Carbon | `22aaee1`, clean | 16 targets; repeat apply converged | Native defaults and existing role pins preserved |

Canonical reconciliation checked exact approved source preimages, kept source
and index recovery material, and rejected unreviewed edits in a controlled
transaction fixture. Managed apply excluded scripts and unrelated targets;
the two reviewed staging/install hooks were executed separately. Native/SSH
configuration, histories, selected files, all original 29 native process
identities and service identities were preserved. All 1,361 observed prefix
files/link targets/modes remained unchanged, excluding generated bytecode.
There were no service restart requests, provider actions or firmware changes.

## Current reads and preservation boundaries

Host Mesh rosters remain Starship-to-Snap, Snap-to-Starship, and
Carbon-to-Snap/Starship. Installed SDK attempts to read Carbon from Starship and
Snap returned `unknown_host` before any connection attempt. Operator SSH used
for this delivery does not grant an automatic Mesh route.

Current cached working-set CLI reads were complete for Starship Default and
Snap Default/Work. Carbon explicitly reported `partial / membership_incomplete`
with zero current/uncertain/nonmember entries. Carbon's cached Service 4 was
ready, schema 6, with two cached rows, complete saved/runtime coverage, no source
errors and current component leases. Only aggregate cached metadata was read;
no row content or native provider query was used to reconcile membership. A
complete-empty Carbon working-set result is not established, and no concrete
delivery regression was found. Native membership investigation is a separate
reopen trigger if that visibility is needed.

The existing immutable dashboard bundle `164b7f99c40e7676`, using Observer a8 /
Mesh a24, passed both working-set and full cached reads on Starship and Snap;
each owned reader closed. The independent full publisher stays a5/a20, Tmux
Mesh stays a24, dashboard SDKs stay a8/a24, and device wire/firmware are retained.
Writer and standalone active-only root commands, unit/link and socket remain
absent. Ordinary working-set active membership remains supported. Delta and
view-feed remain unselected. No GUI or physical-display acceptance is claimed.

Observer's PyPI dependency versions are exact, but dependency wheel hashes are
not individually pinned. Cold-install failure leaves a partial new prefix for
owner recovery rather than replacing it. These limits are documented in the
owning dotfiles bootstrap guide and do not reopen the completed exact artifact
publication or canonical-source reconciliation.

Luna prepared Tmux supply, corrected Observer CI portability/import order,
implemented and tested bootstrap/hardlink handling, and investigated Carbon's
cached state. The primary owned decisions, review, public source/CI/release
integration, signed/download verification, cold installation, canonical
transactions, scoped fleet convergence and final acceptance. P0-P6 are accepted
within the stated source/supply/current-read boundaries.
