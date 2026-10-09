# Mesh delivery candidate 1

This is an experimental outer delivery protocol, not a published Observer API
or an implemented Mesh server. The protocol discriminator is
`mesh-plus.delivery-candidate.v1`; `version` is 1. Domain profile versions are
independent. [Transport architecture](../../docs/transport-design.md) defines
ownership, topology, source integration and backend selection.

## Channels and framing

One logical channel binds one authenticated host, configured source, product
(`state` or `events`) and profile. IPC and SSH use one compact UTF-8 JSON value
per LF-terminated line. WSS uses one UTF-8 text message containing that same
value, with subprotocol `mesh-plus.delivery-candidate.v1`; no trailing LF is
required in a WebSocket message. WebSocket fragmentation is reassembled and
bounded before application parsing. A TCP/SSH read boundary is not a frame.

Reject duplicate JSON keys, nonfinite numbers, BOM, invalid UTF-8, NUL, unpaired
surrogates, unsupported versions and unknown outer fields. Domain payloads are
validated by the negotiated source codec; an outer `payload: object` is not
acceptance of arbitrary provider data. The design parser has a 64-level depth
bound; production parsing/decoded-memory limits need the native profile's
independent admission gate.

Maximum message size is negotiated downward, never above 8 MiB + 80 KiB per
owner channel: Agent's 8 MiB + 16 KiB source-frame allowance plus a separate
64 KiB Mesh wrapping reserve. Requests, controls, hello and metadata are at most 64 KiB; native
payload limits still apply. Credit counts the actual encoded JSON octets,
excluding a stream LF or WebSocket/SSH/TLS overhead. A sender cannot evade byte
credit by changing whitespace. The model accepts an explicit received byte
count; carrier experiments pass that count rather than re-encoding for credit.

Each direction has its own consecutive frame sequence starting at hello=1.
The server assigns a fresh channel UUID. Every later frame binds it. Native
source incarnation, view revision, event cursor and per-subscription sequence
remain independent. Reconnect negotiates a new channel and rejects late frames.

## Hello and capability negotiation

[Client schema](client-frame.schema.json) and [server schema](server-frame.schema.json)
define strict frame variants. A client hello supplies an unpredictable nonce,
expected host, configured source ID, product, profile, required capabilities and
limits. A server hello echoes those bindings and returns a channel UUID, its
capabilities and accepted limits. Bind the returned host to the authenticated
route, not merely to a self-reported label.

Capabilities are `snapshot`, `proof`, `subscribe`, `digest-proof`, `status` and
`replay`. An absent required capability terminates setup with a typed error;
never silently change a subscription into periodic polling. State initially
supports snapshot/proof/subscribe. Events may support status/subscribe/replay
only after an accepted producer contract. An initial pre-hello setup failure is
reported by the backend's typed setup outcome, outside an established frame
sequence; an established channel uses its error frame.

The [endpoint candidate](endpoint.schema.json) binds registry revision,
endpoint identity, host/source/product/profile, backend address and an opaque
configured auth reference. It contains no credentials. IPC must be same-host;
SSH references a published Host Mesh revision/route token; WSS requires a
configured `wss://` endpoint without inline credentials or fragments. This is
separate from the SSH-specific Host Mesh v1 schema and is not an implemented
catalog authority or independently authenticated machine attestation.

## Request/reply

`request` has a channel-scoped request ID, allowlisted operation, relative
timeout budget and profile parameters. The initial operations are cached
`snapshot`/`proof` for state and `status` for events. The caller starts an
absolute suspend-aware local deadline when dispatch is queued; the relative
remote budget is an additional bound, not authority to extend the local timer.

`result` echoes the request ID and returns exactly one successful payload or
typed error. IDs are never reused. A late result after local timeout or cancel
is quarantined in the original ID, not accepted into another request. Remote
timeout/cancel does not prove a provider operation stopped; these methods do
not collect or dispatch actions. A terminal result/ended barrier prohibits
further messages for that handle.

