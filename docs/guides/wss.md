# Optional WSS transport

WSS carries polling and pushed replacement state under the same frozen
Read/Delivery envelopes and pure Observer profiles as IPC/SSH. Its
[addendum](../../contracts/wss-v1/contract.md) defines authorization, selection
and resource guarantees. Installation alone does not select WSS in a reader.

Install the optional extra into a dedicated environment:

```sh
rtk proxy uv pip install --python /absolute/environment/bin/python '/absolute/mesh_plus-0.1.0a25-py3-none-any.whl[wss]'
rtk proxy /absolute/environment/bin/mesh-plus-wss doctor
```

Download and verify the selected a25 wheel from the GitHub prerelease before installing.
No package-index publication is implied. WSS uses the documented
[websockets Sans-I/O API](https://websockets.readthedocs.io/en/stable/howto/sansio.html)
over owned TLS streams, with no high-level proxy/redirect discovery. It is a
direct native endpoint suitable for an explicitly bound LAN/tailnet address.
Browser clients, reverse proxies and automatic carrier fallback are not supported.
Hostname setup owns a bounded standard-library DNS helper process; numeric
addresses bypass it. TLS still checks the configured hostname. Failed DNS setup
reaps its helper rather than leaving an asyncio executor thread. Scoped IPv6
literals are excluded. Measure cold setup against the actual selected endpoint.

## Configuration and authority

All input paths must be absolute, regular, same-user private files in canonical
same-user private directories. Put configuration on an owner-controlled local
filesystem. Use mode 0700 for directories and 0600 for files, including the public
CA/certificate/catalog files. Initial capture is synchronous. Later checks own at
most one daemon read job per configuration owner; a timed-out job cannot deliver
late results or admit more reads while outstanding. Explicit close reports
unretired jobs. Neither caller deadlines nor shutdown can interrupt a kernel
filesystem call that remains blocked.

The client captures five files: Host Mesh catalog JSON, WSS registry JSON, CA PEM,
client certificate PEM and client private key PEM. Obtain the catalog through
the existing selected Host Mesh authority. Updating its captured file is an
explicit composition-owner operation; this API does not poll SSH Plus itself.
Canonical remote hosts still require their existing Host Mesh SSH routes, even
when this selection chooses WSS. WSS-only host authority is a separate feature.

Example registry, with `beta` already present in the captured catalog:

```json
{
  "protocol": "mesh-plus.wss.v1",
  "endpoints": [{
    "hostId": "beta",
    "sourceId": "default",
    "profile": "tmux-observer.mesh-candidate.v1",
    "url": "wss://beta.example:9443/mesh/state",
    "product": "state",
    "capabilities": ["snapshot", "proof", "subscribe"]
  }]
}
```

The listener captures CA PEM, server certificate PEM and private key PEM, plus a
live authorization JSON file. The server certificate must cover the registry
URL's hostname or IP; client certificates must chain to the listener's CA.
Authorization keys are lowercase SHA256 of client certificate **DER** bytes:

```json
{
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef":
    ["beta", "default", "tmux-observer.mesh-candidate.v1"]
}
```

This fingerprint is a placeholder. The triple must exactly match the configured
publisher. Rotation explicitly overlaps old/new fingerprints, then removes old
authorization. Any observed allowlist change retires existing channels for fresh
admission. Trust/certificate/key replacement also revokes existing channels;
restart/reload with a new captured configuration to admit replacement credentials.
Clients likewise create a new Selection after configuration changes.

## Listener and client CLI

`mesh-plus-wss serve` exports one cached Observer source through the existing
private `sources.toml` descriptor. It does not start a collector:

```sh
rtk proxy mesh-plus-wss serve --config /private/sources.toml --source default \
  --address 100.64.0.10 --port 9443 --authorization /private/authorization.json \
  --ca /private/ca.pem --certificate /private/server.pem --key /private/server.key
```

Use an explicitly chosen numeric IPv4/IPv6 address; loopback is also supported.
The command emits one readiness JSON line, then waits for SIGTERM/SIGINT and
retires its accepted sockets/tasks. At most four active/pending TLS clients are
admitted per listener. OS buffers and kernel backlog are outside this count.

`read`, `watch` and `probe` share these explicit client inputs:

```sh
rtk proxy mesh-plus-wss read --catalog /private/catalog.json \
  --registry /private/registry.json --domain tmux --source default \
  --socket /private/local-mesh.sock --scope hosts --hosts beta \
  --ca /private/ca.pem --certificate /private/client.pem --key /private/client.key
```

Replace `read` with `watch` for pushed replacement views, or `probe --mode subscribe`
for a bounded subscription-baseline diagnostic. Probe requires one explicit WSS
host. Add `--metrics` to read/watch for final redacted stderr counters. Protocol
stdout remains Read JSON; doctor/probe stdout is diagnostic JSON.

Fleet read/watch uses registered WSS hosts, local IPC, and captured SSH bindings
for unregistered remote hosts. A failed WSS host remains unavailable while
healthy siblings continue; it never falls back to SSH. These commands perform no
SSH route-health or picker-history writes.

## Pure-profile SDK

```python
from mesh_plus.wss import Selection, configured_reader

selection = Selection.load(catalog, registry, ca, certificate, key)
try:
    reader = await configured_reader(
        "tmux", selection=selection, source="default", socket=local_mesh_socket,
        scope="fleet", profile=owner_pure_profile,
    )
    response = await reader.snapshot()
    stream = reader.watch()
    try:
        async for response in stream:
            # Use the same profile-bound ReadGuard as with IPC/SSH.
            consume(response)
    finally:
        await stream.aclose()
finally:
    selection.close()
```

Reader owns connected Clients. The caller owns Selection and explicitly closes
it after retiring readers. Never retain a view as authority after disconnection.
Source freshness, native validation, nonce proofs and gap/resync retain existing
semantics. WebSocket liveness does not renew producer receipts.

For a publisher with a pure adapter, create `ServerConfiguration`, then a
`Listener(configuration.context, Bridge(adapter).serve, configuration.authorize,
(adapter.host, adapter.source, adapter.profile))`. Start with explicit
`address=`/port, close the Listener, then close ServerConfiguration. The adapter
is trusted and fixed; incoming requests cannot select a different publisher.

## Acceptance and operational gate

```sh
rtk proxy .venv/bin/python scripts/check.py --wss
rtk proxy .venv/bin/python scripts/check.py --wss --native
```

The standalone optional gate uses independent frozen fixture profiles. Native
acceptance requires the exact producer packages declared by the selected gate. Installed
wheel checks additionally use `scripts/check-wss.py --installed --native`.

Before selecting this on real hosts, accept firewall/tailnet reachability,
service restart, certificate replacement, network loss, physical suspend and
rollback on an owned fleet pair. Rollback removes WSS selection, stops its
listener and explicitly restores the separately pinned SSH configuration. No
chezmoi configuration or live artifact is changed by the implementation pass.

## Owner reader selection

Ordinary owners construct `mesh_plus.api.configured_reader` for IPC/SSH. WSS
requires an explicit networking selection with captured Host Mesh catalog,
endpoint registry, CA, client certificate and key, then
`mesh_plus.wss.configured_reader` with the existing pure profile/source/local
socket. Keep this choice in the networking binding, never in domain rows.

Registered WSS endpoints fail as unavailable without automatic SSH fallback.
Close the Reader stream before `Selection.close()`. A trust/selection change
revokes existing watches and requires fresh selection/baseline. Retain native
lease, guard and cleanup rules. Native/fault/resource and rollback qualification
belongs to each actual owner; SSH authority needs no WSS publisher/reader.
