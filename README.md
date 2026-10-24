# Mesh Plus

Reusable host authority and bounded cached-state delivery for a configured fleet.
Mesh owns logical hosts, routes and delivery validity; Observer producers own
the meaning and freshness of their records.

[Project showcase](https://dev.byebyebryan.com/fleet-plus/projects/mesh-plus/) ·
[Get started](docs/getting-started.md) · [Documentation](docs/README.md)

## Start from source

Requires Python 3.11+. Install into a dedicated environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
mesh-plus --help
mesh-plus doctor
```

This installs delivery and authority code. Host inspection additionally needs
configured host authority; domain reads need a compatible Observer profile and
an explicitly running cached publisher. See [getting started](docs/getting-started.md).
Mesh never starts a native provider to satisfy a read.

## Interfaces

| Need | Reference |
| --- | --- |
| Logical hosts and directional routes | [Host authority](docs/ssh-plus-integration.md) |
| Cached polling and replacement watches | [SDK 1](docs/sdk-api.md) and [frozen contracts](docs/contract-freeze.md) |
| Export an Observer-owned cached source | [Publisher API](docs/publisher-api.md) |
| Repeated consumer reads and selection | [Prepared reads](docs/prepared-consumer-api.md) and [owned admission](docs/cpu-admission-api.md) |
| Diagnose or qualify an integration | [Integration handoff](docs/handoff.md) |

Routes are endpoint-specific and directional. Reading from a peer grants it no
reverse route. Delivery preserves unknown, partial, stale and unavailable
producer evidence. A heartbeat or copied view renews no native fact.

## Develop

```sh
python -m pip install jsonschema==4.26.0 ruff==0.16.10
python scripts/check.py
```

The standalone gate requires no sibling checkout or native provider. See
[development](docs/development.md) for optional WSS, native and source-parity gates.

## Releases and scope

[0.1.0a25](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a25)
is the current published prerelease. Full Agent, working-set, Tmux and Host Mesh
interfaces remain independently selected; standalone Agent active-only support
is withdrawn. [Operations](docs/operations.md) links release/deployment evidence.

Ordinary delivery uses complete views. Optional view-feed and WSS support need
explicit selection and acceptance. Delta-sync remains deferred and dark after
failed qualification. The [history index](docs/history/README.md) separates those
studies and old rollout ledgers from current setup and reference material.

[Fleet Plus](https://dev.byebyebryan.com/fleet-plus/) presents the ecosystem;
this repo owns transport/authority contracts, implementation and evidence.
