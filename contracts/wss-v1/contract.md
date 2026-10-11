# Native WSS carriage and selection v1

This additive state-only contract is accepted by lock revision 2 following the
[promotion review](../../docs/wss-promotion-plan.md). It adds optional native WSS
carriage; existing Read/Delivery envelopes, pure profiles and native schema bytes
are unchanged. SDK v1 defaults remain IPC/SSH. Runtime acceptance and real-host
selection are separate gates.

## Endpoint and publisher authority

One WebSocket text message carries one UTF-8 Delivery JSON frame. Negotiate
`mesh-plus.delivery-candidate.v1`, use TLS with verified server chain/hostname
and verified client chain, and require the client certificate DER SHA256 in the
listener allowlist. The configured URL is `wss://HOST[:PORT]/mesh/state`, without
userinfo, query, fragment, redirects, implicit proxies or compression. Native
listeners reject Origin. Only a fixed trusted cached adapter is dispatched;
frames cannot choose paths, executables, collectors or alternative sources.

The authorization map keys are lowercase 64-character DER SHA256 fingerprints.
Values are exactly `[hostId, sourceId, profile]`, matched to the fixed adapter.
The packaged authorization schema bounds this map to 128 principals. Certificate
validity uses wall clock. Policy/trust/certificate/key checks begin at most five
seconds apart while runnable, have a five-second BOOTTIME caller budget, and
failed or changed checks revoke admitted channels before bounded cleanup. Any
observed allowlist change conservatively retires existing sessions. Rotation
requires explicitly overlapping fingerprints followed by new admission. Neither
instantaneous remote revocation nor CRL/OCSP is advertised.

The listener binds an explicitly chosen numeric IPv4/IPv6 address. At most four
active or pending TLS clients are admitted before handshake work. Kernel backlog
and operating-system buffers are outside that admission count. Binary messages
are rejected. Controls/HTTP headers are bounded to 64 KiB; complete messages obey
the existing negotiated profile ceiling and global 8 MiB + 80 KiB ceiling.
Assembly admits at most 256 fragments and queues at most two complete messages.
These bounds do not promise a global RSS limit.

## Selection, revisions and mixed fleets

The registry protocol is `mesh-plus.wss.v1`. Ordered entries bind an existing
canonical remote Host Mesh ID, source selector, supported profile, URL, `state`
product and exactly `snapshot`, `proof`, `subscribe` capabilities. One remote
host occurs at most once, with at most sixteen entries. WSS-only host authority
is excluded. There is one local credential set per captured selection.

The new optional factory captures Host Mesh catalog, registry, CA, client
certificate and key bytes from private regular files. TLS uses owned snapshots;
caller path replacement cannot redirect admitted credentials. The selection
revision is SHA256 of canonical JSON containing `bindingProtocol`,
`hostMeshRevision`, ordered `registry`, and `trustRevision`. `trustRevision` is
SHA256 of canonical JSON with the public PEM `ca` and `certificate` strings.
Digest formatting uses the existing `sha256:` prefix. Private key bytes and
route-health values never enter public revisions or tokens. Changed/unreadable
private keys still revoke the local selection.

This composed revision occupies Read's existing opaque `mesh.catalog.revision`.
For WSS the opaque route token hashes exactly `{bindingProtocol,
selectionRevision, hostId, endpointIndex}`. Legacy factories retain their Host
Mesh revision and SSH token meaning. In the new factory, IPC uses no route token
and SSH tokens use the separately captured original Host Mesh revision and route
index. Registered selected hosts use WSS; unregistered selected hosts use their
captured IPC/SSH binding. A failed WSS connection never selects SSH implicitly.
All connecting, unavailable and ready WSS outcomes report `delivery.path=wss`.
WSS does not write SSH route health, configuration or picker history.

Validate composition authority before snapshot dispatch, each watch acquisition,
and periodic watch checks. Catalog revision changes, ordered registry changes,
trust changes or credential changes require fresh selection. Catalog route-health
updates alone do not revoke selection. No producer field or semantics changes.

## Budgets, local filesystem and diagnostics

Carrier setup has one fifteen-second BOOTTIME budget including TLS, HTTP,
authorization and validation. Send has a two-second budget including encoding,
validation, write-lock admission and IO. Assembly's two-second budget starts at
the first fragment byte and includes decode validation. Synchronous Python work
is checked after returning; it is not preempted. Idle reads use liveness controls,
not a source freshness lease. Ping/Pong never renews producer receipts.

Channel shutdown has a three-second IO budget including graceful close, parser/
liveness retirement, TLS close and abort; caller cancellation does not abandon
owned cleanup. Cooperative task scheduling and synchronous work can postpone
observation of expiry. Listener shutdown owns every accepted task and socket.

Configuration is restricted to owner-controlled local filesystems, private
regular files and private directories. At most one daemon file-read job runs per
configuration owner. Timed-out/cancelled callers receive no late results; no new
job starts while a prior job remains outstanding. Owners close explicitly and
report `wss_configuration_busy` if a read is unretired. A timeout cannot interrupt
an arbitrarily blocked kernel filesystem call; hard filesystem cleanup is not
promised. Synchronous initial capture is also subject to this local-file boundary.

WSS byte counters count completed JSON messages; IPC/SSH counters retain complete
JSON lines including LF. Operation counters use the actual carrier framing.
Mixed Reader counters identify their mixed scope. WebSocket framing counters are
before TLS and cannot be presented as encrypted or NIC bytes.

Ordered events, replay/status, digest-only proof, brokers/pools, browser clients,
automatic fallback, provider collection, refresh and actions remain excluded.
