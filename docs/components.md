# Mesh Plus implementation components

## Package boundaries

| Component | Responsibility | Prohibited dependency |
| --- | --- | --- |
| Pure base contract | Schemas, bounded codecs, scope guards, generic validity arithmetic | Provider adapters, collectors, SSH execution, Rofi, desktop or writes |
| Catalog authority | Host Mesh identity/aliases/routes/policy, revision and route-health reports | SSH picker history, native session state |
| Delivery sessions | Request/subscription correlation, cancellation, credit, framing and epoch guards | Native facts, event notification policy or action retry |
| Transport backends | Authenticated IPC/SSH/WSS channels, setup, owned resources and bounded close | Source freshness or replay semantics |
| Domain read adapter | Public contract validation, fixed cached source access, receipt extraction and record projection | Provider collection internals, action executors |
| Host-local bridge | Fixed adapter selection, local endpoint authentication and nonce proof | Fleet export, arbitrary command dispatch, source autostart |
| Reader coordinator | Selected-host outcomes, retained views, independent recovery, replacement watch delivery | Native refresh scheduling, viewer matching |
| Optional local Mesh service | Shared reader lifetime/admission and independent downstream subscriptions | Durable event journal, domain interpretation or desktop policy |

Domain adapters can be distributed by their owning Observer packages. They expose
small pure validation/projection facades and explicit cached read hooks. Mesh Plus
owns bridge/transport lifecycle. Installing an Agent adapter must not force a
Codex or Claude collector import in the pure Mesh parser. A future source requires
an explicit adapter/profile, not generic arbitrary remote argv.

## Current interfaces

Commands exist in the candidate package; no operational installation is selected:

```text
mesh-plus hosts --authority ssh-plus|mesh
mesh-plus mesh list|report-route --json ...
mesh-plus read --domain tmux|agent --source ID --socket LOCAL_MESH_IPC --scope local|fleet|hosts
mesh-plus watch --domain tmux|agent --source ID --socket LOCAL_MESH_IPC --scope local|fleet|hosts
mesh-plus bridge --source SOURCE --stdio
mesh-plus serve --source SOURCE --socket HOST_BRIDGE_IPC
```

Domain-facing CLIs retain their own names and adopt the new profile via an
explicit option or endpoint. They may call a pure local adapter or the reusable
reader. The public process interface is independently callable without Rofi.
Remote bridge source IDs resolve through installed owner configuration; neither
the requester nor metadata text supplies an executable path.

`serve` publishes one configured host-local source; it is not the deferred
shared fleet-reader broker. The public SDK uses `Reader.execute(request)` for
the Mesh Read envelope, `Client.request`/`subscribe` for delivery, and
`ReadGuard.accept`/`current` for safe consumer adoption. See the
[contract freeze and work boundaries](contract-freeze.md) for exact scope.

The configured SSH destination plus existing SSH authentication/host-key policy
is the trusted route binding. Source host labels are checked against it but are
not independent cryptographic machine attestation. Aliases express configured
correlation, not permission to rename returned source identities. Remote UID can
differ from local UID; enforce the remote bridge's own same-user IPC policy and
the selected source binding rather than numeric cross-host UID equality.

## SSH and subprocess ownership

See the [transport design](transport-design.md) and
[delivery candidate](../contracts/mesh-delivery-v1/contract.md) for request/reply,
subscription lifecycle and backend boundaries. SSH is the first remote backend.
Local IPC carries the same delivery semantics; WSS has a separate future listener
and authorization gate. Clients call Mesh APIs rather than owning networking.

Reuse the existing strict noninteractive policy: no PTY, bounded setup,
`BatchMode=yes`, `StrictHostKeyChecking=yes`, cleared forwardings and no agent
forwarding. Respect SSH configuration for destinations, credentials and jump
hosts. Do not write global SSH config or take over existing multiplexing masters.

Use local argv arrays and tested POSIX quoting at the remote command boundary.
OpenSSH sends a remote command line; local argv construction alone does not
avoid remote-shell parsing. The fixed bridge command and source selector are
quoted separately. A nonce marker proves the remote wrapper was reached, not
that the Observer succeeded. See the [OpenSSH manual](https://man.openbsd.org/ssh).

Initial channels can be one owned SSH process per source/host. Shared SSH masters
are an optional measured optimization, with private control paths and cleanup of
owned masters only. Neither sharing a socket nor a master merges source epochs.
See [connection-sharing policy](https://man.openbsd.org/ssh_config).

## Source adapters

An adapter descriptor declares domain/profile version, supported cached reads,
owner protocol, exact document limits, source binding extraction, receipt
components and pure effective projection. No universal provider/runtime enum is
part of Mesh Plus. Tmux source IDs may be `default`; Agent source IDs derive from
provider plus namespace, preserving both as opaque identity inputs.

For a probe, an adapter returns an immutable checked full owner view with its
original service metadata and source-clock expiries. The bridge calculates
remaining time only in that clock domain. It rejects a changed source/publisher
binding, future encoding, regressing receipt counters or mismatched payload.
The reader rejects old connection/catalog epochs even if a delayed reply has
the right host label.

## Scheduling and resources

Owner publishers retain native collection schedules. Mesh schedules only setup,
probes and cached reads. Watch subscribers and UI callbacks cannot increase native
collection frequency. Tmux's explicit refresh capability stays domain-specific.

Use Linux BOOTTIME for absolute deadlines and skip missed slots after suspend.
BOOTTIME includes suspended time; time namespaces can shift its origin, so the
boot/time binding must accompany receipts. See [clock semantics](https://man7.org/linux/man-pages/man2/clock_gettime.2.html)
and [time namespaces](https://man7.org/linux/man-pages/man7/time_namespaces.7.html).

Material changed pushes prompt coalesced proofs; periodic proofs cover unchanged
samples. Candidate cadence starts at three seconds for Tmux and ten seconds for
Agent, bounded by the shortest active lease and source-specific configuration.
These are tuning candidates. Measure proof bytes/CPU before deploying; full
Agent views can be much larger than Tmux views. Same-host IPC needs no remote
probe, but still needs expiry and publisher checks.

An optional negotiated digest-proof extension avoids a second full payload when
a fresh cached read validates the same retained source version. Changed receipts
or records require full replacement; a lost owner cannot renew a retained copy.
This saves bytes rather than the proof round trip. See the
[proof conditions](transport-design.md#freshness-without-a-second-inventory-copy).

Resource admission counts source payloads, pending frames and owned children.
Overflow rejects the operation or individual source explicitly. A frame already
being written cannot be replaced; queue one latest replacement behind it. Gap
and full resync preserve uncertainty if intermediate publications are skipped.

## Actions

The first release carries reads only. Existing action clients retain routing
through the Host Mesh facade. A later shared action transport may reuse quoting,
deadlines and route binding, but uses a distinct interface with operation-specific
effect/uncertainty semantics. Neither read request IDs nor refresh tickets provide
idempotency. No action may be retried after uncertain dispatch or rerouted because
native execution returned nonzero.
