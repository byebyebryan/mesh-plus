# Host authority and SSH Plus

Mesh Plus owns the shared logical host and route implementation. SSH Plus owns
the canonical Host Mesh v1 contract/facade and its picker/history policy.
The [Host Mesh specification](https://github.com/byebyebryan/rofi-ssh-plus/blob/main/docs/reference/host-mesh-v1.md)
defines configuration, CLI envelopes, revision guards and route reports.

## One configured authority

Logical hosts, aliases, ordered routes, SSH policy, catalog revisions and route
health come from one selected authority. Both `rofi-ssh-plus mesh ... --json`
and the supported native `mesh-plus mesh ...` facade use that authority.
The existing SSH-named config/state locations remain valid; there is no silent
merge, directory migration or second registry. SSH usage history stays private
to the picker and never becomes route health.

The Mesh backend is SSH Plus's default; explicit
`ROFI_SSH_PLUS_MESH_BACKEND=legacy` selects the standalone rollback backend.
A missing or incompatible selected backend produces a typed error without
automatic fallback. Backend selection is distinct from an installed artifact.

## Directional scope

Catalogs are endpoint-specific. An allowed outgoing route grants no reverse
route, and observing a remote row does not add its host to authority. For example,
an endpoint may read two peers while only those peers read each other.
History, DNS, `known_hosts`, hostnames and incoming SSH do not discover a fleet.

Preserve case-folding, ambiguity rejection, deterministic route order, temporary
health demotion, stale-revision guards and configuration-only revision digests.
Route-health reports do not permanently rewrite configured preference.

## Reporting and failure

SSH picker usage can record a server answering with authentication/host-key
diagnostics under its own policy. Background delivery uses the authenticated
reached-wrapper marker. After that marker, domain failure is not transport
failure and does not try another route. Authentication/host-key refusal must
not demote a route as a network failure.

Reports bind the captured catalog revision and original local observation time.
Late reports cannot mutate a replaced route. Preserve bounded parsing,
nonce/marker validation, locks and atomic private state updates.

## Acceptance and selections

Run Host Mesh conformance against each public boundary and independently verify
picker history and terminal behavior when those change. Native SSH, installed
bytes, Rofi and managed recovery require separate evidence. The deployment
owner records the authority's selected version independently of Agent/Tmux
state-delivery SDKs; see [operations](../maintenance/operations.md).