## Subscription and cancellation

`subscribe` provides a unique subscription ID, start mode and initial credit.
State start is `baseline`, with null cursor. Event starts are `live`, `retained`
or `after`; only `after` carries the exact producer cursor. `subscribed` echoes
the requested start and includes the producer baseline/replay barrier and epoch.
Data cannot precede that barrier. A changed requested start is a protocol error,
not a permitted shortcut to live delivery.

`data` carries subscription ID, consecutive stream sequence, publisher epoch,
delivery kind, cursor and exact domain payload. State kinds are `view`/`resync`,
with null event cursor. Event kind is `event`, with the validated native cursor.
These are outer delivery distinctions, not new Tmux/Agent native event kinds.

`cancel` targets one request or subscription. The local client stops exposing
that handle immediately; frames already in flight may be validated and drained
but are quarantined. The server completes any started frame then returns
`ended`; later data is a violation. Sibling handles continue. Handle tables and
tombstones are bounded; drain and rotate after 4096 total handles in a channel.

`control` carries subscription heartbeat, gap, source status or checkpoint.
Each subscription control advances its stream sequence. Channel heartbeat has
null subscription/stream sequence and an empty payload. A heartbeat carries no
source receipts. Native source-status and event checkpoint payloads require
their domain validators; neither supplies work/lifecycle authority.

On state gap, revoke current claims and require a full resync with source proof.
On event gap, report the last accepted cursor and end that subscription; a
new explicit start/resume may recover a retained suffix. A state resync cannot
clear event loss. A publisher restart or expired cursor never silently becomes
a new live feed. There is no replay or global ordering promise across hosts.

## Credit and buffering

Each subscription advertises cumulative frame and encoded-byte totals. A
`credit` update can repeat or increase those ceilings, never decrease them.
Data consumes one frame and its actual JSON length. Repeated credit cannot
double a grant. Initial outstanding credit and later unconsumed windows are
bounded at 32 frames and twice the maximum owner message size. Credit is not
durability, notification acknowledgment or exactly-once application processing.

Controls use a separately bounded 64 KiB channel reserve so a gap/cancel is not
blocked solely by exhausted data credit. Failure to drain even that reserve
closes the channel. Per-subscriber unsent state/event queues and aggregate
application/transport budgets remain mandatory even with credit or SSH/HTTP2
flow control. See [queue policy](../../docs/transport-design.md#flow-control-and-failure-isolation).

## Optional compact state proof

[Digest-proof schema](digest-proof.schema.json) is the success payload of a
negotiated state proof request with unpredictable nonce and known full owner
frame digest. It carries host/configured source, owner incarnation, clock,
evaluation time and the entire original component receipt map with remaining
validity. The client must already possess and validate that exact owner frame.

The bridge must validate a cached read after the nonce and prove the retained
frame is still the same source version. A changed owner/clock/view/receipt,
missing source or inability to prove equivalence returns a full replacement or
failure. Only adapter-proved delivery-only fields may differ between reads;
immutable records and original receipts are unchanged. The fixture oracle's
`sequence`/`encodedAt` exclusions are synthetic, not a generic native allowlist.

Compute expiry from whole request RTT and original remaining leases with the
existing margin/deadline policy. Compact proof saves the second payload copy;
it adds no new clock synchronization assumption and does not remove the round
trip. Nonce single-use and outstanding channel/epoch checks apply as in Mesh
Read 1. A retained frame with a live pipe but failed publisher cannot be renewed.

## What schemas and models establish

The executable [delivery check](../../scripts/check-delivery.py) validates
outer schemas, hostile parsing, bindings, interleaved poll/push, cancellation,
credits, replay/gap scenarios, proof equivalence and sharing keys. Event cursor
scenarios use an explicitly synthetic codec; they do not freeze Agent's future
event wire. The [carrier study](../../scripts/study-carriers.py) exercises
duplex request/push over owned synthetic endpoints, not native source passivity
or production resource/security acceptance.
