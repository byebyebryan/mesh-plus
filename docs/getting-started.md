# Install and inspect Mesh Plus

Mesh Plus is reusable authority and delivery code, not a native agent collector
or an automatic fleet-discovery service. Begin with package metadata, then add
only the authority or cached source required by your client.

## Install

Python 3.11+ is required. From a maintained source checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
mesh-plus --help
mesh-plus doctor
```

`doctor` reports installed package versions; it does not start an Observer or
native provider. Public release assets and immutable provenance are linked from
[operations](maintenance/operations.md). No package-index publication is implied.

## Inspect configured hosts

The default process authority uses the public SSH Plus Host Mesh facade.
Install/configure SSH Plus and make `rofi-ssh-plus` available on `PATH`:

```sh
mesh-plus hosts --authority ssh-plus
```

Use `mesh-plus hosts --help` for supported explicit authority selection.
Configuration owns local identity, logical peers and ordered SSH routes.
History, `known_hosts`, DNS and remote observed rows do not discover new peers.
Routes are directional; a host which reads another host is not automatically
readable in reverse. [Host authority](guides/host-routing.md) explains ownership.

## Add cached state deliberately

A domain read additionally requires a reviewed pure Observer profile, a running
host-local cached service and an explicitly configured publisher/bridge source.
The bridge exports only its owning host, not an already aggregated fleet.

Use the owning Observer's setup guide for its collector and native service.
Then follow the [integration handoff](guides/integration.md), [publisher reference](reference/publishers.md)
and [SDK](reference/sdk.md). Mesh transports published state without collecting native
facts. A missing or incompatible endpoint fails explicitly; there is no provider
startup, fresh-read fallback or automatic reverse route.

Prepared reads, WSS and the complete-view change feed are separate opt-in
interfaces. Do not select them merely because they are installed. Their source,
package, native and consumer gates remain independent.
