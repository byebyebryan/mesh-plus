# Two-host WSS trial, measurement and rollback plan

2026-10-12. **Preparation only; no live WSS selected.** A15 is
[published and accepted](evidence/2026-10-12-a15-release/README.md). This plan
uses that exact wheel and leaves shared launcher/Observer deployment changes to
separate, coordinated acceptance. No firewall, certificate, listener, producer,
collector, desktop or chezmoi selection was changed during preparation.

## Observed baseline and first network

[Read-only inventory](evidence/2026-10-12-wss-plan/README.md) refreshed both hosts
through existing strict authenticated SSH. These observations are dated, not
execution-time guarantees; rerun preflight before preparing or selecting a trial.

| Item | Snap | Starship |
| --- | --- | --- |
| Host Mesh identity | snap | starship |
| Kernel hostname | 80H1VV3 | starship |
| Tailnet IPv4 | 100.70.82.105 | 100.84.31.64 |
| Tailnet DNS SAN | snap.tail223cf3.ts.net | starship.tail223cf3.ts.net |
| Python / OpenSSL | 3.14.8 / 3.6.5 | 3.14.8 / 3.6.5 |
| Proposed Tmux / Agent ports | 9443 / 9444, unoccupied at inventory | 9443 / 9444, unoccupied at inventory |
| Tmux selected tuple | Observer a6, reader Mesh a13, bridge a10 | same |
| Agent selected tuple | Observer a18, reader Mesh a11, retained a16/a10 bridge | same recorded reader/bridge roles |

Both tailnet identities were online. TCP reachability, tailnet ACL/firewall
admission and direct-versus-relay paths were **not** accepted. Tailnet IPv4 is
the first proposed network, with numeric registry URLs to isolate DNS-helper
cost. Repeat a separate hostname test using the same SAN-covered certificates.

Snap's observed LAN addresses are 10.201.9.118/23 and 10.201.65.216/23; Starship
is 192.168.1.110/24. These are different subnets. Do not advertise a matched direct
LAN experiment from this inventory: it requires separately proven routed or
same-LAN reachability, refreshed bind addresses and certificate SANs. A tailnet
trial is not LAN, WAN or relay-performance acceptance.

## Execution boundaries and staged source selection

**Stage A — Mesh-owned isolated state trial.** Use the released package's independent
`mesh_plus.testing.sample.Profile`/`Publisher` with both frozen domain profiles,
canonical host IDs and fixed configured sources `tmux_trial`/`agent_trial`. A
trusted, Mesh-repository trial harness constructs those fixture publishers and
supplies a static lazy map to the published CLI factory hook. Trial readers use
the public SDK with the same explicit fixture `profile=` through Reader/ReadGuard;
do not use the stock reference-profile read/watch CLI to claim Observer-free
fixture admission. This is synthetic
state on real hosts: it proves selected network/carrier behavior, not native
Observer collection. Label every result synthetic; expose no frontend/device
socket or ordinary consumer selection. Build/review the bounded trial harness
before execution; no study CLI copying or arbitrary wire-selected code is allowed.

**Stage B — cached native integration.** Once each owner delivers accepted exact
source/factory/profile artifacts, trial its supported cached publisher in a
separate listener/environment. Preserve ordinary collector cadence and all source
receipts. Cached reads/proofs must not schedule collection. Review normal/capacity
resources and owner-native identity/state admission separately. Stage A success
cannot close Stage B, and WSS does not require early shared-launcher migration.
If an owner is unfinished, retain Stage A findings and mark that native domain
pending rather than substitute a different producer.

Do not run fault/resource trials while another agent is changing selected
artifacts/services. Source-only parallel work may continue; capture package/control
hashes, unit PID/birth identities and native-owner incarnation before each window.
A changed input invalidates that comparison and requires a fresh baseline.

## Concrete isolated layout and service selection

Trial environment on each host:

- `%h/.local/share/mesh-plus/trials/wss-v1/venv`, containing downloaded/checksummed
  a15, jsonschema 4.26.0 and websockets 17.2. Resolve/archive exact transitive
  dependency wheels per Python ABI before installation. Never alter existing
  `%h/.local/bin/mesh-plus`, shared versioned roots or Observer prefixes.
- `%h/.config/mesh-plus/trials/wss-v1`, mode 0700, with 0600 per-domain source,
  trust, credential, authorization, catalog and registry files. Use canonical
  private local-filesystem paths. Secrets remain outside the repository/chezmoi.
