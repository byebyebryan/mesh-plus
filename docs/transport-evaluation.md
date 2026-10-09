# Backend and protocol evaluation

Research date: 2026-10-09. These are primary-document findings and design
judgments for the current defined Linux fleet. They are not measured production
performance rankings. [Controlled experiments](transport-validation.md) have
a separate evidence scope.

## Requirements and selection

Required now: local/fleet API equivalence; cached request/reply; long-lived state
and eventual ordered-event subscriptions; authenticated host/user/source binding;
bounded memory; cancellation; independent host recovery; and explicit gaps.
Avoid changing native collection or requiring a centralized deployment to read
two already SSH-accessible hosts. Preserve multi-client and future device access.

The recommendation is **persistent SSH stdio first, local IPC throughout, WSS
as the preferred alternative**. Keep the application delivery protocol
independent of all three. Add a local service wrapper when multiple consumers
justify shared upstream channels. An external message broker is not required by
the present publish/subscribe requirement.

## Options compared

| Option | Request/reply and push | Deployment/auth | Main tradeoff | Disposition |
| --- | --- | --- | --- | --- |
| Unix IPC + JSON frames | Both over a persistent duplex channel | Same-user socket and peer credentials | Local only; library/daemon lifetime still needed | Initial local backend |
| SSH exec stdio + JSON frames | Both over an existing session channel | Existing sshd, keys, host keys, jump hosts; fixed bridge executable | Owned subprocesses, remote command deployment, reconnect/setup and duplicated channels | Initial remote backend |
| SSH forwarding to a Mesh endpoint | Both using the forwarded application's protocol | SSH plus an additional local endpoint/listener | Extra endpoint and forwarding lifetime; useful only if one already exists | Supported future composition, not initial default |
| WSS + Mesh JSON messages | Both over one duplex WebSocket | Mesh listener, TLS, client authentication and source ACLs | Removes remote shell startup; adds certificate/credential/listener operations | Preferred direct-network alternative |
| Length/line-framed TCP + TLS | Both over a duplex TLS stream | Mesh listener, TLS and source ACLs | Small carrier surface, but custom framing/integration and no HTTP ecosystem | Viable fallback if WSS integration adds unnecessary cost |
| HTTPS requests + SSE feed | Requests and downstream stream on separate HTTP exchanges | HTTP endpoint/auth, proxy behavior | Subscription/control/proof correlation split across channels; event ID is not native replay by itself | Possible browser facade, no core selection |
| gRPC unary + streaming | Unary requests and server/bidirectional streams | HTTP/2 service, auth, stubs/runtime | Strong RPC tooling, but another schema/runtime layer for existing Python/JSON consumers | Revisit for typed multi-language SDK demand |
| Core NATS / JetStream | Request-reply plus subject subscriptions; JetStream adds persistence | External broker, subjects/ACLs/credentials and retention operations | Natural many-to-many fanout; broker persistence changes event policy and payload limits | Revisit for central ingestion or durable offline feeds |
| MQTT 5 | Publish/subscribe plus response-topic correlation | Broker, topics/ACLs/credentials/session policy | Device-friendly; retained messages/QoS are not source freshness or native replay | Possible device edge integration |

These occupy different layers. SSH and TLS secure channels; WebSocket and gRPC
provide application carriage/RPC; NATS and MQTT add routing/broker semantics.
Do not turn the comparison into a single interchangeable `socket_type` enum.
An endpoint registry records backend capability and its authenticated source
mapping. A broker adapter, if selected later, needs its own topology and
end-to-end identity review.

## SSH findings

