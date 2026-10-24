# Mesh Plus

Reusable host authority and bounded cached-state delivery for a configured fleet.
Mesh owns logical hosts, routes and delivery validity; Observer producers own
what their records mean. Local IPC and SSH carry already published state.

[Project walkthrough](https://dev.byebyebryan.com/fleet-plus/projects/mesh-plus/) ·
[SDK reference](docs/sdk-api.md) · [Host Mesh interface](docs/ssh-plus-integration.md)

## What it provides

- One host/route authority behind SSH Plus's public Host Mesh interface.
- Explicit cached reads and replacement-state watches over local IPC and SSH.
- Conservative handling of source identity, coverage, gaps and expiry.
- Pure Observer profiles for Agent and Tmux clients; provider collection remains
  with the owning Observer and presentation/actions with each consumer.

Host membership is endpoint-specific and directional. A host that can read a
peer does not grant that peer a reverse route. No automatic full mesh is implied.

## Current release and selections

[**0.1.0a25**](https://github.com/byebyebryan/mesh-plus/releases/tag/v0.1.0a25)
withdraws the standalone Agent active profile. Working-set, full Agent, Tmux
and Host Mesh boundaries remain. Working-set retains active membership.
The [public delivery closeout](docs/evidence/2026-10-23-public-delivery/README.md)
records exact release assets, public-download verification and scoped deployment.

Roles retain independent reviewed versions: Agent collectors/working-set use
Observer a9 / Mesh a25; the full publisher, Tmux, dashboard and SSH authority
have separate selections. Read the [integration handoff](docs/handoff.md) and
owner deployment manifests before changing any role.

Delta-sync development is stopped behind its [dark-feature gate](docs/delta-sync-dark-status.md)
after failed CPU/capacity gates. The separately published [view-feed API](docs/view-feed-api.md)
and optional WSS transport require explicit selection and their own adoption
acceptance. Ordinary configured readers retain complete-view delivery.

## Install and inspect

Python 3.11+ is required. From a checkout, use a dedicated environment:

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/mesh-plus hosts --authority ssh-plus
```

The host command requires an installed, configured SSH Plus public facade.
Domain delivery additionally needs the matching Observer package and explicitly
configured cached publisher. See [source configuration](docs/implementation-progress.md),
[components](docs/components.md) and [transport design](docs/transport-design.md).
Mesh does not start a native provider to satisfy a read.

## Develop

Run the standalone source gate with its declared dependencies:

```sh
uv pip install --python .venv/bin/python jsonschema==4.26.0 ruff==0.16.10
.venv/bin/python scripts/check.py
```

Native/SSH, optional WSS and sibling-source checks have explicit additional
inputs and scopes; see [validation](docs/handoff.md#validation). Source tests,
package qualification and managed deployment establish separate things.

## Documentation

- [Architecture](docs/architecture.md) and [component boundaries](docs/components.md).
- [Frozen contracts](docs/contract-freeze.md) and [SDK](docs/sdk-api.md).
- [Local ecosystem role](docs/ecosystem-role.md) and [Fleet Plus architecture](https://dev.byebyebryan.com/fleet-plus/architecture/).
- [Maintained-source orientation](docs/source-orientation.md).
- [Historical README checkpoints](docs/readme-history.md), preserving earlier
  releases, experiments, examples and acceptance links in their original scope.
