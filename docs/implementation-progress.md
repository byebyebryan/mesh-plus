# Implementation checkpoints

## Foundation: 0.1.0a1

The runtime package now implements strict candidate framing, transactional
state-product lifecycle guards, private same-user IPC and owned noninteractive
SSH stdio channels. Packaged schema resources preserve the reviewed candidate
bytes. Domain payload validation remains an adapter responsibility. Event
products reject setup until an accepted native codec is integrated.

Eight runtime tests cover hostile parsing, deadline quarantine, terminal
barriers, SSH command policy, real duplex IPC, pathname preservation and owned
listener cleanup. The original design suites remain independent oracles.

This checkpoint is transport infrastructure. It does not yet provide a client,
bridge command, Observer adapter, selected runtime or deployed migration.

## Concurrent delivery engine

The asynchronous client and fixed-source bridge now support cached requests
concurrently with independent state subscriptions. Cumulative credit uses actual
encoded octets. A bounded latest-state slot coalesces pending replacements and
signals a gap before resync. Cancellation completes an admitted write before its
terminal barrier; source request failure is typed and leaves siblings usable.
Client queues have per-stream frame bounds and a 96 MiB encoded-byte admission
budget. Decoded heap and OS buffers require separate resource measurement.

Fifteen runtime tests include actual IPC concurrency, independent cancellation,
request deadlines, a 1 MiB frame, source-failure isolation, zero-credit resync and
packaged-schema parity. Adapter/native and real SSH acceptance remain subsequent
checkpoints. No publisher polling fallback or provider actions are introduced.

## Cached Observer adapters and bridge command

Eighteen runtime tests now cover Tmux service 1 and Agent service 2 adapters
against their public pure validators and owned synthetic cached-service sockets.
Full native snapshots are unchanged, proof requests perform a new cached read
after the nonce, and remaining leases retain the original source receipts.
The adapters check same-user IPC, owner host, UID and local clock binding.
Native heartbeat traffic is not promoted to state change or renewed validity.
Native gaps terminate explicitly; recovery requires a new subscription.

`mesh-plus bridge --source ID --stdio` resolves ID through a private configured
source file. `mesh-plus serve --source ID --socket PATH` exposes the same bridge
on private IPC. There is no executable/plugin path in requester metadata. The
source file defaults to `$XDG_CONFIG_HOME/mesh-plus/sources.toml` (or the normal
`~/.config` fallback), must be user-owned mode 0600 and has this format:

```toml
version = 1
host = "canonical-host-id"

[sources.tmux_default]
domain = "tmux"
socket = "/run/user/1000/tmux-observer/owner.sock"

[sources.agent_default]
domain = "agent"
socket = "/explicit/private/agent-service.sock"
```

Install the selected Observer packages alongside Mesh on bridge/client hosts.
The validation environment uses editable checkouts; this is not an artifact
selection or deployment. Source configuration does not start an owner. Tests
also exposed and fixed Python 3.13 listener shutdown ordering: cancel and close
owned handlers before waiting for the listener to finish closing.

## Fleet reader and pure domain facade

The Reader SDK now composes local/fleet responses with the candidate domain
profile, lossless owner reconstruction, per-host outcomes and independent
recovery. Remote reads require full nonce proofs; local reads use the checked
owner clock. Watches consume native state subscriptions and schedule cached
proofs independently of collection. Lease deadlines wake the reader even with
no publication; no periodic full-view output loop is used.

The pure `validate_response` and `current_sessions` facade applies the same
schema, scope and conservative receipt rules locally and across hosts. Original
records remain available in attributable snapshots; consumers use the facade
for current claims, preserving unknown and partial native facts. SSH Plus is
accessed through its published process contract. Catalog identity/route parsing
and route-report forwarding now have a Mesh-owned boundary, while SSH Plus
remains the sole configuration/health writer. No history operation is added.

Twenty-five runtime tests pass, including all fourteen frozen profiles,
lossless local/remote reconstruction, an independently unavailable host, wrong
nonce exclusion, pre-dispatch scope rejection, simulated suspend expiry, live
reader watch cleanup and Host Mesh identity-collision rejection. Native
operational and old-client migration gates remain separate.

## CLI and actual SSH runtime acceptance

`mesh-plus hosts`, `read` and `watch` now consume the common catalog/Reader
boundary. `read/watch --domain tmux|agent --source ID --socket LOCAL_MESH_IPC`
use the defined fleet by default; `--scope local` or `--scope hosts --hosts ID...`
select a subset. `--local-host ID` explicitly selects standalone local operation.
This CLI consumes a configured local Mesh bridge, not the native owner socket.

Remote channels preserve configured SSH policy and use the published reached
nonce marker. Only clear pre-marker transport failure permits another configured
route. Authentication/host-key/ambiguous failure and reached-source failure do
not fall through. Route health reports go through the existing authority with
revision and observation time; no picker history or connection counter is used.
Unsuccessful host watches back off independently up to thirty seconds.

Twenty-nine runtime tests pass, including the actual runtime bridge over a
disposable localhost SSH daemon with private keys, forced command, pinned host
key and StrictModes enabled. Separate tests execute the POSIX quoting wrapper
and verify route failover boundaries. The SSH harness's initial escaped marker
was corrected with a fixed private script; no operational SSH policy changed.
Framing now has a first-byte deadline, and client-side control input has a
64 KiB admission bound. Native fleet recovery, physical suspend and production
costs remain unproved. All endpoints in these tests are disposable synthetic
publishers using validated native fixture frames.

## Lifecycle hardening and owned tmux proof

Thirty-two runtime tests now include shutdown waking pending handles, deterministic
native watch closure, an 8 MiB request response, and per-provider expiry after Mesh
downgrades an active component to stale. The latter also corrected the independent
design oracle; read checks now total 117 plus 161 delivery checks.

An actual owned tmux server and Observer process passed three Mesh subscriptions
and fifteen cached reads: native identities, hooks and attachment counts stayed
unchanged, collection attempts stayed within the owner's normal two-second
cadence, and the native server disappeared with Mesh watches still connected.
This establishes bounded local passivity for that disposable test, not ordinary
fleet selection, Agent provider behavior or physical suspend.

Use `scripts/check-runtime.py --report docs/evidence/runtime-validation.json`
for the full runtime report with Observer packages installed. `--core-only`
explicitly excludes Observer/native tests and is suitable for standalone package
checks; it must not be reported as adapter or native acceptance.

The latest review adds a deterministic crossing-cancel test: an incoming cancel
already in flight after the server's result cannot close sibling operations or
reopen the completed handle. Runtime tests now total thirty-three. Reports bind
the tested package and test bytes by SHA-256. Standalone CI explicitly runs only
the core suite on Python 3.11/3.13; full native/adapter acceptance remains a
separately recorded local gate.

Reproduce runtime tests after installing the package into a validation venv:

```sh
rtk proxy uv pip install --python .venv-design/bin/python --no-deps -e .
rtk proxy .venv-design/bin/python -m unittest discover -s tests -v
rtk proxy .venv-design/bin/ruff check src tests scripts
```
