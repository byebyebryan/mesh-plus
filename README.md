# Mesh Plus

The [a17 system classification extension](contracts/agent-profile-v3/contract.md)
adds explicit Agent v3 for Observer wire 6/Service 4 through SDK 1. The
[acceptance receipt](docs/evidence/2026-10-13-system-profile/README.md) records
the exact installed a17 package and independent Observer adoption on Snap and
Starship. Existing Agent v1/v2 and Tmux v1 schemas and defaults are preserved.
The [a16 timing extension](docs/agent-timing-profile.md) retains its dated scope.
Published a15 remains the latest hosted release; local adoption is separate.

Mesh Plus owns request/reply and subscription delivery across a configured fleet. A
mesh-aware domain contract has the same response shape for one local host and
several hosts. Domain records keep their identity and meaning; networking adds
host outcomes, delivery provenance and conservative validity information.

Latest published prerelease: **0.1.0a15**, SDK interface 1, with optional WSS
and the Observer-owned publisher seam. [Release acceptance](docs/evidence/2026-10-12-a15-release/README.md)
records unchanged accepted wheel bytes and independent published-download checks.
Publication does not select live services.

Recorded **0.1.0a10 adoption on Snap and Starship**, 2026-10-10. Polling and pushed
replacement state over local IPC and SSH stdio use the frozen contract. Snap and
Starship select a10 for the public CLI/transport, Tmux Observer 0.6.0a5 / Tmux
Plus 0.12.0a5, and separate Agent 0.5.0a16 reader / bridge environments.
Agent's 0.5.0a15 collector and 0.4.0a16 writer remain independently selected.
SSH Plus retains its separate shared authority SDK a6 selection.

The [a10 artifact checkpoint](docs/evidence/2026-10-10-hardening-artifacts/README.md)
records fresh package gates, refresh attribution and production-budget lifetimes.
The [hardening adoption record](docs/evidence/2026-10-10-hardening-adoption/README.md)
binds exact selection, live recovery and paired rollback/reselection; final
resource and installed SSH/Tmux checks pass; Agent cached delivery passes
separately, with Agent Plus migration excluded.
The [earlier adoption record](docs/evidence/2026-10-10-fleet-adoption/README.md)
preserves a9's exact artifacts and its own acceptance.
A8 introduced proactive watch connection rotation and cumulative measurements;
a9 makes owned send/close retirement withstand repeated caller cancellation.
The [reliability plan](docs/reliability-and-measurement.md) records the remaining
optimization gates. Ordered events/replay, a shared fleet broker and further
Plus/device migrations remain deferred.

SDK interface v1 in **0.1.0a11** adds explicit pure profile injection throughout
IPC/SSH polling and pushed fleet state. See the [SDK specification](docs/sdk-api.md)
and [independent Observer networking tasks](docs/sdk-owner-handoff.md). This SDK
package checkpoint is separate from the selected a10 live artifacts above.

The [SDK maintenance plan](docs/sdk-maintenance-plan.md) is complete in a12:
owner conformance tooling, diagnostics, matched measurements and package acceptance.
Independent Observer adoption can proceed against SDK interface v1.

**0.1.0a12** publishes the [portable owner conformance kit](docs/conformance.md),
explicit [SDK diagnostics and cached assessment](docs/sdk-diagnostics.md), and
[matched measurement/package evidence](docs/evidence/2026-10-11-sdk-maintenance/README.md).
The maintenance sequence is complete without a speculative core optimization.
This package checkpoint does not change live selections.

**0.1.0a13** hardens conformance certification and adds real publisher update/
restart coverage through owned IPC with local and remote-proof bindings. SDK v1
and runtime contracts stay unchanged; see the
[follow-up acceptance](docs/evidence/2026-10-11-conformance-followup/README.md).

The completed research track is the [WSS roadmap](docs/wss-roadmap.md): isolated carrier,
authenticated endpoint binding, native state acceptance and matched measurements.
The a14 source/private-wheel candidate promotes optional native WSS under
[lock revision 2](contracts/wss-v1/contract.md). See [WSS configuration and SDK](docs/wss.md)
for polling, push, the separate `mesh-plus-wss` CLI and operational limits.
Existing wire/profile schemas, SDK v1 defaults and live selections remain unchanged.

The **a15 release** adds a generic cached publisher and trusted installed
factory hook for independent Observer publisher ownership. See the
[publisher API and owner handoff](docs/publisher-api.md). Existing defaults and
the wire contract remain unchanged; no live selection is made.

Start with the [integration handoff](docs/handoff.md) for ownership, entry points,
acceptance gates and current evidence. The
[implementation checkpoints](docs/implementation-progress.md) preserve history.
The [controlled networking benchmark](studies/controlled/README.md) provides
pinned, exact-work IPC/SSH/WSS comparisons; its
[assessment](docs/evidence/2026-10-12-controlled-performance/README.md) retains
SSH defaults and unchanged runtime bytes.

The [admission simplification assessment](docs/evidence/2026-10-13-simplification/README.md)
removes repeated fleet scans and reuses fixed control schemas while preserving
full boundary admission, mutable-view checks and the accepted Agent timing extension.
Its private a16 wheels are separate from the published release and live pins.

The additive [prepared consumer interface](docs/prepared-consumer-api.md) offers
explicit generation-static preparation for repeated watch reads. Existing
ReadGuard/current_sessions behavior and all wire/schema bytes remain unchanged.
Owner certification and selective adoption are separate from Mesh implementation.

