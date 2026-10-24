# Historical README checkpoints

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Archived on 2026-10-23 during the presentation pass. These passages describe
their original checkpoints; their future tense and older current selections are
historical. Use the [current README](../../../README.md) for supported behavior.

## Mesh Plus

Source candidate **0.1.0a25** [withdraws the standalone Agent active profile](../../active-profile-retirement.md).
Working-set, full Agent, Tmux and Host Mesh boundaries remain. The published
releases and their historical capability/acceptance records below are unchanged.

Reusable host authority and cached state delivery for a configured fleet.
Mesh owns logical hosts/routes and network validity; producers own the meaning
of their records. SSH Plus exposes the supported Host Mesh CLI and SSH picker.
Agent Observer supplies Codex observations for read-only utilities; the Tmux
pair serves generic tmux workflows. Agent Plus opens native provider managers
through Host Mesh and does not consume Observer or Tmux state.

Start with the [current ecosystem and ownership guide](../../ecosystem-role.md),
[Host Mesh boundary](../../ssh-plus-integration.md) and [SDK interface](../../sdk-api.md).
Package publication, producer acceptance and installed role selection have
independent receipts. The release/experiment checkpoints below retain their
original scope.

Delta-sync is a **dark, gated development feature**. Work is stopped at its
retained source/evidence checkpoint because CPU and 2,000-row capacity gates
fail. It is unavailable through the normal configured routes and has no new
release or adoption acceptance. See the [dark-feature status and safe Git
handoff](../experiments/delta-sync-dark-status.md) before resuming work or cleaning this
checkout.

A separate [view change-feed design](../experiments/view-change-feed-design.md) captures
the proposed conservative Mesh-owned comparison/reconstruction path over complete
published views. The [explicit API](../../view-feed-api.md) implements that path
on its own opt-in IPC/stdio route, published as an experimental prerelease. The
retained delta implementation stays dark and live selections are unchanged.

The [**0.1.0a24 experimental prerelease**](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a24) adds this explicit complete-view
feed and includes the opt-in working-set SDK registration. It preserves the
accepted full/active/Tmux defaults, full nonce proofs and existing selections.
Its qualification covers standalone correctness and disposable source/Reader
composition; producer CPU/RSS, large-view/native fleet and deployed-pair gates
remain separate. See the [view-feed API](../../view-feed-api.md) and
[publication review and receipt](../../evidence/2026-10-20-view-feed-publication/README.md).

The [**0.1.0a23**](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a23)
release has its own dated installed producer qualification.
The release publishes the exact independently qualified wheel, with SHA256 and
provenance assets; see the [producer acceptance](../../evidence/2026-10-16-active-feed/README.md).
The [publication receipt](../../evidence/2026-10-16-active-feed-publication/acceptance.json)
verifies public downloads, signed assets/tags and fresh installed owner gates.
It requires Python 3.11+ and pairs the opt-in Agent active route with Observer
0.7.0a7. Publishing the package does not change any installed selection.

The **a23 release** adds the explicit
[projected Agent active profile](../experiments/active-feed-api.md) under lock 5. SDK 1,
Read 1, Delivery 1, old full/Tmux schema bytes and original proof/receipt rules
remain. The new native/profile route is opt-in; installed producer qualification
and later role selection are separate. The [agreed G0 boundary](../experiments/active-feed-g0-proposal.md)
records the producer/consumer ownership and lifecycle choices.

The **a22 source/private candidate** adds [owned admission, row-free context and
whole-roster selection summaries](../../cpu-admission-api.md) for explicitly opted-in
prepared watch consumers. It retains accepted a20 receipt/deadline fixes, SDK 1,
preparation 1, lock 4, schema bytes, acquisition and live pins. Candidate acceptance
and later Observer/RLCD adoption remain separate.

The **a20 source/private candidate** fixes cached publisher acquisition-history
ordering and refines shared BOOTTIME expiry checks, including short-deadline rearming. Its
[idle simplification evidence](../../evidence/2026-10-14-idle-simplification/README.md)
records corrected installed-wheel acceptance and matched CPU reductions of about
22% for empty fleets and 17% under controlled updates. These are Fleet-process
figures; the preceding a19 prototype has separate long-run evidence.
SDK 1, preparation interface 1, lock 4, schema bytes and managed selections remain
unchanged. Tmux a10 is the separate matching private package pin.

