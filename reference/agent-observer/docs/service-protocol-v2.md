# Local service protocol 2

Date: 2026-10-09. Prerelease read contract, accepted for the installed Codex
[a5 candidate](evidence/2026-10-08-codex-observation-completion/REPORT.md).
The current [a11 checkpoint](evidence/2026-10-09-runtime-only-retention/REPORT.md)
selects normal read services with the same protocol. Protocol 2 embeds API 2 snapshot wire 4
and rejects protocol 1; there is no converter or automatic direct fallback.
The [Claude read-contract review](claude-read-contract-review.md) settles
interactive Claude's fit within this envelope; a9 independently accepts its
producer/native and scoped operational gates.

The pure `agent_observer.service_public` facade exports the descriptor,
request/frame schemas, bounded parsers, validators and `StreamGuard`.
It imports no provider adapter or action implementation. The local transport
`agent_observer.service_client.frames` also checks endpoint/peer ownership,
host/user/source scope, boot/time namespace and source lease validity on receipt.

One newline-framed request per connection selects only `status`, `snapshot` or
`watch` and the expected host scope:

```json
{"serviceProtocol":2,"operation":"watch","hostScope":"snap"}
```

Subscribers cannot select provider stores, force a refresh, change cadence,
start a publisher/provider or request actions. The endpoint is a same-user Unix
socket in an owned private directory. Same-user credentials establish local
access, not host-name attestation or provider event truth.

Frames bind a service UUID, kernel boot UUID, BOOTTIME/time-namespace clock
domain, UID, host scope and configured sources. `sequence` starts at one per
connection; `viewRevision` is monotonic within the service incarnation.
Reconnect requires a new `StreamGuard` and a complete initial view. Publisher
restart changes service identity. There is no durable/native event replay.

| Frame kind | Embedded snapshot |
| --- | --- |
| view, resync | required wire-4 snapshot |
| status | current snapshot or null during warm-up |
| heartbeat, gap, error | null |

A warming null snapshot is not complete empty discovery. A gap requires a
replacement resync before consuming another view. Readers may skip samples with
explicit gap/resync or be disconnected when slow. A view revision does not
establish a distinct native state episode or guaranteed completion notification.

Each source has independent runtime/history receipts: attempt/accept counts,
sample-start and expiry BOOTTIME milliseconds, health, finite result and in-flight
state. Sample age includes read duration. Known current facts expire before
publication; failure, expiry or incarnation change preserves uncertainty and
original native event clocks. Heartbeats, cached requests and reader arrival
never renew collected evidence or conversation age.

Native runtime evidence obtained during metadata work is accepted under the
runtime lease/order rules. Metadata-only work cannot renew runtime. Parked has
phase null only while the adapter's reviewed native predicate and positive saved
identity are established under a current runtime receipt. For Codex this uses
current native `notLoaded`; Claude has its separately declared predicate/scope.
Expiry produces unknown runtime/phase with last-known parked evidence. Direct,
cached pull and cached push share the classifier described in
[API 2](api-v2.md).

Partial runtime coverage can coexist with current scoped row facts. No new
service component or envelope is needed for Claude's registration assumption.
Its runtime refresh may prove exact saved identity without renewing the slower
catalog/title/activity receipt. A stale history component invalidates its current
coverage/enrichment; it does not invalidate independently current runtime evidence.
This does not let a consumer infer parked from a missing row, warming view or gap.

Disappeared unsaved rows can remain stale unknown only until their original
accepted runtime lease expires. Partial receipts, history enrichment and
heartbeats cannot extend that retention deadline. Current rows and positive
saved identities remain protected. Expiry removes unsaved memory from both
component caches and the next complete pushed view; it supplies no native
lifecycle event or action permission. Conversation clocks remain unchanged.

Custom host-local consumers must account for elapsed BOOTTIME and matching
boot/time scope, stop current claims on expired leases or transport silence,
and conservatively invalidate a source at the earliest expiry among its
currently current/partial components unless a newly projected view is received.
An already-stale component does not schedule another current deadline. Forwarding
to another host requires separately conservative source-age accounting; receipt
arrival must not reset event age. Networking is outside this contract.

Requests are bounded to 16 KiB. Frames allow the 8 MiB observation limit plus
16 KiB envelope overhead. Duplicate keys, malformed encoding/framing, excessive
depth/nodes, nonfinite values, unsupported versions and scope/lease conflicts
fail with content-free codes. Structural schema checks require semantic
validation too. Do not pass a service envelope to the standalone snapshot/watch
parser: validate the envelope/stream first, then consume its snapshot when present.