- Separate user units `mesh-plus-wss-trial-tmux.service` and
  `mesh-plus-wss-trial-agent.service`, initially **not enabled**. Each unit uses
  an absolute private interpreter and the hash-reviewed trusted trial launcher,
  a fixed source config, tailnet bind IP, its fixed port and its own policy files.
  `UMask=0077`, `NoNewPrivileges=yes`, bounded restart with `Restart=on-failure`,
  and explicit stop/cleanup checks. Stopping a trial unit must not restart an
  ordinary owner or bridge. Unit/harness files stay in Mesh's owning repository;
  a later lasting deployment may manage only necessary selection config in chezmoi.

Per-host sources remain the existing version-1 descriptor shape. Stage A records
absolute `/unused` native socket paths because its explicitly selected fixture
factory performs no native socket I/O. Stage B uses the owner-accepted absolute
cached IPC path. One example for Snap:

```toml
version = 1
host = "snap"
[sources.tmux_trial]
domain = "tmux"
socket = "/unused"
[sources.agent_trial]
domain = "agent"
socket = "/unused"
```

The Tmux listener binds 100.70.82.105:9443 on Snap and 100.84.31.64:9443 on
Starship; Agent uses port 9444. Do not bind 0.0.0.0/:: or assume an unoccupied
port grants firewall access. Stop if a proposed port became occupied.

Obtain each reader host's own fresh Host Mesh catalog through its existing
selected authority, writing only its private trial capture. Registries bind remote
host/source/profile exactly: Starship reads `wss://100.70.82.105:9443/mesh/state`
for snap/tmux_trial/Tmux v1, and vice versa; Agent uses agent_trial/Agent v1/9444.
Use `scope=hosts` for the first remote-only gate; a later mixed-fleet gate combines
an owned local IPC endpoint and remote WSS. Separate legacy SSH endpoints retain
their independently captured Host Mesh revision and existing tokens. No registry
change, catalog failure or WSS failure may silently choose SSH.

## Credentials, reachability and rotation

Create a **dedicated trial CA**, unrelated to SSH/production trust. Keep its
private signing key only in an owner-controlled offline/private issuer directory
on Snap; neither listener nor reader needs that key. Generate server/client keys
on their owning hosts and transfer only CSRs/certificates/public CA through the
existing authenticated route. No keys/certificates are created by this planning pass.

Use separate server certificates per host covering its numeric tailnet IP and
DNS SAN. Require serverAuth; client identities use clientAuth, with independent
host/domain keys. Suggested trial validity: 30 days for CA, 7 days for endpoint
certificates. The execution issuer must record exact openssl commands, extensions,
serials and UTC validity ranges and verify chains/hostname before selection.
TLS verifies the configured registry hostname or IP on every connection.

Each listener's authorization JSON maps the selected reader client certificate's
DER SHA256 to exactly its own `[hostId, sourceId, profile]` tuple. Tmux and Agent
use separate listeners/allowlists because each fingerprint maps to one fixed tuple.
CA validity alone does not authorize a publisher. No ambient OS trust, browser
Origin, proxy, relay service or credential fallback is introduced.

Check tailnet ACL and host firewall reachability without modifying either during
preflight. If admission requires a rule, review a narrow peer-to-host TCP rule
and its exact reversible removal before applying it in the later trial. Never
change SSH access or use global tailnet disconnect/firewall flush to simulate loss.

Rotation sequence: create replacement host/domain client credential, verify it,
add its DER fingerprint alongside the old entry, observe conservative retirement
and readmit via a newly captured Selection; then remove the old entry and prove
old admission fails. Any observed policy change retires existing channels, even
a planned overlap. Credential/trust file replacement also retires channels;
restart listeners with newly captured server configuration. Exercise server cert,
client cert and dedicated CA replacement as separate cases. Policy updates and
key/cert selections are explicit operations with rollback copies; no in-place
silent reload assumption is permitted.

## Acceptance sequence and failure criteria

1. **Freeze inputs:** re-run both preflights; verify wheel and dependency origins,
   private paths, clocks, catalog/source bindings, proposed ports, rollback inventory
   and unchanged ordinary controls/incarnations. Review and pin the trial harness.
2. **Local TLS first:** start one owned listener/domain on one host; verify mTLS,
   wrong/missing/unknown credentials and wrong tuple fail before source dispatch.
   Confirm readiness, poll, subscription baseline and owned stop cleanup.
3. **Two-host tailnet:** remote polling and pushed replacement state for both
   domains, first one direction, then reverse; validate native/profile reconstruction,
   expiry, complete-empty/partial/stale and healthy local sibling behavior.