The [Tmux actual-pipeline qualification](../../evidence/2026-10-14-tmux-preparation/README.md)
certifies an optional Observer facade and retains the existing Fleet guard:
that consumer performs no Mesh current queries. It also corrects the a18 runtime
version banner and binds a distinct private wheel; no release or live pin changes.

The preceding **a18 source/private candidate** integrates the accepted Agent v3 profile
with compatible admission simplification and opt-in prepared watch consumers.
The [changing-watch qualification](../../evidence/2026-10-14-watch/README.md)
separates consumer CPU/allocation evidence, package acceptance and owner handoff.
SDK 1, lock 4, all accepted schemas, existing defaults and live pins remain.

The [a17 system classification extension](../../../contracts/agent-profile-v3/contract.md)
adds explicit Agent v3 for Observer wire 6/Service 4 through SDK 1. The
[acceptance receipt](../../evidence/2026-10-13-system-profile/README.md) records
the exact installed a17 package and independent Observer adoption on Snap and
Starship. Existing Agent v1/v2 and Tmux v1 schemas and defaults are preserved.
The [a16 timing extension](../design/agent-timing-profile.md) retains its dated scope.
The published a15 checkpoint remains historical; local adoption is separate.

Mesh Plus owns request/reply and subscription delivery across a configured fleet. A
mesh-aware domain contract has the same response shape for one local host and
several hosts. Domain records keep their identity and meaning; networking adds
host outcomes, delivery provenance and conservative validity information.

The preceding published **0.1.0a15** checkpoint supplies SDK interface 1, optional WSS
and the Observer-owned publisher seam. [Release acceptance](../../evidence/2026-10-12-a15-release/README.md)
records unchanged accepted wheel bytes and independent published-download checks.
Publication does not select live services.

Recorded **0.1.0a10 adoption on Snap and Starship**, 2026-10-10. Polling and pushed
replacement state over local IPC and SSH stdio use the frozen contract. Snap and
Starship select a10 for the public CLI/transport, Tmux Observer 0.6.0a5 / Tmux
Plus 0.12.0a5, and separate Agent 0.5.0a16 reader / bridge environments.
Agent's 0.5.0a15 collector and 0.4.0a16 writer remain independently selected.
SSH Plus retains its separate shared authority SDK a6 selection.

The [a10 artifact checkpoint](../../evidence/2026-10-10-hardening-artifacts/README.md)
records fresh package gates, refresh attribution and production-budget lifetimes.
The [hardening adoption record](../../evidence/2026-10-10-hardening-adoption/README.md)
binds exact selection, live recovery and paired rollback/reselection; final
resource and installed SSH/Tmux checks pass; Agent cached delivery passes
separately, with Agent Plus migration excluded.
The [earlier adoption record](../../evidence/2026-10-10-fleet-adoption/README.md)
preserves a9's exact artifacts and its own acceptance.
A8 introduced proactive watch connection rotation and cumulative measurements;
a9 makes owned send/close retirement withstand repeated caller cancellation.
The [reliability plan](../design/reliability-and-measurement.md) records the remaining
optimization gates. Ordered events/replay, a shared fleet broker and further
Plus/device migrations remain deferred.

SDK interface v1 in **0.1.0a11** adds explicit pure profile injection throughout
IPC/SSH polling and pushed fleet state. See the [SDK specification](../../sdk-api.md)
and [independent Observer networking tasks](sdk-owner-handoff.md). This SDK
package checkpoint is separate from the selected a10 live artifacts above.

The [SDK maintenance plan](../design/sdk-maintenance-plan.md) is complete in a12:
owner conformance tooling, diagnostics, matched measurements and package acceptance.
Independent Observer adoption can proceed against SDK interface v1.

**0.1.0a12** publishes the [portable owner conformance kit](../../conformance.md),
explicit [SDK diagnostics and cached assessment](../../sdk-diagnostics.md), and
[matched measurement/package evidence](../../evidence/2026-10-11-sdk-maintenance/README.md).
The maintenance sequence is complete without a speculative core optimization.
This package checkpoint does not change live selections.

