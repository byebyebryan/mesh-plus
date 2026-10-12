# WSS fleet planning inventory

2026-10-12. Read-only snapshots from Snap and Starship support the
[trial plan](../../wss-fleet-trial-plan.md). They establish current host identity,
tailnet presence, selected manifest metadata, observed user-unit states and
unoccupied proposed TCP ports. They do **not** establish listener reachability,
firewall/tailnet ACL permission, verified installed payload parity, native producer
semantics, resource budgets or a lasting selection.

- [Snap](snap.json): Host Mesh identity snap, kernel hostname 80H1VV3.
- [Starship](starship.json): Host Mesh/kernel identity starship.
- Both: Python 3.14.8, OpenSSL 3.6.5; Tmux Observer a6/a13 reader/a10 shared bridge,
  Agent a18/a11 reader with its retained a16/a10 cached bridge recorded separately.
- Tailnet IPv4: Snap 100.70.82.105, Starship 100.84.31.64; both reported online.
- Proposed ports 9443/9444 had no TCP listener at observation time. An empty
  listener inventory is not firewall/reachability acceptance.
- LAN addresses are on different subnets; direct LAN testing is conditional.
- Ordinary owner and Agent cached bridge units remained active. No service restart,
  configuration write, WSS socket connection, collection or authority report ran.

Reproduce from Mesh's owning repository:

```sh
rtk proxy python scripts/wss-fleet-preflight.py --host-id snap
rtk proxy ssh -T -o BatchMode=yes -o ConnectTimeout=5 -o ConnectionAttempts=1 \
  -o StrictHostKeyChecking=yes starship 'python3 - --host-id starship' \
  < scripts/wss-fleet-preflight.py
```

The script uses only stdlib/read-only process queries, bounded per-command waits,
selected manifest metadata and filtered tailscale/ip/systemd/ss outputs. It reads
no credentials or native session contents. Existing strict SSH authentication is
used; no remote file is installed. Unknown/failed queries retain explicit error
objects. Preflight output is dated and must be refreshed before execution,
especially while owner agents develop or select new immutable artifacts.

Project scripts/docs/evidence live here. Chezmoi is unchanged; only a future
lasting deployment may add necessary managed configuration there. The source
trial plan, not these snapshots, defines staged execution and failure criteria.
