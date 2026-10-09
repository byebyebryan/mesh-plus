# SSH Plus integration and host authority migration

## Final ownership

Mesh Plus owns logical hosts, aliases, ordered routes, SSH policy, catalog revision
and background route-health reports. SSH Plus becomes a consumer of that authority
and retains its SSH picker, ad-hoc destinations, explicit connection history,
recent ordering, Forget behavior and terminal launch.

The catalog describes configured logical hosts. It does not discover a fleet
from `known_hosts`, history, DNS, provider rows or tmux names. Neither project owns
VPN, credentials, host keys or SSH configuration.

## Preserve the existing contract

Host Mesh v1 already separates route health from usage. Its wire behavior and
fixtures are the migration baseline. Preserve case-folding, alias ambiguity
rejection, deterministic route order, health demotion TTL, stale-revision report
guards and the configuration-only revision digest. A preferred fallback does
not become a new permanent preference.

`rofi-ssh-plus mesh list/report-route --json` remains a supported compatibility
facade delegating to the current single authority. It does not become a second
registry or route-health writer. Existing Tmux and Agent action clients can keep
calling that interface during read extraction.

The missing-executable local-only behavior remains explicit. A present malformed
or incompatible authority is an error. Local selection can still operate with
its configured local identity without fleet catalog access; fleet selection must
not silently turn into local-only success when its authority is missing.

## Staged ownership transfer

| Stage | Authority and state | Compatibility |
| --- | --- | --- |
| A | Mesh Plus consumes SSH Plus's existing Host Mesh v1 process API | No configuration/history changes; proves transport extraction first |
| B | Extract parser, identity model and route-health owner into Mesh Plus; retain existing config/state locations initially | SSH Plus mesh commands delegate to it; exact revision and fixture parity required |
| C | Optional canonical `mesh-plus/config.toml` migration after consumers pass | Explicit one-time migration, rollback and source selection; no dual live authority |

Stage C is optional. A directory rename is not required to establish component
ownership. During transfer there is one selected config and one state writer.
If new and old configs both exist, require an explicit selection or verify exact
equivalence under a recorded migration; do not silently merge them. Atomic private
state updates and advisory locks remain required.

Old SSH usage remains at SSH Plus's private history path. Moving route health
must not import usage as reachability or increment connection counts. Preserve
timestamps, counts, ad-hoc rows and rollback-readable history bytes.

The implementation now provides a source-tested Stage B authority candidate via
`mesh-plus mesh ... --json`; `hosts/read/watch --authority mesh` selects it
explicitly. The model/store retains the original paths and bytes. SSH Plus's
actual facade and operational artifact selection remain at Stage A until their
paired integration gate. See [checkpoint evidence](implementation-progress.md).

## Route reporting

The interactive SSH picker can continue recording a server that answers with an
authentication or host-key diagnostic under its existing usage rules. Background
Mesh reporting uses the stricter authenticated reached-wrapper marker. These
are intentionally different observations, and are not one generic "reachable"
classifier.

After the marker, source failure is a domain/availability result and stops route
selection. Before the marker, a positively classified transport failure may try
the next configured route and report unreachable. Authentication refusal and
host-key refusal do not demote network routes. Reports bind to the captured
catalog revision and original local observation time; a late stale report cannot
alter a replaced route definition.

The common bridge should adopt the published `ROFI_PLUS_REACHED_V1` marker while
preserving existing Tmux marker readers until their explicit adapter migration.
Do not change markers without conformance tests for exact nonce, duplicates,
fragmentation, missing marker and domain nonzero exit. Route tokens are private
diagnostics; full destinations need not appear in normal profile results.

## Acceptance

Run the released Host Mesh fixture corpus against both producer entry points.
Compare normalized revisions, route order, accepted/ignored reports and errors.
Exercise absent config, malformed config, ambiguous aliases, old/future reports
and restored preferred routes after TTL. Independently verify SSH picker history
preservation and shell/authentication behavior. Native SSH, Rofi and managed
deployment evidence remain separate from pure fixture parity.