4. **Owned faults:** reader restart/cancel, listener restart, publisher restart/gap,
   targeted connection loss, captured catalog/registry change, allowlist and
   certificate replacement. Record revocation before reproof/resync; no old cached
   view retains positive authority. Prove bounded channels/tasks and no late results.
   Use a scoped owned socket/proxy fault fixture when needed; exclude its cost from
   clean performance windows and never sever global tailnet/ordinary SSH sessions.
5. **Admission/load:** one reader, two independent readers, then four stable readers
   per listener. Four includes pending TLS sessions; fifth admission must fail without
   dispatch. Before reconnect, retire the previous channel; test burst reconnect
   behavior separately. Avoid overlapping parallel test runs on the same listener.
6. **Suspend:** only in a separately coordinated quiet window, suspend one host and
   exercise BOOTTIME invalidation/recovery on the other. Simulated clocks are not
   physical-suspend acceptance. Until this is actually run, record it pending.
7. **Rollback and preservation:** stop all trial readers/listeners, restore any
   trial-only selection and peer firewall rule, verify resource retirement and the
   captured ordinary SSH/native-owner baseline. Only then consider Stage B or a
   lasting selection. No consumer/UI rollout follows automatically.

Any proof/receipt renewal from delivery, missing revocation, wrong binding,
unauthorized dispatch, leaked resource, changed ordinary collector/authority or
unexplained regression is a failed gate. Keep successful gates as scoped evidence;
do not compensate by dropping an adversarial case or relabeling stale state.

## Matched SSH/WSS measurement

Measure **released a15 on both sides**, with the same Python/dependencies/profile,
source payloads and receipt age. A10 bridge compatibility is a separate gate,
not a matched performance input. Run matched one-reader cases first, then deployed
multi-reader topology. WSS uses one listener worker per source; SSH uses one fixed
stdio bridge process per connection. Count those topology differences explicitly,
including attributable ssh/sshd children. Do not attribute the whole shared sshd
or unrelated services to a trial reader. A controlled one-worker-per-reader
variant can distinguish sharing from carrier cost; report it separately.

Use at least four SSH/WSS **ABBA blocks** per domain/workload. Each fresh window
has 15 seconds warmup and 60 seconds measurement; collect 20 cold acquisitions
per carrier/domain. Workloads: idle, one-row and 256 unique-row state updates at
fixed 1 Hz, and one/two/four independent readers. Capacity fixtures must first
pass their domain schemas and unique host-qualified identities. Source update
traces are identical; receipts advance only on explicit source-owned state
evidence events, never merely from reads/delivery. Idle expiry is expected and
measured separately from connection liveness.

Record both hosts' attributable process-tree CPU, PSS/RSS, FD/process counts,
reader-visible update age, cold acquisition median/p95 and exact completed JSON
byte scopes. Sample at 500 ms and measure sampler cost separately. Record payload
sizes, read/watch/proof cadence, successful updates, drops/gaps, cleanup totals and
trial runtime digests. TLS/NIC bytes require independent interface attribution;
do not equate JSON counters with encrypted traffic. Report DNS numeric/hostname
cost independently. Preserve raw observations and paired differences; do not
claim significance or fleet budgets from a small fixture sample.

Before/after every block, record tailnet direct-versus-relay path, network type,
background work and ordinary artifact/incarnation stability. If a path switches,
load changes materially or an owner rollout overlaps, reject that paired comparison
and repeat after stabilization. Functional acceptance can pass without a speed
win; no default switch follows from a favorable cold-start median.

## Rollback and scope of the next loop

Because ordinary clients remain on SSH, Stage A rollback consists of stopping
trial consumers, stopping both trial units, verifying no sockets/children/jobs,
removing only trial firewall additions, and leaving disabled units/private
credentials available for explicit reuse or removal. Verify existing authority,
collector/bridge incarnations, selected roots and cached SSH snapshot/watch with
the owner-approved bounded diagnostics. Preserve normal native sessions and history.

If Stage B later selects any consumer, first capture its exact previous launcher,
config/catalog/registry/credential selection and package hashes. Roll back those
paths serially with owner acceptance; do not broadly apply chezmoi or overwrite
immutable environments. A failure never triggers automatic transport fallback.

The next execution loop should implement/review the Mesh-owned bounded trial
harness, freeze both private environments and credential/config/unit candidates,
then run Stage A functional and matched measurement gates. Stage B waits for
owner-native artifact acceptance. Physical suspend and lasting deployment require
their explicit operational windows. Shared publisher launcher composition remains
one separate coordinated checkpoint after both factory handoffs.