SSH supports multiplexed, flow-controlled channels, including remote command
sessions and forwarded connections. Session data and stderr are distinct channel
data classes. A persistent remote-command channel can carry requests toward the
bridge and publications back; push needs no additional connection per update.
[SSH channel/session specification](https://www.rfc-editor.org/rfc/rfc4254.html)

OpenSSH exposes remote execution, non-PTY mode, jump routes and connection
sharing. `ControlMaster`/control sockets can reuse authentication and the TCP
connection, but do not remove application subscriptions, remote bridge processes,
or shared TCP congestion. Respect configured authentication and host-key policy;
own private masters only when explicitly enabled. Keep stderr bounded and drained
so logging cannot stall the JSON data stream.
[OpenSSH](https://man.openbsd.org/ssh),
[OpenSSH configuration](https://man.openbsd.org/ssh_config)

Design judgment: SSH's main likely cost here is how many processes/channels Mesh
creates and how much full-state data it sends, not inability to push. A local
Mesh service can reduce duplicated source channels regardless of backend.
Measure persistent reuse before comparing repeated SSH command startup against
a warm WSS connection; that would conflate lifecycle and carrier costs.

## Application protocol and encoding

Choosing SSH does not settle the application protocol. The candidate uses a
small typed JSON envelope with explicit hello/request/result/subscription/
control/ended frames. Existing Observer payloads remain JSON and keep their
domain validators. Neither SSH nor WebSocket replaces these meanings.

| Protocol/encoding choice | Benefit | Additional work | Candidate decision |
| --- | --- | --- | --- |
| Typed Mesh JSON frames | Mirrors existing strict Observer streams; explicit lifecycle variants | Mesh owns the envelope and conformance suite | Selected candidate, still experimental |
| JSON-RPC 2.0 methods and notifications | Standard request IDs, results and errors; many libraries | Define Mesh subscribe/cancel/credit/gap/replay methods and sequence/epoch metadata | Viable alternative if a consumer needs JSON-RPC interoperability |
| gRPC service/protobuf envelopes | Generated typed service tooling | Schema/runtime integration; source JSON still needs validation or deliberate migration | Deferred until SDK demand justifies it |
| Compact JSON lines on IPC/SSH | Existing producer framing and easy inspection | Bound partial frames and encode embedded newlines as escapes | Initial stream framing |
| RFC 7464 JSON text sequences | Explicit record separators; standardized text-sequence recovery | Change current framing; application continuity still needs epoch/gap validation | No present requirement to replace JSON lines |
| Length-prefixed JSON | Predictable frame allocation/caps | New binary framing and exact byte-length/parser implementation | Optional future stream binding |
| CBOR | Standard binary representation suited to compact clients | Explicit JSON-model mapping, new codecs/schema checks and digest rules | Device projection gate, no core selection |

JSON-RPC 2.0 is transport-agnostic and defines request/response correlation and
unconfirmed notifications. It does not itself specify subscription lifecycle,
credit, native replay or publisher freshness. It could carry the same Mesh
semantics using named methods and notification parameters. Choosing typed Mesh
frames is a design judgment based on existing producer JSON streams and the
absence of a required generic RPC SDK, not a claim that JSON-RPC cannot push.
[JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification)

RFC 7464 uses an ASCII record separator and LF around JSON texts; its parser
recovery does not reconstruct missing domain events. CBOR offers a binary data
model and encoding; smaller wire representation alone does not settle device
memory, domain equivalence or evidence clocks.
[JSON text sequences](https://www.rfc-editor.org/rfc/rfc7464.html),
[CBOR](https://www.rfc-editor.org/rfc/rfc8949.html)

Keep a transport binding narrow: its job is framing/authenticated carriage.
Full-state replacement, compact proof and any future identity-keyed delta are
separate payload choices. Backend switching must not change native semantics.

## WSS findings

WebSocket defines a two-way message connection, message fragmentation and
Ping/Pong/Close controls. It does not define domain subscription, application
cursor, durable replay or exactly-once client effects. Use a negotiated Mesh
subprotocol, one JSON value per WebSocket message, domain-sized message limits,
bounded reassembly and the same application frame validation as IPC/SSH.
Protocol Ping/Pong does not prove an Observer source is current.
[WebSocket specification](https://www.rfc-editor.org/rfc/rfc6455.html)

The evaluated Python library documents a default 1 MiB incoming message limit,
queue bounds and automatic compression/proxy behaviors. These must be configured
explicitly for Agent's larger state envelopes; keep compression disabled for
initial comparison and ensure endpoint routing does not silently inherit an
environment proxy. TLS verification stays enabled and uses an explicit trust
anchor. These are library choices, not WebSocket protocol constraints.
[websockets client API](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)

Design judgment: WSS becomes attractive for clients without SSH executables,
stable always-running Mesh endpoints, browser access, or demonstrated SSH
process/setup cost. It needs server authentication plus per-user/source
authorization, certificate rotation and listener lifecycle proof. A verified
VPN/overlay can change network reachability, but does not remove those application
authority requirements. Do not select WSS simply because the word push appears.

## HTTP/SSE and gRPC findings

SSE provides a server-to-client event stream, reconnect behavior and a
`Last-Event-ID` mechanism. The server still must implement retention and validate
what an ID means. Multiple host-native cursors require a Mesh cursor mapping;
one SSE ID does not establish a native global order. Requests, cancellation and
freshness proof need associated HTTP operations rather than frames in the same
downstream stream.
[HTML EventSource specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)

gRPC defines unary, server-streaming, client-streaming and bidirectional calls;
the two directions of a bidirectional call proceed independently. Streaming
flow control and deadlines are available, but source expiry, replay gaps and
domain validation remain Mesh concerns. The documented default has no deadline,
so read deadlines would still need explicit configuration.
[gRPC core concepts](https://grpc.io/docs/what-is-grpc/core-concepts/),
[flow control](https://grpc.io/docs/guides/flow-control/),
[deadlines](https://grpc.io/docs/guides/deadlines/)

Design judgment: SSE is useful as a downstream web facade; gRPC becomes valuable
when generated typed APIs and several implementation languages justify its
runtime/schema integration. Neither presently removes enough of the Mesh
semantics to warrant replacing existing JSON contracts.

## Broker findings

Core NATS is ephemeral at-most-once pub/sub: an offline subscriber misses messages.
Request-reply adds reply subjects and timeout/no-responder behavior. It provides
no native replay by itself. Its documented default 1 MB payload limit is smaller
than an allowed Agent owner envelope; broker limits and any fragmentation would
need explicit acceptance.
[Core NATS](https://docs.nats.io/learn/core-nats/),
[request-reply](https://docs.nats.io/learn/core-nats/request-reply)

JetStream adds retained streams and consumer delivery/acknowledgment policies.
Continuous consumption can be driven by background pull requests while appearing
as an application subscription. Broker delivery policy does not turn optional
provider callbacks into complete native evidence, or an application side effect
into exactly-once work. A durable broker also adds a separate storage/retention
authority beyond the Observer's proposed five-minute volatile suffix.
[JetStream consumers](https://docs.nats.io/learn/jetstream/pull-consumers)

MQTT 5 defines pub/sub, several QoS levels, retained messages, expiry and
response-topic/correlation properties. Those can carry requests and updates, but
QoS promises concern MQTT delivery scope. They do not prove original state
leases, native callback completeness or exactly-once user notifications. Retained
state must still expire according to the original Observer evidence.
[MQTT 5 specification](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)

Design judgment: an external broker is justified if requirements grow to many
publishers/readers, offline delivery, central event history or broker-native
devices. A small local Mesh connection-sharing service does not require NATS or
MQTT. If a device needs MQTT, an explicit downstream gateway can preserve the
core Mesh contract while owning its device mapping and acceptance separately.

## Decision checkpoints

| Observed requirement or result | Decision to revisit |
| --- | --- |
| Multiple independent readers duplicate source channels | Add per-user local service; measure upstream and downstream separately |
| Persistent SSH still has unacceptable setup/process cost | Compare WSS using identical workload and connection lifetime |
| Large state blocks small event delivery | Isolate product channels; measure before selecting cross-product multiplexing |
| Proof replies dominate bytes | Implement negotiated digest proof before blaming the carrier |
| Native receipt updates dominate full replacements | Review a bounded source delta protocol separately; compact proof alone cannot fix it |
| Browser/non-SSH devices require direct access | Implement WSS or an HTTP/SSE facade with explicit auth and scope |
| Offline events must outlive Observer retention/restarts | Design durable storage/broker policy and end-to-end delivery separately |
| Producers cannot be reached from readers | Review publisher-initiated relay topology; keep connection direction independent of products |

No synthetic timing selects a backend operationally. Acceptance needs the
actual Snap/Starship routes, installed bridge versions, native passivity,
sleep/wake, independent slow-reader behavior and owned-resource cleanup.