The [state contract freeze](docs/contract-freeze.md) defines the interfaces ready
for independent implementation. [The checked lock](contracts/LOCK.json) binds
normative inputs and native schema baselines; CI rejects unreviewed drift.

## Design package

- [Architecture and decisions](docs/architecture.md)
- [Base read contract](contracts/mesh-read-v1/contract.md)
- [Observer contract adaptations](docs/observer-adaptation.md)
- [Agent event delivery boundary](docs/event-delivery.md)
- [Mesh Plus components](docs/components.md)
- [Transport and subscription design](docs/transport-design.md)
- [Backend and protocol evaluation](docs/transport-evaluation.md)
- [Delivery protocol candidate](contracts/mesh-delivery-v1/contract.md)
- [Transport validation and implementation gates](docs/transport-validation.md)
- [SSH Plus integration](docs/ssh-plus-integration.md)
- [Migration and acceptance](docs/migration-and-validation.md)
- [Source baselines and research](docs/research.md)
- [Frozen source reference provenance](reference/README.md)
- [Design review and results](docs/design-review.md)

The central decision is a shared `mesh` section alongside the existing
`sessions` array. The local case has one host outcome; the fleet case has several.
Each host retains the original domain metadata, and each session retains its
existing host-qualified identity. A pure domain facade supplies validation and
effective current views for both cases. Consumers do not implement SSH or source
expiry rules themselves.

Request/reply and publisher-to-client delivery are first-class Mesh operations.
The delivery protocol is independent of its carrier. Local IPC and persistent
SSH stdio are the initial candidates; WSS is the preferred direct-network
alternative. A local Mesh service is a supported topology for sharing upstream
connections across consumers, without requiring a central fleet broker.

Existing published envelopes remain versioned interfaces. The candidate common
shape requires new, explicitly negotiated domain profiles; adding networking
fields does not make an old parser support fleet results. Tmux Observer and
Tmux Plus are a coordinated extraction track. Agent Observer has an independent,
moving producer track. Agent Plus is deliberately deferred, and is not a design
reference for current Agent observation semantics.

## Validate the candidate

On Linux with Python 3.11+, install into a dedicated environment, then run the
same standalone gate as CI:

```sh
rtk proxy uv venv .venv
rtk proxy uv pip install --python .venv/bin/python -e . jsonschema==4.26.0 ruff==0.16.10
rtk proxy .venv/bin/python scripts/check.py
```

This runs the lock, Read/Delivery oracles, core runtime tests (including explicit
Agent v2/v3 negotiation and delivery) and lint. It needs
no Observer packages, providers, desktop tools or configured fleet. With the
reviewed producer dependencies installed, `scripts/check.py --native` runs the
full owned native/SSH suite. Add `--check-sources` to verify sibling source parity.
Neither option deploys artifacts. See the [handoff](docs/handoff.md#validation).

Use Python 3.11+ and `jsonschema` 4.26.0. With an existing validation environment:

```sh
rtk proxy /path/to/python scripts/check-design.py
```

Or use an isolated tool environment:

```sh
rtk proxy uv run --with jsonschema==4.26.0 python scripts/check-design.py
```

Validation is offline after dependencies are available. It checks schemas,
positive and adversarial examples, contract projection against frozen source
fixtures, scope and expiry rules, documentation links and baseline digests.
It does not query providers or start services. The checked-in result is in
[validation evidence](docs/evidence/design-validation.json).

The second candidate adds [delivery validation](docs/evidence/delivery-validation.json)
and an optional [owned carrier study](docs/transport-validation.md#results-and-reproduction).
Current suites pass 117 read checks with source parity (116 offline) and 169
delivery checks. The carrier study
uses temporary synthetic IPC/SSH/WSS endpoints, not ordinary Observer services.

## Experimental runtime

Install Mesh into a dedicated environment; install the selected Observer packages
alongside it for domain adapters. The generic protocol/client package imports no
provider collectors or desktop tools.

```sh
rtk proxy uv pip install --python .venv-design/bin/python --no-deps -e .
rtk proxy .venv-design/bin/python scripts/check-runtime.py --core-only
```

`mesh-plus bridge` and `serve` export explicitly configured cached sources.
`mesh-plus read` and `watch` use the same fleet Reader; `hosts` consumes the
published SSH Plus catalog. See [configuration and acceptance](docs/implementation-progress.md)
for commands, the private source file and recorded runtime evidence. Tmux
Observer 0.6.0a5 and Tmux Plus 0.12.0a5 select the shared Mesh a10 transport on Snap
and Starship. Agent Observer retains its independently selected reader and
bridge packages; producer and consumer acceptance remain separate gates.

`mesh-plus doctor` checks package availability without contacting hosts. Add
`--config /absolute/sources.toml --source tmux` to check a private source descriptor.
`mesh-plus probe --domain tmux --host HOST --source tmux --socket /private/bridge.sock`
exercises one cached snapshot; add `--mode subscribe` to require a pushed baseline.
Omit `--socket` to probe one explicit remote Host Mesh catalog host over SSH.
Probes own and close their connections and do not write route health.

The [Mesh operations pass](docs/mesh-operations.md) describes diagnostic limits,
the synthetic fault/resource lab and the proposed optional connection pool.
The a8 measurement interface adds `read --metrics` and `watch --metrics`: final redacted Reader
counters go to stderr, leaving protocol stdout unchanged. Watch reports on
Ctrl-C after owned cleanup. Python consumers may call `Reader.inspect()` while
running or after completion; totals include retired channels.
