# SDK diagnostics and cached validity assessment

`mesh-plus doctor` and `probe` retain diagnostics v1 and their existing meanings.
Probe success means acquisition of a validated cached snapshot or pushed
baseline. It does not establish freshness or fleet authority.

`mesh-plus doctor --sdk` explicitly selects diagnostics v2, adding SDK interface
version and fixed profile descriptors. It remains offline; package versions do
not prove native semantic compatibility. Descriptor/binding failures use a safe
allowlist in v2; unknown errors remain `rejected`. Neither format exposes private
paths, destinations, records or arbitrary exception messages.

```sh
mesh-plus assess --domain agent --source agent \
  --socket /run/user/1000/mesh-plus-agent/read.sock --scope fleet
mesh-plus assess --domain tmux --source tmux_default \
  --socket /private/mesh.sock --scope local --local-host my-host --mode subscribe
```

Assessment returns `mesh-plus.diagnostics.v2` separately from the frozen Read
envelope. It uses configured Reader polling or a guarded subscription, with
route reporting disabled. `--timeout-ms 1..60000` includes catalog resolution
and acquisition; owned cleanup has its existing additional grace. No collection,
refresh, history update or live selection occurs. Subscription requires a real
baseline; missing capabilities do not downgrade to polling.

`ok`/exit 0 means some validated delivery was acquired and cleanup completed.
It does not mean all hosts or records are current. `sample` separately reports
delivery completeness, host-index outcomes, current/expired receipt counts and
raw/current record counts. A current empty inventory can succeed with zero rows;
warming/nonpositive evidence remains distinguishable. Original positive receipt
expiry is considered even after Reader has downgraded it. Native clocks stay
host-scoped; remote expiry uses the acquired nonce proof and reviewed RTT margin.
Reports contain indices rather than host identities or record bodies.

The watch guard is disconnected and every iterator/connection retired before
returning. `currentRecordsAtSample` is a past sample; `retainedAuthority` is always
false. This command does not monitor ongoing continuity, and cannot detect a
later disconnect or grant action authority. A healthy host can be reported with
other hosts partial, connecting or unavailable.

Python consumers call `mesh_plus.diagnostics.assess(reader, mode=..., timeout_ms=...)`
with their explicit-profile Reader, or `assess_configured(domain, ..., profile=...)`.
Those helpers are a diagnostic interface, not new exports in `mesh_plus.api`.
`assess_configured` rejects route-reporting opt-in. The CLI retains supported
reference facades; it does not dynamically load arbitrary profiles.
