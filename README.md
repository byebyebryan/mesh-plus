# Mesh Plus design

Mesh Plus owns request/reply and subscription delivery across a configured fleet. A
mesh-aware domain contract has the same response shape for one local host and
several hosts. Domain records keep their identity and meaning; networking adds
host outcomes, delivery provenance and conservative validity information.

Status: design candidate, 2026-10-09. This repository contains specifications,
schemas, examples and executable design checks. It contains no networking
runtime, selected artifact or deployed migration.

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
Current suites pass 116 read checks and 161 delivery checks. The carrier study
uses temporary synthetic IPC/SSH/WSS endpoints, not ordinary Observer services.
