# Read-only host census

Collected at the UTC timestamps in the accompanying JSON snapshots during the
2026-10-23 ecosystem loop. The evidence directory retains the originating plan's
2026-10-22 date. No service, runtime, installed selection or firmware was changed.

The public Host Mesh list identified Starship, Snap and Carbon. SSH inspections
used the configured destination names, BatchMode, strict host keys, no host-key
updates, bounded connect/command deadlines and no shared control connection.
The probe invoked no native provider query, action, TUI, discovery or collector.

| Logical host | Native hostname | Observer collectors | Publication roles | Tmux | Dashboard |
| --- | --- | --- | --- | --- | --- |
| starship | starship | Default a8 | Full a5/a20; active a7/a23; working set a8/a24 | Owner and desktop fleet active | Bundle 164b7f99c40e7676, a8/a24 |
| snap | 80H1VV3 | Default and Work a8 | Full a5/a20; active a7/a23; Default and Work working set a8/a24 | Owner and desktop fleet active | Bundle 164b7f99c40e7676, a8/a24 |
| carbon | carbon | Default a8 | Full a5/a20; active a7/a23; working set a8/a24 | Owner and desktop fleet active | No selected entrypoint or unit observed |

All three hosts' public Agent read CLI links select Observer a5. Collector links
select a8. The historical writer link selects 0.4.0a16. Agent Plus links select
0.15.0a14 on all three. The Tmux source/managed census binds the selected
Observer a9 / Plus a8 / Mesh a24 tuple; its launcher paths remain independently
managed. A single `--version` command would not describe all these roles.

Unit MainPIDs, process start ticks and allowlisted artifact paths corroborate
that a8 collectors/working-set launchers, a7 active launchers and a5 full
publication are running. Starship/Snap dashboard process arguments also contain
the selected 164b7f99c40e7676 bundle and a8 interpreter. Unit state and argv are
metadata evidence; this census does not establish imported package-byte parity,
source freshness, successful native observation or physical display behavior.

Effective dashboard selections were inspected per host. Candidate manifests
referencing d4304a1ff7e07ac4 do not override the observed selection. Earlier
a7/a23 adoption handoffs do not describe this current baseline.

Process identities include only UID/PID/birth/executable metadata and
allowlisted installed artifact paths. Command lines, raw provider payloads,
conversation titles/content and environment variables are not captured.
Configuration files are hashed; only bounded dashboard selection fields are
exported. This is not an activity or native lifecycle census.

## Inputs and limitations

- [Collector](collect_host_census.py)
- [Starship snapshot](host-starship.json)
- [Snap snapshot](host-snap.json)
- [Carbon snapshot](host-carbon.json)
- Source and managed-role consumers are traced separately in the source census.

These snapshots show that the retained roles are actually enabled/running. They
do not establish demand for every publication role. Unknown manual/external
consumers remain explicit; a role with no known consumer is a retirement
proposal rather than permission to stop its unit. Native processes can change
through ordinary user activity during the loop; no ownership or shutdown right
is inferred from the process snapshot.
