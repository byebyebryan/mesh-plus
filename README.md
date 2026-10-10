# Mesh Plus

Mesh Plus owns request/reply and subscription delivery across a configured fleet. A
mesh-aware domain contract has the same response shape for one local host and
several hosts. Domain records keep their identity and meaning; networking adds
host outcomes, delivery provenance and conservative validity information.

Status: **0.1.0a7 released and selected**, 2026-10-10. Polling and pushed state
over local IPC and SSH stdio are implemented against a frozen contract. Snap and
Starship select SDK a7 for the shared public CLI/authority and Tmux Observer's
fleet transport. The [accepted Tmux rollout](https://github.com/byebyebryan/tmux-observer/blob/main/docs/evidence/2026-10-10-catalog-bound-fix/README.md)
records exact package/native, headless, resource, capacity, installed recovery
and paired rollback gates. Agent's reader/collector/writer and private SDK a4
resident bridge remain independently selected and verified. Ordered events/replay,
WSS, a shared fleet broker and further Plus/device migrations remain deferred.

Start with the [integration handoff](docs/handoff.md) for ownership, entry points,
acceptance gates and current evidence. The
[implementation checkpoints](docs/implementation-progress.md) preserve history.

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

This runs the lock, Read/Delivery oracles, core runtime tests and lint. It needs
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
Observer 0.6.0a2 and Tmux Plus 0.12.0a2 select the shared Mesh transport on Snap
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