**0.1.0a13** hardens conformance certification and adds real publisher update/
restart coverage through owned IPC with local and remote-proof bindings. SDK v1
and runtime contracts stay unchanged; see the
[follow-up acceptance](../../evidence/2026-10-11-conformance-followup/README.md).

The completed research track is the [WSS roadmap](../experiments/wss-roadmap.md): isolated carrier,
authenticated endpoint binding, native state acceptance and matched measurements.
The a14 source/private-wheel candidate promotes optional native WSS under
[lock revision 2](../../../contracts/wss-v1/contract.md). See [WSS configuration and SDK](../../wss.md)
for polling, push, the separate `mesh-plus-wss` CLI and operational limits.
Existing wire/profile schemas, SDK v1 defaults and live selections remain unchanged.

The **a15 release** adds a generic cached publisher and trusted installed
factory hook for independent Observer publisher ownership. See the
[publisher API and owner handoff](../../publisher-api.md). Existing defaults and
the wire contract remain unchanged; no live selection is made.

Start with the [integration handoff](../../handoff.md) for ownership, entry points,
acceptance gates and current evidence. The
[implementation checkpoints](../design/implementation-progress.md) preserve history.
The [controlled networking benchmark](../../../studies/controlled/README.md) provides
pinned, exact-work IPC/SSH/WSS comparisons; its
[assessment](../../evidence/2026-10-12-controlled-performance/README.md) retains
SSH defaults and unchanged runtime bytes.

The [admission simplification assessment](../../evidence/2026-10-13-simplification/README.md)
removes repeated fleet scans and reuses fixed control schemas while preserving
full boundary admission, mutable-view checks and the accepted Agent timing extension.
Its private a16 wheels are separate from the published release and live pins.

The additive [prepared consumer interface](../../prepared-consumer-api.md) offers
explicit generation-static preparation for repeated watch reads. Existing
ReadGuard/current_sessions behavior and all wire/schema bytes remain unchanged.
Owner certification and selective adoption are separate from Mesh implementation.

The [state contract freeze](../../contract-freeze.md) defines the interfaces ready
for independent implementation. [The checked lock](../../../contracts/LOCK.json) binds
normative inputs and native schema baselines; CI rejects unreviewed drift.

## Design package

- [Architecture and decisions](../../architecture.md)
- [Base read contract](../../../contracts/mesh-read-v1/contract.md)
- [Observer contract adaptations](../design/observer-adaptation.md)
- [Agent event delivery boundary](../design/event-delivery.md)
- [Mesh Plus components](../../components.md)
- [Transport and subscription design](../design/transport-design.md)
- [Backend and protocol evaluation](../design/transport-evaluation.md)
- [Delivery protocol candidate](../../../contracts/mesh-delivery-v1/contract.md)
- [Transport validation and implementation gates](../design/transport-validation.md)
- [SSH Plus integration](../../ssh-plus-integration.md)
- [Migration and acceptance](../design/migration-and-validation.md)
- [Source baselines and research](../design/research.md)
- [Frozen source reference provenance](../../../reference/README.md)
- [Design review and results](../design/design-review.md)

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
moving producer track. Agent Plus is an independent native-manager entry/window
client through Host Mesh; Agent read utilities consume Observer's public read
facades. Agent Plus's former external conversation-control model is historical.

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
Neither option deploys artifacts. See the [handoff](../../handoff.md#validation).

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
[validation evidence](../../evidence/design-validation.json).

The second candidate adds [delivery validation](../../evidence/delivery-validation.json)
and an optional [owned carrier study](../design/transport-validation.md#results-and-reproduction).
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
published SSH Plus catalog. See [configuration and acceptance](../design/implementation-progress.md)
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

The [Mesh operations pass](../design/mesh-operations.md) describes diagnostic limits,
the synthetic fault/resource lab and the proposed optional connection pool.
The a8 measurement interface adds `read --metrics` and `watch --metrics`: final redacted Reader
counters go to stderr, leaving protocol stdout unchanged. Watch reports on
Ctrl-C after owned cleanup. Python consumers may call `Reader.inspect()` while
running or after completion; totals include retired channels.
